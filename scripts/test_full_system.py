#!/usr/bin/env python3
"""
Full System E2E Test — Trading Bot Pipeline Verification
========================================================
Injects two webhooks (Winner + Loser), waits for Worker/AI processing,
then verifies Supabase data. Use after reset_system.py for smoke testing.

Usage:
    python scripts/test_full_system.py

Requirements:
    - .env: WEBHOOK_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    - Optional: WEBHOOK_SECRET (if API requires auth)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Load .env from project root or backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for env_file in [PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"]:
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file)
            break
        except ImportError:
            pass

# ANSI / Rich-style output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

TEST_SYMBOL = "TESTUSD"
VERIFY_ATTEMPTS = 5
VERIFY_INTERVAL_SEC = 2


def _log(msg: str, style: str = "") -> None:
    print(f"{style}{msg}{RESET}")


def _log_pass(msg: str) -> None:
    _log(f"  ✅ {msg}", GREEN)


def _log_fail(msg: str) -> None:
    _log(f"  ❌ {msg}", RED)


def _log_warn(msg: str) -> None:
    _log(f"  ⚠️  {msg}", YELLOW)


def _log_info(msg: str) -> None:
    _log(f"  ℹ️  {msg}", CYAN)


# ═══════════════════════════════════════════════════════════
# Part 1: Configuration
# ═══════════════════════════════════════════════════════════


def load_config() -> tuple[str, str, str, str | None]:
    """Load WEBHOOK_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, WEBHOOK_SECRET."""
    webhook_url = (os.getenv("WEBHOOK_URL") or os.getenv("API_URL") or "").strip().rstrip("/")
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (
        (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    )
    webhook_secret = (os.getenv("WEBHOOK_SECRET") or "").strip() or None

    if not webhook_url:
        _log_fail("WEBHOOK_URL (or API_URL) not set in .env")
        sys.exit(1)
    if not supabase_url or not supabase_key:
        _log_fail("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    return webhook_url, supabase_url, supabase_key, webhook_secret


def init_supabase(url: str, key: str):
    """Initialize Supabase client."""
    try:
        from supabase import create_client

        return create_client(url, key)
    except ImportError as e:
        _log_fail(f"supabase package not installed: {e}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════
# Part 2: Injection (Stimulus)
# ═══════════════════════════════════════════════════════════


# Test Case A: The Perfect Trade — high score, valid structure
PAYLOAD_WINNER = {
    "symbol": TEST_SYMBOL,
    "side": "BUY",
    "entry": 100.0,
    "sl": 95.0,
    "tp": 110.0,
    "size": 0.01,
    "zone_id": 88881,
    "zone_type": "demand",
    "entry_model": "FLIP",
    "liq_swept": True,
    "target_swept": True,
    "caused_sweep": True,
    "is_accuracy": True,
    "score": 95,
    "freshness": 1,
    "session": 2,
    "trend": 1,
    "departure_strength": 85,
    "return_strength": 88,
    "base_quality": 82,
    "rsi": 58,
}

# Test Case B: The Bad Trade — low score, bad structure (should be AI rejected)
PAYLOAD_LOSER = {
    "symbol": TEST_SYMBOL,
    "side": "SELL",
    "entry": 100.0,
    "sl": 105.0,
    "tp": 90.0,
    "size": 0.01,
    "zone_id": 88882,
    "zone_type": "supply",
    "entry_model": "BREAK_CANDLE",
    "liq_swept": False,
    "target_swept": False,
    "caused_sweep": False,
    "is_accuracy": False,
    "score": 10,
    "freshness": 0,
    "session": 0,
    "departure_strength": 5,
    "return_strength": 10,
    "base_quality": 15,
}


def send_webhook(webhook_url: str, payload: dict, webhook_secret: str | None) -> tuple[bool, int, str]:
    """
    POST payload to /webhook. Returns (success, status_code, message).
    """
    try:
        import requests
    except ImportError:
        return False, 0, "requests package not installed"

    url = f"{webhook_url}/webhook"
    headers = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        return resp.status_code == 200, resp.status_code, resp.text
    except Exception as e:
        return False, 0, str(e)


def inject_signals(webhook_url: str, webhook_secret: str | None) -> bool:
    """Send both webhooks. Returns True iff both return 200."""
    _log(f"\n{BOLD}Part 2: Injection (Stimulus){RESET}", CYAN)
    _log_info(f"Sending Winner (BUY, score=95) to {webhook_url}/webhook")
    ok_a, code_a, msg_a = send_webhook(webhook_url, PAYLOAD_WINNER, webhook_secret)
    if not ok_a:
        _log_fail(f"Test A (Winner): API returned {code_a} — {msg_a[:200]}")
        return False
    _log_pass(f"Test A (Winner): API 200 OK")

    _log_info(f"Sending Loser (SELL, score=10) to {webhook_url}/webhook")
    ok_b, code_b, msg_b = send_webhook(webhook_url, PAYLOAD_LOSER, webhook_secret)
    if not ok_b:
        _log_fail(f"Test B (Loser): API returned {code_b} — {msg_b[:200]}")
        return False
    _log_pass(f"Test B (Loser): API 200 OK")

    return True


# ═══════════════════════════════════════════════════════════
# Part 3: Verification (Assertion)
# ═══════════════════════════════════════════════════════════


def fetch_test_signals(supabase) -> list[dict]:
    """Query trading_signals for TESTUSD, ordered by created_at DESC."""
    try:
        result = (
            supabase.table("trading_signals")
            .select("*")
            .eq("symbol", TEST_SYMBOL)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def verify_signals(supabase) -> dict:
    """
    Poll Supabase up to VERIFY_ATTEMPTS times, 2s apart.
    Returns dict: api_ok, worker_ok, ai_logic_ok, rows, errors
    """
    _log(f"\n{BOLD}Part 3: Verification (Assertion){RESET}", CYAN)
    _log_info(f"Waiting up to {VERIFY_ATTEMPTS * VERIFY_INTERVAL_SEC}s for Worker to process...")

    rows: list[dict] = []
    for attempt in range(1, VERIFY_ATTEMPTS + 1):
        time.sleep(VERIFY_INTERVAL_SEC)
        rows = fetch_test_signals(supabase)
        if rows:
            _log_info(f"Attempt {attempt}/{VERIFY_ATTEMPTS}: Found {len(rows)} row(s)")
            break
        _log_info(f"Attempt {attempt}/{VERIFY_ATTEMPTS}: No rows yet")

    result = {"api_ok": True, "worker_ok": False, "ai_logic_ok": False, "rows": rows, "errors": []}

    if not rows:
        result["worker_ok"] = False
        result["errors"].append("Worker did not process data — no TESTUSD signals in DB")
        return result

    result["worker_ok"] = True

    # Map zone_id -> row for lookup
    by_zone = {r.get("zone_id"): r for r in rows}

    # Test A: zone_id 88881 (Winner) — expect active or executed (or filtered if logic filters)
    row_winner = by_zone.get(88881)
    if not row_winner:
        result["ai_logic_ok"] = False
        result["errors"].append("Winner signal (zone_id=88881) not found")
        return result

    status_winner = (row_winner.get("status") or "").lower()
    valid_winner = status_winner in ("active", "executed", "filtered")
    if not valid_winner:
        result["ai_logic_ok"] = False
        result["errors"].append(
            f"Winner expected status active/executed/filtered, got '{status_winner}'"
        )
        return result

    # Test B: zone_id 88882 (Loser) — expect ai_rejected
    row_loser = by_zone.get(88882)
    if not row_loser:
        result["ai_logic_ok"] = False
        result["errors"].append("Loser signal (zone_id=88882) not found")
        return result

    status_loser = (row_loser.get("status") or "").lower()
    if status_loser != "ai_rejected":
        result["ai_logic_ok"] = False
        result["errors"].append(
            f"AI Logic: Bad trade should be ai_rejected, got '{status_loser}'"
        )
        return result

    result["ai_logic_ok"] = True
    return result


def print_report(inject_ok: bool, verify: dict) -> None:
    """Print Pass/Fail report for each component."""
    _log(f"\n{BOLD}══════════════════════════════════════{RESET}", CYAN)
    _log(f"{BOLD}  E2E Test Report{RESET}", CYAN)
    _log(f"{BOLD}══════════════════════════════════════{RESET}", CYAN)

    api_status = f"{GREEN}✅ PASS{RESET}" if inject_ok else f"{RED}❌ FAIL{RESET}"
    worker_status = f"{GREEN}✅ PASS{RESET}" if verify["worker_ok"] else f"{RED}❌ FAIL{RESET}"
    ai_status = f"{GREEN}✅ PASS{RESET}" if verify["ai_logic_ok"] else f"{RED}❌ FAIL{RESET}"

    _log(f"  API (200 OK):        {api_status}")
    _log(f"  Worker (DB write):   {worker_status}")
    _log(f"  AI Logic (reject):   {ai_status}")

    for err in verify.get("errors", []):
        _log_fail(err)

    _log("")


# ═══════════════════════════════════════════════════════════
# Part 4: Cleanup Instructions
# ═══════════════════════════════════════════════════════════


def print_cleanup_sql() -> None:
    _log(f"{BOLD}Part 4: Cleanup{RESET}", CYAN)
    _log_info("To remove test data, run in Supabase SQL Editor:")
    _log("")
    _log(f"  DELETE FROM trading_signals WHERE symbol = '{TEST_SYMBOL}';", DIM)
    _log("")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════


def main() -> int:
    _log("")
    _log(f"{BOLD}Full System E2E Test — Trading Bot{RESET}", CYAN)
    _log("Inject → Wait → Verify", DIM)
    _log("")

    webhook_url, supabase_url, supabase_key, webhook_secret = load_config()
    supabase = init_supabase(supabase_url, supabase_key)

    inject_ok = inject_signals(webhook_url, webhook_secret)
    if not inject_ok:
        print_report(inject_ok, {"worker_ok": False, "ai_logic_ok": False, "rows": [], "errors": ["API injection failed"]})
        print_cleanup_sql()
        return 1

    verify = verify_signals(supabase)
    print_report(inject_ok, verify)
    print_cleanup_sql()

    if inject_ok and verify["worker_ok"] and verify["ai_logic_ok"]:
        _log(f"{BOLD}✅ All E2E checks passed. Pipeline is healthy.{RESET}", GREEN)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
