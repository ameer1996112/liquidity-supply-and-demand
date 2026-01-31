print("🚀 NEW WORKER CODE LOADED: v5.1 (Probability Fix)")  # <--- PROOF LINE
import os
import json
import time
import asyncio
import logging
import pickle
import pandas as pd
import numpy as np
from supabase import create_client, Client
from redis import Redis
from pathlib import Path

# --- CONFIGURATION ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- INIT CLIENTS ---
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- LOAD BRAIN (ML MODEL) ---
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "model.pkl"
ENCODER_PATH = BASE_DIR / "ml" / "encoders.pkl"

model = None
encoders = {}

try:
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        with open(ENCODER_PATH, "rb") as f:
            encoders = pickle.load(f)
        logger.info(f"🧠 AI Brain Loaded! Features: {getattr(model, 'feature_names_', 'Unknown')}")
    else:
        logger.warning("⚠️ ML Model not found. AI Guardian will be disabled.")
except Exception as e:
    logger.error(f"❌ Failed to load ML model: {e}")

# --- TRADING LOGIC ---

def calculate_position_size(account_balance, risk_per_trade, stop_loss_pips, symbol):
    """Calculates safe lot size based on risk %"""
    risk_amount = account_balance * risk_per_trade
    # Standard approximation: $10 per pip per lot (for standard pairs)
    # For JPY pairs, it's roughly $6.5 per pip.
    pip_value = 6.5 if "JPY" in symbol else 10.0
    
    if stop_loss_pips <= 0: return 0.01
    
    lots = risk_amount / (stop_loss_pips * pip_value)
    return round(lots, 2)

def ml_predict(signal_data):
    """Asks the AI Brain for a probability score"""
    if not model or not encoders:
        return 0.5 
        
    try:
        # 1. Extract Features
        features = {
            'asset_id': 0, 'hour': 12, 'day_of_week': 2, 'type_encoded': 0,
            'signal_encoded': 0, 'source_encoded': 0, 'session_encoded': 0, 'liq_distance': 50.0
        }
        
        # Symbol Encoding
        sym = signal_data.get('symbol', '')
        if 'symbol' in encoders and sym in encoders['symbol'].classes_:
            features['asset_id'] = encoders['symbol'].transform([sym])[0]
            
        # Time Encoding
        if 'time' in signal_data:
            dt = pd.to_datetime(signal_data['time'])
            features['hour'] = dt.hour
            features['day_of_week'] = dt.dayofweek

        # Signal Feature Extraction
        sig_str = signal_data.get('signal', '')
        import re
        f_pattern = re.compile(r'F:(\w+)=([\d.+-]+)')
        matches = f_pattern.findall(str(sig_str))
        for key, val in matches:
            features[f'f_{key.lower()}'] = float(val)

        # Create DataFrame 
        df_feat = pd.DataFrame([features])
        
        # Ensure all model columns exist
        for col in model.feature_names_:
            if col not in df_feat.columns:
                df_feat[col] = 0.0
                
        # Reorder columns 
        df_feat = df_feat[model.feature_names_]
        
        # Predict
        prob = model.predict_proba(df_feat)[0][1]
        return float(prob)

    except Exception as e:
        logger.error(f"🧠 Brain Freeze: {e}")
        return 0.5

def process_trade(signal):
    """Main Processor"""
    symbol = signal['symbol']
    side = signal['side']
    size = float(signal['size'])
    entry = float(signal['entry'])
    sl = float(signal['sl'])
    
    logger.info(f"⚡ Processing: {symbol} {side} {size} lots")

    # 1. RISK GUARDIAN
    price_diff = abs(entry - sl)
    contract_size = 100000
    converter = 155.0 if "JPY" in symbol else 1.0 
    risk_usd = (price_diff * contract_size * size) / converter
    
    if risk_usd > 500.0:
        save_result(signal, "risk_rejected", f"Risk too high: ${risk_usd:.2f}", 0.0)
        return

    # 2. CORRELATION GUARD
    active_trades = supabase.table("trading_signals").select("*").eq("status", "active").execute()
    if len(active_trades.data) >= 3:
        save_result(signal, "correlation_rejected", "Max trades (3) reached.", 0.0)
        return

    # 3. PINE GUARDIAN
    pips = price_diff * (100 if "JPY" in symbol else 10000)
    safe_lots = calculate_position_size(10000, 0.01, pips, symbol)
    
    # 50% tolerance for testing
    if abs(size - safe_lots) > (safe_lots * 0.5): 
        save_result(signal, "pine_rejected", f"Size mismatch: Sent {size}, Safe {safe_lots}", 0.0)
        return

    # 4. AI GUARDIAN
    win_prob = ml_predict(signal)
    
    if win_prob >= 0.60:
        status = "active"
        note = "AI Approved"
    else:
        status = "ml_rejected"
        note = f"AI Low Confidence: {win_prob:.2%}"
        
    save_result(signal, status, note, win_prob)

def save_result(signal, status, note, prob):
    """Saves to Supabase"""
    data = {
        "symbol": signal['symbol'], "side": signal['side'], "size": signal['size'],
        "entry": signal['entry'], "sl": signal['sl'], "tp": signal['tp'],
        "status": status, "notes": note,
        "ml_win_probability": prob,  # <--- CRITICAL LINE
        "run_mode": signal.get("run_mode", "PAPER")
    }
    try:
        supabase.table("trading_signals").insert(data).execute()
        logger.info(f"✅ Saved: {status} | Prob: {prob}")
    except Exception as e:
        logger.error(f"❌ DB Save Failed: {e}")

def run_worker():
    logger.info("👷 Worker Started & Listening...")
    while True:
        try:
            task = redis_client.blpop("trading_queue", timeout=5)
            if task:
                payload = json.loads(task[1])
                process_trade(payload)
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_worker()