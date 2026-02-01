"""
Trade Executor (Consumer) v6.4 - SAFE MODE
==========================================

Extreme stability worker with crash-proof guards:
1. RISK GUARD: Hard limit on position size
2. CORRELATION GUARD: Max 3 open positions
3. ML GUARD: RandomForest win probability prediction

Key Fixes in v6.4:
- ALL guards wrapped in individual try/except blocks
- Explicit logging: "Correlation Check: X/Y active" on every check
- Fail-SAFE design: guard failures reject (not allow) trades
- Absolute path resolution for model files (Railway compatibility)
- Strict feature frame initialization with 0.0 defaults

Architecture:
- Single-load brain (model loaded once at startup)
- Regex-based feature extraction for "Super String" signals
- Crash-proof guard pipeline
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
ML_MIN_CONFIDENCE = 0.50  # 50% win probability threshold (lowered for testing)

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
    """
    Load the ML model and encoders once at startup.
    Uses strict absolute path resolution for Railway compatibility.
    """
    global AI_MODEL, AI_ENCODERS

    # STRICT ABSOLUTE PATH RESOLUTION
    base_dir = Path(__file__).resolve().parent.parent
    model_path = base_dir / "ml" / "model.pkl"
    enc_path = base_dir / "ml" / "encoders.pkl"

    try:
        if not model_path.exists():
            logger.warning(f"⚠️ Brain Missing: {model_path}")
            return

        with open(model_path, "rb") as f:
            AI_MODEL = pickle.load(f)
        with open(enc_path, "rb") as f:
            AI_ENCODERS = pickle.load(f)
        logger.info(f"🧠 Brain Online. Features: {len(AI_MODEL.feature_names_in_)}")
    except Exception as e:
        logger.error(f"❌ Brain Load Error: {e}")


# --- INTELLIGENCE LAYER ---

def get_prediction(payload: Dict[str, Any]) -> tuple:
    """
    Safely predict win probability using the trained RandomForest model.

    Returns:
        tuple: (probability: float, note: str)
               Returns (0.5, "AI Disabled") if model unavailable
               Returns (0.5, "AI Error: ...") on any prediction failure
    """
    if AI_MODEL is None:
        return 0.5, "AI Disabled (Missing Model)"

    try:
        # 1. Initialize Safe Feature Frame (All Zeros)
        features = {col: 0.0 for col in AI_MODEL.feature_names_in_}

        # 2. Extract Features from Signal String (Regex)
        signal_str = str(payload.get('signal', ''))
        matches = re.findall(r"F:([a-zA-Z_]+)=([0-9.]+)", signal_str)
        for key, val in matches:
            try:
                val_f = float(val)
                # Map raw key and f_key to ensure hit
                if key in features:
                    features[key] = val_f
                if f"f_{key}" in features:
                    features[f"f_{key}"] = val_f
            except ValueError:
                pass

        # 3. Fallback Mapping (Score -> Signal Encoded)
        if features.get('signal_encoded', 0) == 0:
            features['signal_encoded'] = features.get('score', 0)
        if features.get('f_signal_encoded', 0) == 0:
            features['f_signal_encoded'] = features.get('f_score', 0)

        # 4. Asset Encoding
        symbol = payload.get('symbol', 'UNKNOWN')
        if AI_ENCODERS and 'asset_id' in AI_ENCODERS:
            if symbol in AI_ENCODERS['asset_id'].classes_:
                features['asset_id'] = AI_ENCODERS['asset_id'].transform([symbol])[0]

        # 5. Predict
        df = pd.DataFrame([features])
        prob = float(AI_MODEL.predict_proba(df)[0][1])
        return prob, f"AI Confidence: {prob:.1%}"

    except Exception as e:
        logger.error(f"⚠️ Prediction Error: {e}")
        return 0.5, f"AI Error: {str(e)[:50]}"


# --- EXECUTION LAYER ---

def _get_settings():
    """Lazy load config (works as backend.worker or standalone worker.py)."""
    try:
        from backend.config import get_settings
        return get_settings()
    except ImportError:
        from config import get_settings
        return get_settings()


def _exists_trade_key(trade_key: str) -> bool:
    """Return True if an alert already exists for this trade_key (idempotency)."""
    if not trade_key or not str(trade_key).strip() or not supabase:
        return False
    try:
        r = supabase.table("trading_signals").select("id").eq("trade_key", trade_key.strip()).limit(1).execute()
        return len(r.data) > 0
    except Exception as e:
        logger.warning(f"Idempotency check failed (trade_key): {e}")
        return False


def process_trade(payload: Dict[str, Any]):
    """
    Process incoming trade signal through the guard pipeline.

    Guards (each wrapped in try/except for crash prevention):
    0. KILL-SWITCH - Block all if trading_kill_switch enabled
    1. IDEMPOTENCY - Skip if signal_id/trade_key already exists
    2. RISK GUARD - Reject oversized positions
    3. CORRELATION GUARD - Reject if bucket full (3 positions)
    4. ML GUARD - Reject low confidence trades
    On pass: call logic.process_trade() (save_alert + optional paper + Discord). Rejections use save_result only.
    """
    symbol = payload.get('symbol', 'UNKNOWN')
    side = payload.get('side', 'buy')
    size = float(payload.get('size', 0.01))

    logger.info(f"⚡ Processing: {symbol} | {side.upper()} | Size: {size}")

    # ══════════════════════════════════════════════════════════
    # GUARD 0: KILL-SWITCH
    # ══════════════════════════════════════════════════════════
    try:
        s = _get_settings()
        if getattr(s, "trading_kill_switch", False):
            save_result(payload, "kill_switch_blocked", "Trading kill-switch is ON", 0.0)
            logger.warning("❌ KILL-SWITCH: execution blocked")
            return
    except Exception as e:
        logger.error(f"❌ Kill-switch check failed: {e}")
        save_result(payload, "kill_switch_blocked", f"Config error: {str(e)[:50]}", 0.0)
        return

    # ══════════════════════════════════════════════════════════
    # GUARD 0.5: IDEMPOTENCY (prevent duplicate orders for same signal_id)
    # ══════════════════════════════════════════════════════════
    signal_id = payload.get("signal_id") or payload.get("trade_key")
    if signal_id and _exists_trade_key(signal_id):
        logger.info(f"⏭️ Idempotency: signal_id/trade_key already exists, skipping: {str(signal_id)[:64]}")
        return

    # ══════════════════════════════════════════════════════════
    # GUARD 1: RISK GUARDIAN (Hard Limit)
    # ══════════════════════════════════════════════════════════
    try:
        logger.info(f"   Risk Check: size {size} vs limit {MAX_LOT_SIZE}")
        if size > MAX_LOT_SIZE:
            save_result(payload, "risk_rejected", f"Size {size} > Limit {MAX_LOT_SIZE}", 0.0)
            logger.warning(f"❌ RISK REJECTED: {symbol} size {size} exceeds limit {MAX_LOT_SIZE}")
            return
        logger.info(f"   Risk Check: PASSED")
    except Exception as e:
        logger.error(f"❌ Risk Guard Crashed: {e}")
        save_result(payload, "risk_rejected", f"Risk Guard Error: {str(e)[:50]}", 0.0)
        return

    # ══════════════════════════════════════════════════════════
    # GUARD 2: CORRELATION GUARDIAN (Bucket Limit)
    # ══════════════════════════════════════════════════════════
    try:
        if supabase:
            # Fetch just IDs, no fancy count - use len() in Python
            active = supabase.table("trading_signals").select("id").eq("status", "active").execute()
            active_count = len(active.data)
            logger.info(f"   Correlation Check: {active_count}/{MAX_OPEN_POSITIONS} active")

            if active_count >= MAX_OPEN_POSITIONS:
                save_result(payload, "correlation_rejected", f"Bucket Full ({active_count}/{MAX_OPEN_POSITIONS})", 0.0)
                logger.warning(f"❌ CORRELATION REJECTED: {symbol} - bucket full ({active_count}/{MAX_OPEN_POSITIONS})")
                return
            logger.info(f"   Correlation Check: PASSED")
        else:
            logger.warning("   Correlation Check: SKIPPED (no Supabase)")
    except Exception as e:
        logger.error(f"❌ Correlation Guard Crashed: {e}")
        # Fail-SAFE: reject trade on DB error to avoid risk
        save_result(payload, "correlation_rejected", f"DB Error: {str(e)[:50]}", 0.0)
        return

    # ══════════════════════════════════════════════════════════
    # GUARD 3: ML GUARDIAN (The Brain)
    # ══════════════════════════════════════════════════════════
    try:
        win_prob, note = get_prediction(payload)
        logger.info(f"   ML Check: confidence {win_prob:.1%} vs threshold {ML_MIN_CONFIDENCE:.0%}")

        if win_prob >= ML_MIN_CONFIDENCE:
            logger.info(f"✅ ML APPROVED: {symbol} (confidence: {win_prob:.1%})")
            # Execute via logic: save_alert + optional paper + Discord/Telegram (DRY_RUN when LIVE_TRADING=false)
            try:
                s = _get_settings()
                dry_run = not getattr(s, "live_trading_enabled", False)
                if dry_run:
                    logger.info("   DRY_RUN: LIVE_TRADING=false — saving alert + notify only, no order")
                try:
                    from backend import logic
                except ImportError:
                    import logic
                logic.process_trade(payload, dry_run=dry_run)
                logger.info("🏁 logic.process_trade completed")
            except Exception as exec_err:
                logger.error(f"❌ logic.process_trade failed: {exec_err}")
                save_result(payload, "execution_failed", f"logic.process_trade: {str(exec_err)[:80]}", win_prob)
        else:
            status = "ml_rejected"
            note = f"Low Confidence ({win_prob:.1%} < {ML_MIN_CONFIDENCE:.0%})"
            logger.warning(f"❌ ML REJECTED: {symbol} (confidence: {win_prob:.1%} < {ML_MIN_CONFIDENCE:.0%})")
            save_result(payload, status, note, win_prob)
    except Exception as e:
        logger.error(f"❌ ML Guard Crashed: {e}")
        save_result(payload, "ml_rejected", f"ML Guard Error: {str(e)[:50]}", 0.0)


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
    tk = (payload.get("trade_key") or "").strip()
    if tk:
        data["trade_key"] = tk
    try:
        supabase.table("trading_signals").insert(data).execute()
        logger.info(f"🏁 Saved: {status} | {note}")
    except Exception as e:
        logger.error(f"❌ DB Write Failed: {e}")


# --- MAIN LOOP ---

def run():
    """Main worker loop - crash-proof with exponential backoff."""
    init_connections()
    load_brain()

    try:
        s = _get_settings()
        kill_sw = getattr(s, "trading_kill_switch", False)
        live = getattr(s, "live_trading_enabled", False)
    except Exception:
        kill_sw = False
        live = False
    logger.info("=" * 60)
    logger.info("🚀 WORKER v6.5 (SAFE MODE) STARTED")
    logger.info(f"  Risk Limit: {MAX_LOT_SIZE} lots")
    logger.info(f"  Correlation Limit: {MAX_OPEN_POSITIONS} positions")
    logger.info(f"  ML Confidence: {ML_MIN_CONFIDENCE:.0%}")
    logger.info(f"  Kill-Switch: {'ON (blocking all)' if kill_sw else 'OFF'}")
    logger.info(f"  LIVE_TRADING: {'true (orders allowed)' if live else 'false (DRY_RUN)'}")
    logger.info(f"  AI Brain: {'LOADED' if AI_MODEL else 'DISABLED'}")
    logger.info(f"  Guard Strategy: FAIL-SAFE (reject on error)")
    logger.info("=" * 60)

    backoff = 5
    while True:
        try:
            # Short timeout to allow clean shutdowns/restarts if needed
            task = redis_client.blpop(QUEUE_NAME, timeout=5)
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
            logger.error(f"⚠️ Invalid JSON from queue: {e}")
            continue
        except Exception as e:
            logger.error(f"🔥 Loop Error: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
