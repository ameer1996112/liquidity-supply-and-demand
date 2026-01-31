import requests
import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# --- CONFIGURATION & SETUP ---
# Auto-discover .env: scripts/, root, backend/
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
env_path = None
for p in [current_dir / ".env", project_root / ".env", project_root / "backend" / ".env"]:
    if p.exists():
        load_dotenv(dotenv_path=p)
        env_path = p
        break
if env_path:
    print(f"🔍 Loaded .env from: {env_path}")
else:
    print("   ⚠️  No .env found (scripts/, root, backend/). Using system vars.")

BASE_URL = os.getenv("WEBHOOK_URL", os.getenv("API_URL", "https://grand-learning-production-bc96.up.railway.app")).strip().rstrip("/")
SECRET = os.getenv("WEBHOOK_SECRET", "c817492a65caa767fdc438f61b8c2b64404a4e4aa6d9edfac74514c07bae20c6")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("\n❌ CRITICAL ERROR: Missing Supabase Credentials.")
    sys.exit(1)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"❌ Failed to initialize Supabase client: {e}")
    sys.exit(1)

# --- HELPER FUNCTIONS ---
def send_signal(symbol, size, signal_features="Unknown", entry=1.0, sl=0.99, tp=1.02):
    params = {"secret": SECRET}
    payload = {
        "passphrase": SECRET,
        "symbol": symbol,
        "side": "buy",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "size": size,
        "run_mode": "PAPER",
        "time": "2026-01-27T15:00:00Z",
        "exchange": "OANDA",
        "signal": signal_features
    }
    try:
        requests.post(f"{BASE_URL}/webhook", json=payload, params=params)
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")

def verify_db_status(symbol, expected_status_list):
    print(f"   ...verifying {symbol} in Database...")
    for _ in range(12): # Wait up to 12s
        time.sleep(1)
        response = supabase.table("trading_signals").select("status, notes, ml_win_probability").eq("symbol", symbol).order("created_at", desc=True).limit(1).execute()
        if response.data:
            record = response.data[0]
            status = record['status']
            prob = record.get('ml_win_probability', 0)
            
            if status in expected_status_list:
                return True, status, prob, record['notes']
            
            # Debugging Help
            if status == 'risk_rejected':
                 return False, status, 0, f"Risk Rejection: {record.get('notes')}"
            if status == 'pine_rejected':
                 return False, status, 0, f"Pine Rejection: {record.get('notes')}"
                 
    return False, "TIMEOUT", 0, "Worker did not process in time"

# ==========================================
# 🚀 STARTING THE TEST SUITE
# ==========================================

print("\n🤖 TRINITY SYSTEM INTEGRITY CHECK (BUFFERED MATH MODE)")
print(f"Target: {BASE_URL}")

# --- TEST 1: RISK ENGINE ---
print("\n🧪 TESTING: RISK GUARDIAN")
print("👉 Sending XAUUSD with 5.0 Lots (Should be REJECTED)...")
send_signal("XAUUSD", size=5.0, entry=2000.0, sl=1990.0) 

success, status, _, _ = verify_db_status("XAUUSD", ["risk_rejected"])
if success: 
    print(f"✅ PASS: Blocked with status '{status}'")
else: 
    print(f"❌ FAIL: Expected 'risk_rejected', got '{status}'")

# --- TEST 2: CORRELATION ENGINE ---
print("\n🧪 TESTING: CORRELATION GUARD")
good_features = " | F:75,8,2,0,0.57,0,1,63.56,1,0,32.82,0,100,38.38,98.2,2.8,36.67"

# NOTE: Using 0.19 lots ($95 risk) to safely clear the $100 limit
print("👉 Filling Slot 1: EURUSD (0.19 lots)...")
send_signal("EURUSD", size=0.19, signal_features=good_features, entry=1.1000, sl=1.0950)
time.sleep(1)

print("👉 Filling Slot 2: GBPUSD (0.19 lots)...")
send_signal("GBPUSD", size=0.19, signal_features=good_features, entry=1.2500, sl=1.2450)
time.sleep(1)

print("👉 Filling Slot 3: AUDUSD (0.19 lots)...")
send_signal("AUDUSD", size=0.19, signal_features=good_features, entry=0.6500, sl=0.6450)
time.sleep(1)

print("👉 Sending 4th Trade: NZDUSD (Should Fail due to limit)...")
send_signal("NZDUSD", size=0.19, signal_features=good_features, entry=0.6000, sl=0.5950)

success, status, _, note = verify_db_status("NZDUSD", ["correlation_rejected"])
if success: 
    print(f"✅ PASS: Overflow blocked with status '{status}'")
else: 
    print(f"❌ FAIL: Expected 'correlation_rejected', got '{status}'")
    print(f"   Reason: {note}")

# --- TEST 3: AI BRAIN ---
print("\n🧪 TESTING: AI GUARDIAN")

# Naked Signal (GBPCAD) -> 0.19 Lots
print("👉 Sending 'Naked' GBPCAD...")
send_signal("GBPCAD", size=0.19, signal_features="Unknown", entry=1.7000, sl=1.6950)
success, status, prob, _ = verify_db_status("GBPCAD", ["ml_rejected", "active"])

if success:
    if prob is None:
         print(f"⚠️ PARTIAL FAIL: Worker outdated (NULL probability). Push to Railway!")
    elif prob < 0.60:
        print(f"✅ PASS: AI doubted trade (Conf: {prob:.2%})")
    else:
        print(f"⚠️ WARNING: AI had high confidence ({prob:.2%}) on naked signal.")
else:
    print(f"❌ FAIL: Expected processed, got '{status}'")

# Rich Signal (USDJPY) -> 0.29 Lots (JPY needs slightly more size, using 0.29 for buffer)
print("\n👉 Sending 'Rich' USDJPY (0.29 lots)...")
send_signal("USDJPY", size=0.29, signal_features=good_features, entry=155.00, sl=154.50)
success, status, prob, _ = verify_db_status("USDJPY", ["active"])

if success:
    if prob is None:
         print(f"⚠️ PARTIAL FAIL: Worker outdated (NULL probability). Push to Railway!")
    elif prob >= 0.60:
        print(f"✅ PASS: AI Liked trade (Conf: {prob:.2%})")
    else:
        print(f"❌ FAIL: AI rejected good trade (Conf: {prob:.2%})")

print("\n🏁 DONE")