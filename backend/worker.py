"""
Trade Executor (Consumer) v6.0 - OPTIMIZED
==========================================

Simplified, robust worker with three core guards:
1. RISK GUARD: Hard limit on position size
2. CORRELATION GUARD: Max 3 open positions
3. ML GUARD: RandomForest win probability prediction

Architecture:
- Single-load brain (model loaded once at startup)
- Regex-based feature extraction for "Super String" signals
- Fail-open error handling
- Clean Supabase logging
"""

import json
import logging
import os
import pickle
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from dotenv import load_dotenv
from redis import Redis
from supabase import create_client, Client

# --- SETUP ---
_backend = Path(__file__).resolve().parent
load_dotenv(_backend / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("TRINITY_WORKER")

# --- CONFIG ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
QUEUE_NAME = "trading_queue"

# Risk limits
MAX_LOT_SIZE = 0.30  # Hard limit (0.30+ = rejected)
MAX_OPEN_POSITIONS = 3  # Correlation bucket limit
ML_MIN_CONFIDENCE = 0.60  # 60% win probability threshold

# --- GLOBAL SINGLETONS ---
redis_client: Optional[Redis] = None
supabase: Optional[Client] = None
AI_MODEL = None
AI_ENCODERS = None


def init_connections():
    """Initialize Redis and Supabase connections."""
    global redis_client, supabase

    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connected")
    else:
        logger.warning("Supabase credentials missing - logging disabled")


def load_brain():
    """Load the ML model and encoders once at startup."""
    global AI_MODEL, AI_ENCODERS

    base_dir = Path(__file__).resolve().parent.parent
    model_path = base_dir / "ml" / "model.pkl"
    enc_path = base_dir / "ml" / "encoders.pkl"

    try:
        if model_path.exists():
            with open(model_path, "rb") as f:
                AI_MODEL = pickle.load(f)
            with open(enc_path, "rb") as f:
                AI_ENCODERS = pickle.load(f)
            logger.info(f"AI Brain Loaded. Features: {len(AI_MODEL.feature_names_in_)}")
        else:
            logger.warning("Brain Missing (ml/model.pkl). AI will be DISABLED.")
    except Exception as e:
        logger.error(f"Brain Damage: {e}")


# --- INTELLIGENCE LAYER ---

def extract_features(signal_str: str) -> Dict[str, float]:
    """
    Parse the 'Super String' from TradingView/Notion.

    Extracts key=value pairs like: F:score=95, F:signal_encoded=95
    Returns a dict mapping feature names to float values.
    """
    features = {}

    if not signal_str:
        return features

    # Regex to find F:key=value patterns (e.g., F:score=95)
    matches = re.findall(r"F:([a-zA-Z_]+)=([0-9.]+)", str(signal_str))
    for key, val in matches:
        try:
            float_val = float(val)
            features[key] = float_val
            # Double mapping for safety (both score and f_score)
            features[f"f_{key}"] = float_val
        except ValueError:
            pass

    # Hardcoded criticals (if missing)
    if 'score' in features and 'signal_encoded' not in features:
        features['signal_encoded'] = features['score']
    if 'f_score' in features and 'f_signal_encoded' not in features:
        features['f_signal_encoded'] = features['f_score']

    return features


def predict_success(signal_data: Dict[str, Any]) -> float:
    """
    Predict win probability using the trained RandomForest model.

    Returns:
        float: Win probability between 0.0 and 1.0
               Returns 0.5 (neutral) if model unavailable
    """
    if AI_MODEL is None:
        return 0.5

    try:
        # 1. Base Feature Frame (initialize with zeros)
        df = pd.DataFrame(columns=AI_MODEL.feature_names_in_)
        df.loc[0] = 0.0

        # 2. Extract features from signal string
        extracted = extract_features(signal_data.get('signal', ''))

        # 3. Encode asset_id if available
        sym = signal_data.get('symbol', 'UNKNOWN')
        if AI_ENCODERS and 'asset_id' in AI_ENCODERS:
            if sym in AI_ENCODERS['asset_id'].classes_:
                df.loc[0, 'asset_id'] = AI_ENCODERS['asset_id'].transform([sym])[0]

        # 4. Fill known features
        for col in df.columns:
            if col in extracted:
                df.loc[0, col] = extracted[col]

        # 5. Predict
        prob = AI_MODEL.predict_proba(df)[0][1]
        return float(prob)

    except Exception as e:
        logger.error(f"Prediction Failed: {e}")
        return 0.5


# --- EXECUTION LAYER ---

def process_trade(payload: Dict[str, Any]):
    """
    Process incoming trade signal through the guard pipeline.

    Guards:
    1. RISK GUARD - Reject oversized positions
    2. CORRELATION GUARD - Reject if bucket full (3 positions)
    3. ML GUARD - Reject low confidence trades
    """
    symbol = payload.get('symbol', 'UNKNOWN')
    side = payload.get('side', 'buy')
    size = float(payload.get('size', 0.01))

    logger.info(f"Processing: {symbol} | {side.upper()} | Size: {size}")

    # ══════════════════════════════════════════════════════════
    # GUARD 1: RISK GUARDIAN (Hard Limit)
    # ══════════════════════════════════════════════════════════
    if size > MAX_LOT_SIZE:
        save_result(payload, "risk_rejected", f"Size {size} > Limit {MAX_LOT_SIZE}", 0.0)
        logger.warning(f"RISK REJECTED: {symbol} size {size} exceeds limit {MAX_LOT_SIZE}")
        return

    # ══════════════════════════════════════════════════════════
    # GUARD 2: CORRELATION GUARDIAN (Bucket Limit)
    # ══════════════════════════════════════════════════════════
    if supabase:
        try:
            active = supabase.table("trading_signals").select("id").eq("status", "active").execute()
            if len(active.data) >= MAX_OPEN_POSITIONS:
                save_result(payload, "correlation_rejected", f"Bucket Full ({len(active.data)}/{MAX_OPEN_POSITIONS})", 0.0)
                logger.warning(f"CORRELATION REJECTED: {symbol} - bucket full ({len(active.data)}/{MAX_OPEN_POSITIONS})")
                return
        except Exception as e:
            logger.error(f"Correlation check failed: {e} - allowing trade (fail-open)")

    # ══════════════════════════════════════════════════════════
    # GUARD 3: ML GUARDIAN (The Brain)
    # ══════════════════════════════════════════════════════════
    win_prob = predict_success(payload)

    if win_prob >= ML_MIN_CONFIDENCE:
        status = "active"
        note = f"AI Approved (confidence: {win_prob:.1%})"
        logger.info(f"ML APPROVED: {symbol} (confidence: {win_prob:.1%})")
    else:
        status = "ml_rejected"
        note = f"Low Confidence ({win_prob:.1%} < {ML_MIN_CONFIDENCE:.0%})"
        logger.warning(f"ML REJECTED: {symbol} (confidence: {win_prob:.1%} < {ML_MIN_CONFIDENCE:.0%})")

    save_result(payload, status, note, win_prob)


def save_result(payload: Dict[str, Any], status: str, note: str, prob: float):
    """Log trade result to Supabase."""
    if not supabase:
        logger.warning(f"Supabase unavailable - result not saved: {status}")
        return

    data = {
        "symbol": payload.get('symbol', 'UNKNOWN'),
        "side": payload.get('side', 'buy'),
        "size": float(payload.get('size', 0.01)),
        "entry": float(payload.get('entry', 0)) if payload.get('entry') else None,
        "sl": float(payload.get('sl', 0)) if payload.get('sl') else None,
        "tp": float(payload.get('tp', 0)) if payload.get('tp') else None,
        "status": status,
        "notes": note,
        "ml_win_probability": prob,
        "run_mode": payload.get('run_mode', 'PAPER'),
    }

    try:
        supabase.table("trading_signals").insert(data).execute()
        logger.info(f"Saved: {status} | {note}")
    except Exception as e:
        logger.error(f"Failed to save to Supabase: {e}")


# --- MAIN LOOP ---

def run():
    """Main worker loop - never crashes."""
    init_connections()
    load_brain()

    logger.info("=" * 60)
    logger.info("WORKER v6.0 (OPTIMIZED) STARTED")
    logger.info(f"  Risk Limit: {MAX_LOT_SIZE} lots")
    logger.info(f"  Correlation Limit: {MAX_OPEN_POSITIONS} positions")
    logger.info(f"  ML Confidence: {ML_MIN_CONFIDENCE:.0%}")
    logger.info(f"  AI Brain: {'LOADED' if AI_MODEL else 'DISABLED'}")
    logger.info("=" * 60)

    backoff = 5
    while True:
        try:
            task = redis_client.blpop(QUEUE_NAME, timeout=30)
            backoff = 5  # Reset backoff on success

            if task is None:
                continue

            _key, payload_str = task
            payload = json.loads(payload_str)

            # Skip exit events (only process entries)
            if payload.get('event_type') == 'exit':
                logger.info(f"Exit event for {payload.get('symbol')} - skipping")
                continue

            process_trade(payload)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from queue: {e}")
            continue
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
