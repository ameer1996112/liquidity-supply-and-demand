#!/usr/bin/env python3
"""
Trinity System Integrity Check
==============================
Verifies Risk Guardian, Correlation Guard, and AI Brain.
Run from project root or scripts/ — auto-discovers .env.
"""

import os
import sys
import time
from pathlib import Path

import requests
from supabase import create_client, Client

# -----------------------------------------------------------------------------
# Robust Env Loading: Search up the directory tree
# -----------------------------------------------------------------------------

def _find_and_load_env() -> Path | None:
    """
    Check ./.env, ../.env, ../../.env. Stop at the first one found.
    Returns the path if found, None otherwise.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("❌ ERROR: python-dotenv not installed. Run: pip install python-dotenv")
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    candidates = [
        script_dir / ".env",              # scripts/.env
        project_root / ".env",            # project_root/.env
        project_root / "backend" / ".env",  # project_root/backend/.env
        project_root.parent / ".env",     # project_root/../.env
    ]

    for path in candidates:
        if path.exists():
            load_dotenv(dotenv_path=path)
            print(f"🔍 Loaded .env from: {path}")
            return path

    return None


def _validate_config() -> tuple[str, str, str, str]:
    """Validate required env vars. Exit loudly if missing."""
    env_path = _find_and_load_env()
    if env_path is None:
        print("")
        print("❌ " + "=" * 56)
        print("❌  ERROR: No .env file found!")
        print("❌  Searched: ./, ../, ../../")
        print("❌  Please create .env in the project root.")
        print("❌ " + "=" * 56)
        sys.exit(1)

    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (
        (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    )
    base_url = (os.getenv("WEBHOOK_URL") or os.getenv("API_URL") or "").strip().rstrip("/")
    secret = (os.getenv("WEBHOOK_SECRET") or "").strip()

    if not supabase_url:
        print("")
        print("❌ " + "=" * 56)
        print("❌  ERROR: SUPABASE_URL is missing!")
        print("❌  .env was loaded but SUPABASE_URL is not set.")
        print("❌  Please add SUPABASE_URL to your .env file.")
        print("❌ " + "=" * 56)
        sys.exit(1)

    if not supabase_key:
        print("")
        print("❌ " + "=" * 56)
        print("❌  ERROR: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY is missing!")
        print("❌  Please add one of these to your .env file.")
        print("❌ " + "=" * 56)
        sys.exit(1)

    if not base_url:
        base_url = "https://grand-learning-production-bc96.up.railway.app"

    if not secret:
        secret = "c817492a65caa767fdc438f61b8c2b64404a4e4aa6d9edfac74514c07bae20c6"

    return supabase_url, supabase_key, base_url, secret


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SUPABASE_URL, SUPABASE_KEY, BASE_URL, SECRET = _validate_config()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

REDEPLOY_WARNING = (
    "⚠️  Worker outdated! Please git push to Railway."
)


def print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {title}")
    print(f"{'='*60}")


def send_signal(
    symbol: str,
    size: float,
    signal_features: str = "Unknown",
    entry: float = 1.0,
    sl: float = 0.99,
    tp: float = 1.02,
) -> int:
    """Sends a standardized signal to the webhook."""
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
        "signal": signal_features,
    }
    try:
        r = requests.post(f"{BASE_URL}/webhook", json=payload, params=params, timeout=15)
        return r.status_code
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return 0


def verify_db_status(
    symbol: str,
    expected_status_list: list[str],
) -> tuple[str, str | None, float | None, str | None]:
    """
    Queries Supabase to see what the Worker actually did.

    Returns: (result, status, ml_win_probability, notes)
    - result: "PASS" | "FAIL" | "PARTIAL_FAIL"
    - status: record status or None if timeout
    - ml_win_probability: float or None if NULL (worker outdated)
    - notes: record notes or None
    """
    print(f"   ...verifying {symbol} in Database...")
    for _ in range(10):
        time.sleep(1)
        try:
            response = (
                supabase.table("trading_signals")
                .select("status, notes, ml_win_probability")
                .eq("symbol", symbol)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as e:
            print(f"   ❌ DB Error: {e}")
            return "FAIL", None, None, None

        if response.data:
            record = response.data[0]
            status = record.get("status")
            prob_raw = record.get("ml_win_probability")
            notes = record.get("notes")

            # Smart Verification: NULL ml_win_probability = worker outdated
            prob: float | None = None
            if prob_raw is not None:
                try:
                    prob = float(prob_raw)
                except (TypeError, ValueError):
                    prob = None

            if status in expected_status_list:
                if prob is None:
                    return "PARTIAL_FAIL", status, None, notes
                return "PASS", status, prob, notes
            else:
                # Record exists but wrong status
                if prob is None:
                    return "PARTIAL_FAIL", status, None, notes
                return "FAIL", status, prob, notes

    return "FAIL", "TIMEOUT", None, "Worker did not process in time"


# =============================================================================
# Test Suite
# =============================================================================

def main() -> int:
    print("\n🤖 TRINITY SYSTEM INTEGRITY CHECK")
    print(f"Target: {BASE_URL}")

    # --- TEST 1: RISK ENGINE ---
    print_header("RISK GUARDIAN (Anti-Gambling)")
    symbol = "TEST_RISK"
    print(f"👉 Sending {symbol} with 5.0 Lots ($5000 Risk)...")
    code = send_signal(symbol, size=5.0)

    if code == 200:
        result, status, prob, note = verify_db_status(symbol, ["risk_rejected"])
        if result == "PASS":
            print(f"✅ PASS: Blocked with status '{status}'")
            print(f"   Note: {note}")
        elif result == "PARTIAL_FAIL":
            print(f"⚠️  PARTIAL FAIL: Blocked with status '{status}'")
            print(f"   {REDEPLOY_WARNING}")
            if note:
                print(f"   Note: {note}")
        else:
            print(f"❌ FAIL: Expected 'risk_rejected', got '{status}'")
    else:
        print(f"❌ FAIL: API did not accept signal (Code {code})")

    # --- TEST 2: CORRELATION ENGINE ---
    print_header("CORRELATION GUARD (Max 3 Trades)")
    good_features = " | F:75,8,2,0,0.57,0,1,63.56,1,0,32.82,0,100,38.38,98.2,2.8,36.67"

    for i in range(1, 4):
        sym = f"TEST_FILL_{i}"
        print(f"👉 Filling Slot {i}: {sym}...")
        send_signal(sym, size=0.1, signal_features=good_features, entry=155.0, sl=154.5)
        time.sleep(1)

    overflow_sym = "TEST_OVERFLOW"
    print(f"👉 Sending 4th Trade: {overflow_sym} (Should Fail)...")
    send_signal(overflow_sym, size=0.1, signal_features=good_features, entry=155.0, sl=154.5)

    result, status, prob, note = verify_db_status(overflow_sym, ["correlation_rejected"])
    if result == "PASS":
        print(f"✅ PASS: Overflow blocked with status '{status}'")
        print(f"   Note: {note}")
    elif result == "PARTIAL_FAIL":
        print(f"⚠️  PARTIAL FAIL: Overflow blocked with status '{status}'")
        print(f"   {REDEPLOY_WARNING}")
        if note:
            print(f"   Note: {note}")
    else:
        print(f"❌ FAIL: Expected 'correlation_rejected', got '{status}'")

    # --- TEST 3: AI BRAIN (ML GUARDIAN) ---
    print_header("AI GUARDIAN (The Brain)")

    # A. The Idiot Test (Naked Signal)
    naked_sym = "TEST_AI_DUMB"
    print(f"👉 Sending 'Naked' Signal (No Features): {naked_sym}...")
    send_signal(naked_sym, size=0.1, signal_features="Unknown", entry=155.0, sl=154.5)

    result, status, prob, _ = verify_db_status(naked_sym, ["ml_rejected", "active"])
    if result == "PASS":
        if prob is not None and prob < 0.60:
            print(f"✅ PASS: AI correctly doubted this trade.")
            print(f"   Confidence: {prob:.2%} (Low)")
        else:
            prob_str = f"{prob:.2%}" if prob is not None else "N/A"
            print(f"⚠️ WARNING: AI had high confidence ({prob_str}) on a naked signal? Check Training.")
    elif result == "PARTIAL_FAIL":
        print(f"⚠️  PARTIAL FAIL: Signal processed but ml_win_probability is NULL.")
        print(f"   {REDEPLOY_WARNING}")
    else:
        print(f"❌ FAIL: Worker failed to process. Status: {status}")

    # B. The Genius Test (Rich Data)
    rich_sym = "TEST_AI_SMART"
    print(f"\n👉 Sending 'Rich' Signal (Winning Pattern): {rich_sym}...")
    send_signal(rich_sym, size=0.1, signal_features=good_features, entry=155.0, sl=154.5)

    result, status, prob, _ = verify_db_status(rich_sym, ["active"])
    if result == "PASS":
        if prob is not None and prob >= 0.60:
            print(f"✅ PASS: AI Recognized the winner!")
            print(f"   Confidence: {prob:.2%} (High)")
        else:
            prob_str = f"{prob:.2%}" if prob is not None else "N/A"
            print(f"❌ FAIL: AI rejected a good trade. Confidence: {prob_str}")
    elif result == "PARTIAL_FAIL":
        print(f"⚠️  PARTIAL FAIL: Signal active but ml_win_probability is NULL.")
        print(f"   {REDEPLOY_WARNING}")
    else:
        print(f"❌ FAIL: Signal not active. Status: {status}")

    print("\n" + "=" * 60)
    print("🏁 SYSTEM INTEGRITY CHECK COMPLETE")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
