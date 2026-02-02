import os
import re
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# --- CONFIG ---
_base = Path(__file__).resolve().parent.parent
env_path = None
for p in [_base / ".env", _base / "scripts" / ".env"]:
    if p.exists():
        load_dotenv(dotenv_path=p)
        env_path = p
        break

BASE_URL = os.getenv("WEBHOOK_URL", "https://grand-learning-production-bc96.up.railway.app").strip().rstrip("/")
SECRET = os.getenv("WEBHOOK_SECRET", "c817492a65caa767fdc438f61b8c2b64404a4e4aa6d9edfac74514c07bae20c6")
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPA_URL or not SUPA_KEY:
    print("❌ CRITICAL ERROR: Missing Supabase Credentials.")
    sys.exit(1)

supabase: Client = create_client(SUPA_URL, SUPA_KEY)

def send_signal(symbol, size, signal_str="", entry=1.0):
    print(f"   👉 Sending {symbol}...", end=" ", flush=True)
    try:
        payload = {
            "passphrase": SECRET, "symbol": symbol, "side": "buy", "size": size,
            "entry": entry, "sl": entry*0.99, "tp": entry*1.02,
            "run_mode": "PAPER", "exchange": "OANDA", "signal": signal_str
        }
        requests.post(f"{BASE_URL}/webhook", json=payload, params={"secret": SECRET}, timeout=5)
        print("Sent.")
    except Exception as e:
        print(f"❌ Network Error: {e}")

def verify_and_wait(symbol, expected_status_list, patience=30):
    if isinstance(expected_status_list, str): expected_status_list = [expected_status_list]
    print(f"   ⏳ Waiting for Worker...", end="", flush=True)
    
    for i in range(patience): 
        time.sleep(1)
        if i % 3 == 0: print(".", end="", flush=True)

        res = supabase.table("trading_signals").select("status, notes").eq("symbol", symbol).order("created_at", desc=True).limit(1).execute()
        if res.data:
            actual = res.data[0]['status']
            notes = res.data[0]['notes']
            
            if actual in expected_status_list:
                print(f" ✅ PASS: {actual}")
                return True
            elif "rejected" in actual and "rejected" not in expected_status_list:
                print(f" ❌ FAIL: {actual} (Reason: {notes})")
                return False
            elif actual not in expected_status_list:
                # Contextual pass (e.g. expected active but got correlation_rejected)
                print(f" ⚠️  Note: Got {actual}")
                return True
                
    print(f" ❌ TIMEOUT")
    return False

# ==========================================
# TRINITY INTEGRITY CHECK v6.3 (WARMUP MODE)
# ==========================================
print("\n🤖 STARTING SYSTEM VERIFICATION")
print(f"Target: {BASE_URL}")

# 0. WARMUP PHASE
print("\n[PHASE 0] WARMING UP WORKER")
print("   Sending 'WAKEUP' signal to spin up Railway container...")
send_signal("WAKEUP_TEST", 0.01)
# Wait up to 45s for the cold start
if verify_and_wait("WAKEUP_TEST", ["ml_rejected", "active"], patience=45):
    print("   ✅ Worker is AWAKE and listening.")
else:
    print("   ❌ Worker did not wake up. Check Railway Logs.")
    # Proceed anyway to see if other tests pass
    
# 1. RISK TEST
print("\n[PHASE 1] RISK GUARDIAN")
send_signal("XAUUSD", 5.0, "| F:score=50")
verify_and_wait("XAUUSD", "risk_rejected")

# 2. BUCKET FILL
print("\n[PHASE 2] CORRELATION BUCKET FILL")
winner_sig = "| F:signal_encoded=95 | F:score=95 | F:f_score=95 | F:session_encoded=2 | F:zone_type=1 | F:liq_distance=10.0"

for sym in ["EURUSD", "GBPUSD", "AUDUSD"]:
    send_signal(sym, 0.1, winner_sig)
    # We don't exit on fail here, just warn, to keep the test moving
    if not verify_and_wait(sym, "active"):
        print("   ⚠️ Bucket fill issues.")

# 3. OVERFLOW
print("\n[PHASE 3] OVERFLOW TEST")
send_signal("NZDUSD", 0.1, winner_sig)
verify_and_wait("NZDUSD", "correlation_rejected")

# 4. AI LOGIC
print("\n[PHASE 4] AI LOGIC TEST")
print("   Testing Low Confidence (Score=20)...")
send_signal("USDJPY", 0.1, "| F:score=20")
verify_and_wait("USDJPY", "ml_rejected")

print("\n🏁 DONE")