import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = "https://grand-learning-production-bc96.up.railway.app" 
SECRET = os.getenv("WEBHOOK_SECRET", "c817492a65caa767fdc438f61b8c2b64404a4e4aa6d9edfac74514c07bae20c6")

def send_test_signal(symbol, entry, sl, tp, calculated_size, signal_features=None):
    # 1. Attach secret to the URL 
    params = {"secret": SECRET}
    
    # 2. The Payload
    payload = {
        "passphrase": SECRET,
        "symbol": symbol,
        "side": "buy",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "size": calculated_size,
        "run_mode": "PAPER",
        "time": "2026-01-27T15:00:00Z", # Tuesday (Good Day)
        "exchange": "OANDA",
        
        # CRITICAL: Injecting the "Feature Packet"
        # This tells the AI the RSI, Trend, and Volatility values
        "signal": signal_features or "Unknown" 
    }

    print(f"🧠 Testing Brain on {symbol}...")
    try:
        r = requests.post(f"{BASE_URL}/webhook", json=payload, params=params)
        print(f"   Status: {r.status_code}")
        if r.status_code != 200:
            print(f"   Response: {r.text}")
    except Exception as e:
        print(f"   Error: {e}")

print("--- STARTING 'RICH DATA' IQ TEST ---")

# 1. GBPCAD (The Skeptic)
# We send a "Naked" signal. The AI should still dislike the pair itself.
send_test_signal(
    symbol="GBPCAD", 
    entry=1.7500, 
    sl=1.7450, 
    tp=1.7600, 
    calculated_size=0.27,
    signal_features="Unknown"
)

time.sleep(2)

# 2. USDJPY (The Golden Child)
# We inject a KNOWN WINNING Feature Packet from your history (Trade #169)
# This setup historically made money, so the AI should love it.
winning_features = " | F:75,8,2,0,0.57,0,1,63.56,1,0,32.82,0,100,38.38,98.2,2.8,36.67"

send_test_signal(
    symbol="USDJPY", 
    entry=155.00, 
    sl=154.50, 
    tp=156.00, 
    calculated_size=0.30,
    signal_features=winning_features # <--- The Secret Sauce
)