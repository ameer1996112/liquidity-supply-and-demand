"""
System Integrity Verifier v6.1
==============================

Tests the entire trading system end-to-end:
1. RISK GUARD - Oversized position rejection
2. CORRELATION GUARD - Bucket overflow rejection
3. AI GUARD - Low confidence rejection

Uses the "Super String" format (F:key=value) expected by worker v6.1.
"""

import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# --- CONFIGURATION & SETUP ---
# Auto-discover .env: backend/ first (where .env lives), then root, scripts/
_base = Path(__file__).resolve().parent.parent
env_path = None
for p in [_base / "backend" / ".env", _base / ".env", _base / "scripts" / ".env"]:
    if p.exists():
        load_dotenv(dotenv_path=p)
        env_path = p
        break

if env_path:
    print(f"Loaded .env from: {env_path}")
else:
    print("   No .env found (backend/, root, scripts/).")

# CONFIG
BASE_URL = os.getenv(
    "WEBHOOK_URL",
    os.getenv("API_URL", "https://grand-learning-production-bc96.up.railway.app")
).strip().rstrip("/")
SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "c817492a65caa767fdc438f61b8c2b64404a4e4aa6d9edfac74514c07bae20c6"
)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("\nCRITICAL ERROR: Missing Supabase Credentials.")
    sys.exit(1)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Failed to initialize Supabase client: {e}")
    sys.exit(1)


# --- HELPER FUNCTIONS ---

def send_signal(symbol, size, signal_str="", entry=1.0, sl=0.99, tp=1.02):
    """Send a trade signal to the webhook."""
    print(f"   Sending {symbol} ({size} lots)...")
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
        "time": "2026-01-27T09:00:00Z",
        "exchange": "OANDA",
        "signal": signal_str
    }
    try:
        resp = requests.post(f"{BASE_URL}/webhook", json=payload, params=params, timeout=5)
        if resp.status_code != 200:
            print(f"      Webhook Error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"      Connection Error: {e}")


def verify_status(symbol, expected_status):
    """Verify trade status in database."""
    print(f"   ...verifying {symbol} in DB...")
    for _ in range(8):  # Wait up to 8 seconds
        time.sleep(1)
        res = supabase.table("trading_signals").select(
            "status, notes, ml_win_probability"
        ).eq("symbol", symbol).order("created_at", desc=True).limit(1).execute()

        if res.data:
            record = res.data[0]
            actual = record['status']
            notes = record.get('notes', '')
            prob = record.get('ml_win_probability')

            # Fallback: Check if probability is in notes
            if prob is None and notes:
                match = re.search(r"(\d+\.\d+)%", notes)
                if match:
                    prob = float(match.group(1)) / 100.0

            if actual == expected_status:
                print(f"   PASS: {symbol} -> {actual}")
                return True, actual, prob, notes
            elif "rejected" in actual and "rejected" not in expected_status:
                print(f"   FAIL: {symbol} -> {actual} (Reason: {notes})")
                return False, actual, prob, notes

    print(f"   FAIL: {symbol} -> TIMEOUT (Worker did not process)")
    return False, "TIMEOUT", 0, "Worker did not process in time"


# ==========================================
# STARTING THE TEST SUITE
# ==========================================

print("\n" + "=" * 50)
print("TRINITY SYSTEM INTEGRITY CHECK v6.1")
print("=" * 50)
print(f"Target: {BASE_URL}")

# --- TEST 1: RISK ENGINE ---
print("\n[TEST 1] RISK GUARDIAN")
print("Sending XAUUSD with 5.0 Lots (Should be REJECTED)...")
send_signal("XAUUSD", size=5.0, entry=2000.0, sl=1990.0)

success, status, _, _ = verify_status("XAUUSD", "risk_rejected")
if success:
    print(f"   Result: Blocked with status '{status}'")
else:
    print(f"   Result: Expected 'risk_rejected', got '{status}'")

# --- TEST 2: CORRELATION GUARD ---
print("\n[TEST 2] CORRELATION GUARD")

# The "Super String" format with winning features
# Score=95 teaches the AI this is a high-probability trade
winning_features = "| F:signal_encoded=95 | F:score=95 | F:f_score=95 | F:f_signal_encoded=95 | F:session_encoded=2 | F:zone_type=1 | F:liq_distance=10.0 | F:source_encoded=2"

print("Filling Slot 1: EURUSD (0.1 lots)...")
send_signal("EURUSD", size=0.1, signal_str=winning_features, entry=1.1000, sl=1.0950)
time.sleep(1.5)

print("Filling Slot 2: GBPUSD (0.1 lots)...")
send_signal("GBPUSD", size=0.1, signal_str=winning_features, entry=1.2500, sl=1.2450)
time.sleep(1.5)

print("Filling Slot 3: AUDUSD (0.1 lots)...")
send_signal("AUDUSD", size=0.1, signal_str=winning_features, entry=0.6500, sl=0.6450)
time.sleep(1.5)

print("Sending 4th Trade: NZDUSD (Should Fail due to limit)...")
send_signal("NZDUSD", size=0.1, signal_str=winning_features, entry=0.6000, sl=0.5950)

success, status, _, note = verify_status("NZDUSD", "correlation_rejected")
if success:
    print(f"   Result: Overflow blocked with status '{status}'")
else:
    print(f"   Result: Expected 'correlation_rejected', got '{status}'")
    print(f"   Reason: {note}")

# --- TEST 3: AI GUARDIAN ---
print("\n[TEST 3] AI GUARDIAN (Low Confidence)")

# Weak signal with score=20 -> Should be rejected
weak_features = "| F:score=20 | F:signal_encoded=20"
print("Sending USDJPY with weak signal (Score=20)...")
send_signal("USDJPY", size=0.1, signal_str=weak_features, entry=155.00, sl=154.50)

success, status, prob, note = verify_status("USDJPY", "ml_rejected")
if success:
    prob_str = f"{prob:.2%}" if prob else "N/A"
    print(f"   Result: AI rejected trade (Confidence: {prob_str})")
else:
    print(f"   Result: Expected 'ml_rejected', got '{status}'")

# --- TEST 4: AI GUARDIAN (High Confidence) ---
print("\n[TEST 4] AI GUARDIAN (High Confidence)")

# Note: This may get correlation_rejected if slots are still full
print("Sending GBPCAD with strong signal (Score=95)...")
send_signal("GBPCAD", size=0.1, signal_str=winning_features, entry=1.7000, sl=1.6950)

success, status, prob, note = verify_status("GBPCAD", "active")
if success:
    prob_str = f"{prob:.2%}" if prob else "N/A"
    print(f"   Result: AI approved trade (Confidence: {prob_str})")
elif status == "correlation_rejected":
    print(f"   Result: Bucket still full (expected behavior)")
else:
    print(f"   Result: Expected 'active', got '{status}'")
    print(f"   Reason: {note}")

print("\n" + "=" * 50)
print("INTEGRITY CHECK COMPLETE")
print("=" * 50)
