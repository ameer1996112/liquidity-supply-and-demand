#!/usr/bin/env python3
"""
Max Open Positions Limit Test (v2 - Synchronous)
=================================================
Tests the "Max Open Positions" rule (Limit: 3) in the Trinity Engine.

Sends "Perfect Signals" designed to bypass PineGuardian entry checks
(correct lot size of 0.2 for $100 risk with 50-pip stop).

Attack Sequence:
1. TEST_FILL_1 -> wait_for_active() -> Expect: ACTIVE
2. TEST_FILL_2 -> wait_for_active() -> Expect: ACTIVE
3. TEST_FILL_3 -> wait_for_active() -> Expect: ACTIVE
4. TEST_OVERFLOW -> Expect: correlation_rejected (Max positions reached)

v2 Changes:
- Synchronous polling: wait for each signal to become 'active' before next
- Handles None types in verification step
- Eliminates race conditions between signal sending and worker processing

Usage:
    python scripts/test_correlation_limits.py

Author: QA Automation Engineer
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
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

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Test Configuration
TEST_SYMBOLS = ["TEST_FILL_1", "TEST_FILL_2", "TEST_FILL_3", "TEST_OVERFLOW"]
FILL_SYMBOLS = ["TEST_FILL_1", "TEST_FILL_2", "TEST_FILL_3"]
PERFECT_SIZE = 0.2       # Critical: 0.2 lots for $100 risk
ENTRY_PRICE = 1.0850     # Entry price
SL_PRICE = 1.0800        # 50-pip stop loss
TP_PRICE = 1.0950        # Take profit (100 pips)

# Synchronous polling configuration
WAIT_FOR_ACTIVE_ATTEMPTS = 10
WAIT_FOR_ACTIVE_INTERVAL = 1  # seconds

# Final verification configuration
VERIFY_ATTEMPTS = 10
VERIFY_INTERVAL_SEC = 2


def log(msg: str, style: str = "") -> None:
    print(f"{style}{msg}{RESET}")


def log_pass(msg: str) -> None:
    log(f"  [PASS] {msg}", GREEN)


def log_fail(msg: str) -> None:
    log(f"  [FAIL] {msg}", RED)


def log_info(msg: str) -> None:
    log(f"  [INFO] {msg}", CYAN)


def log_warn(msg: str) -> None:
    log(f"  [WARN] {msg}", YELLOW)


def print_header() -> None:
    print(f"""
{CYAN}{BOLD}+==================================================================+
|     MAX OPEN POSITIONS LIMIT TEST (v2 - Synchronous)             |
|     Trinity Engine Correlation Guard - QA Validation             |
+==================================================================+{RESET}

{YELLOW}Configuration:{RESET}
  Max Open Positions: 3
  Perfect Lot Size:   {PERFECT_SIZE}
  Entry Price:        {ENTRY_PRICE}
  Stop Loss:          {SL_PRICE} (50-pip stop)

{YELLOW}Synchronous Attack Sequence:{RESET}
  [1] TEST_FILL_1   -> wait_for_active() -> Expect: ACTIVE
  [2] TEST_FILL_2   -> wait_for_active() -> Expect: ACTIVE
  [3] TEST_FILL_3   -> wait_for_active() -> Expect: ACTIVE
  [4] TEST_OVERFLOW -> Expect: correlation_rejected
""")


def load_config() -> tuple[str, str, str, str | None]:
    """Load configuration from environment."""
    webhook_url = (os.getenv("WEBHOOK_URL") or os.getenv("API_URL") or "").strip().rstrip("/")
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
    ).strip()
    webhook_secret = (os.getenv("WEBHOOK_SECRET") or "").strip() or None

    if not webhook_url:
        log_fail("WEBHOOK_URL not set in .env")
        sys.exit(1)
    if not supabase_url or not supabase_key:
        log_fail("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    log_info(f"Webhook URL: {webhook_url}")
    log_info(f"Supabase URL: {supabase_url[:40]}...")
    return webhook_url, supabase_url, supabase_key, webhook_secret


def init_supabase(url: str, key: str):
    """Initialize Supabase client."""
    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError as e:
        log_fail(f"supabase package not installed: {e}")
        sys.exit(1)


def create_perfect_signal(symbol: str, index: int) -> dict:
    """
    Create a "Perfect Signal" payload designed to bypass PineGuardian checks.

    Key parameters:
    - Size: 0.2 lots (exactly what system expects for $100 risk)
    - Entry/SL: Creates valid 50-pip stop
    - All quality flags set to pass validation
    """
    return {
        "symbol": symbol,
        "side": "buy",
        "entry": ENTRY_PRICE,
        "sl": SL_PRICE,
        "tp": TP_PRICE,
        "size": PERFECT_SIZE,  # Critical: 0.2 lots
        "zone_id": int(datetime.now().timestamp() * 1000) + index,
        "zone_type": "demand",
        "entry_model": "FLIP",
        "liq_swept": True,
        "target_swept": True,
        "caused_sweep": True,
        "is_accuracy": True,
        "score": 90.0,
        "freshness": 1,
        "session": 2,
        "trend": 1,
        "departure_strength": 85.0,
        "return_strength": 88.0,
        "base_quality": 82.0,
        "rsi": 55.0,
        "run_mode": "TEST",
        "run_id": "max-positions-test",
    }


def send_signal(webhook_url: str, webhook_secret: str | None, payload: dict, label: str) -> bool:
    """Send a webhook signal and return success status."""
    try:
        import requests
    except ImportError:
        log_fail("requests package not installed")
        return False

    url = f"{webhook_url}/webhook"
    headers = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret

    log_info(f"Sending: {label}")
    log(f"      Symbol: {payload['symbol']} | Side: {payload['side'].upper()}", DIM)
    log(f"      Entry: {payload['entry']} | SL: {payload['sl']} | Size: {payload['size']}", DIM)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            log_pass(f"HTTP 200 - Signal queued")
            return True
        else:
            log_fail(f"HTTP {resp.status_code} - {resp.text[:100]}")
            return False
    except Exception as e:
        log_fail(f"Request failed: {e}")
        return False


def cleanup_test_signals(supabase) -> None:
    """Delete any existing test signals before running the test."""
    log_info("Cleaning up previous test signals...")
    try:
        for symbol in TEST_SYMBOLS:
            supabase.table("trading_signals").delete().eq("symbol", symbol).execute()
        log_pass("Cleanup complete")
    except Exception as e:
        log_warn(f"Cleanup warning: {e}")


def query_signal_status(supabase, symbol: str) -> dict | None:
    """Query a single signal's status from Supabase."""
    try:
        result = (
            supabase.table("trading_signals")
            .select("*")
            .eq("symbol", symbol)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        log_warn(f"Query error: {e}")
        return None


def wait_for_active(supabase, symbol: str) -> bool:
    """
    Synchronously wait for a signal to become 'active' in Supabase.

    Polls up to WAIT_FOR_ACTIVE_ATTEMPTS times with WAIT_FOR_ACTIVE_INTERVAL delay.

    Args:
        supabase: Supabase client
        symbol: Symbol to wait for

    Returns:
        True if signal became active, False if timeout

    Raises:
        RuntimeError: If signal is rejected or timeout occurs
    """
    log_info(f"Waiting for {symbol} to become active...")

    for attempt in range(1, WAIT_FOR_ACTIVE_ATTEMPTS + 1):
        time.sleep(WAIT_FOR_ACTIVE_INTERVAL)

        signal = query_signal_status(supabase, symbol)

        if signal:
            status = (signal.get("status") or "").lower()

            if status == "active":
                log_pass(f"{symbol} is now ACTIVE (attempt {attempt}/{WAIT_FOR_ACTIVE_ATTEMPTS})")
                return True

            # Check for rejection - signal was processed but not accepted
            if status and status not in ("pending", "active"):
                notes = signal.get("notes") or ""
                raise RuntimeError(
                    f"{symbol} was rejected with status '{status}': {notes}"
                )

            log(f"      Attempt {attempt}/{WAIT_FOR_ACTIVE_ATTEMPTS}: status='{status}', waiting...", DIM)
        else:
            log(f"      Attempt {attempt}/{WAIT_FOR_ACTIVE_ATTEMPTS}: signal not yet in DB, waiting...", DIM)

    # Timeout
    raise RuntimeError(
        f"Timeout waiting for {symbol} to become active after "
        f"{WAIT_FOR_ACTIVE_ATTEMPTS * WAIT_FOR_ACTIVE_INTERVAL}s"
    )


def execute_attack_sequence(supabase, webhook_url: str, webhook_secret: str | None) -> bool:
    """
    Execute the synchronous attack sequence:
    1. Send TEST_FILL_1 -> wait_for_active('TEST_FILL_1')
    2. Send TEST_FILL_2 -> wait_for_active('TEST_FILL_2')
    3. Send TEST_FILL_3 -> wait_for_active('TEST_FILL_3')
    4. Send TEST_OVERFLOW (no wait - we verify rejection separately)
    """
    log(f"\n{BOLD}=== EXECUTING SYNCHRONOUS ATTACK SEQUENCE ==={RESET}", MAGENTA)

    try:
        # Send FILL signals with synchronous wait
        for i, symbol in enumerate(FILL_SYMBOLS, 1):
            log(f"\n{CYAN}[Step {i}/4] {symbol}{RESET}")

            payload = create_perfect_signal(symbol, i)
            success = send_signal(webhook_url, webhook_secret, payload, f"Perfect Signal #{i}")

            if not success:
                log_fail(f"Failed to send {symbol}")
                return False

            # Wait for this signal to become active before sending next
            wait_for_active(supabase, symbol)

        # Send OVERFLOW signal (step 4)
        log(f"\n{CYAN}[Step 4/4] TEST_OVERFLOW{RESET}")
        payload = create_perfect_signal("TEST_OVERFLOW", 4)
        success = send_signal(webhook_url, webhook_secret, payload, "Perfect Signal #4 (OVERFLOW)")

        if not success:
            log_fail("Failed to send TEST_OVERFLOW")
            return False

        log_pass("All signals sent successfully")
        return True

    except RuntimeError as e:
        log_fail(f"Attack sequence failed: {e}")
        return False


def verify_overflow_rejection(supabase) -> dict:
    """
    Wait for TEST_OVERFLOW to be processed and verify it was rejected.
    Returns dict with test results.
    """
    log(f"\n{BOLD}=== VERIFICATION PHASE ==={RESET}", MAGENTA)
    log_info(f"Waiting for TEST_OVERFLOW to be processed...")
    log_info(f"Will check every {VERIFY_INTERVAL_SEC}s for up to {VERIFY_ATTEMPTS * VERIFY_INTERVAL_SEC}s")

    results = {
        "fill_1_active": False,
        "fill_2_active": False,
        "fill_3_active": False,
        "overflow_rejected": False,
        "overflow_status": None,
        "overflow_notes": None,
    }

    # Poll until TEST_OVERFLOW has a final status
    for attempt in range(1, VERIFY_ATTEMPTS + 1):
        time.sleep(VERIFY_INTERVAL_SEC)

        overflow = query_signal_status(supabase, "TEST_OVERFLOW")
        if overflow:
            status = (overflow.get("status") or "").lower()
            # Check if it's been processed (not pending)
            if status and status != "pending":
                results["overflow_status"] = status
                results["overflow_notes"] = overflow.get("notes") or ""
                log_info(f"Attempt {attempt}: TEST_OVERFLOW status = '{status}'")
                break

        log_info(f"Attempt {attempt}/{VERIFY_ATTEMPTS}: Waiting for processing...")

    # Now check all signals
    log(f"\n{CYAN}Checking final statuses:{RESET}")

    for symbol in FILL_SYMBOLS:
        sig = query_signal_status(supabase, symbol)
        if sig:
            status = (sig.get("status") or "").lower()
            key = symbol.lower().replace("test_", "") + "_active"
            results[key] = status == "active"
            status_display = f"{GREEN}{status}{RESET}" if status == "active" else f"{YELLOW}{status}{RESET}"
            log(f"  {symbol}: {status_display}")
        else:
            log(f"  {symbol}: {RED}NOT FOUND{RESET}")

    # Final overflow status
    overflow = query_signal_status(supabase, "TEST_OVERFLOW")
    if overflow:
        status = (overflow.get("status") or "").lower()
        notes = overflow.get("notes") or ""  # Handle None
        results["overflow_status"] = status
        results["overflow_notes"] = notes

        is_rejected = status == "correlation_rejected"
        # Safely check notes (already handled None above)
        has_max_note = "max" in notes.lower() and "position" in notes.lower()
        results["overflow_rejected"] = is_rejected and has_max_note

        status_display = f"{GREEN}{status}{RESET}" if is_rejected else f"{RED}{status}{RESET}"
        log(f"  TEST_OVERFLOW: {status_display}")
        log(f"  Notes: {notes}", DIM)
    else:
        log(f"  TEST_OVERFLOW: {RED}NOT FOUND{RESET}")

    return results


def print_test_report(results: dict) -> bool:
    """Print final test report. Returns True if test passed."""
    log(f"\n{BOLD}{'=' * 60}{RESET}", CYAN)
    log(f"{BOLD}  TEST REPORT: MAX OPEN POSITIONS LIMIT{RESET}", CYAN)
    log(f"{BOLD}{'=' * 60}{RESET}", CYAN)

    # Check conditions
    fills_active = results["fill_1_active"] and results["fill_2_active"] and results["fill_3_active"]
    overflow_rejected = results["overflow_rejected"]

    # Report each signal
    for i in range(1, 4):
        key = f"fill_{i}_active"
        status = "ACTIVE" if results[key] else "NOT ACTIVE"
        icon = "[PASS]" if results[key] else "[FAIL]"
        color = GREEN if results[key] else RED
        log(f"  {color}{icon} TEST_FILL_{i}: {status}{RESET}")

    # Overflow signal
    icon = "[PASS]" if overflow_rejected else "[FAIL]"
    color = GREEN if overflow_rejected else RED
    log(f"  {color}{icon} TEST_OVERFLOW: {results['overflow_status'] or 'UNKNOWN'}{RESET}")

    log(f"\n{BOLD}Success Criteria:{RESET}")
    log(f"  Status: {results['overflow_status']}")
    log(f"  Notes:  {results['overflow_notes']}")

    expected_status = "correlation_rejected"
    expected_note = "Max positions reached"

    status_match = results["overflow_status"] == expected_status
    # Safely handle None in notes comparison
    overflow_notes = results["overflow_notes"] or ""
    note_match = expected_note.lower() in overflow_notes.lower()

    log(f"\n{BOLD}Validation:{RESET}")
    log(f"  Expected status: '{expected_status}' -> {'MATCH' if status_match else 'NO MATCH'}", GREEN if status_match else RED)
    log(f"  Expected note contains: '{expected_note}' -> {'MATCH' if note_match else 'NO MATCH'}", GREEN if note_match else RED)

    # Final verdict
    passed = fills_active and status_match and note_match

    log(f"\n{BOLD}{'=' * 60}{RESET}")
    if passed:
        log(f"{GREEN}{BOLD}  TEST PASSED: Max Open Positions rule is working correctly!{RESET}")
    else:
        log(f"{RED}{BOLD}  TEST FAILED: Max Open Positions rule not enforced as expected.{RESET}")
    log(f"{BOLD}{'=' * 60}{RESET}\n")

    return passed


def print_cleanup_sql() -> None:
    """Print cleanup SQL for manual execution."""
    symbols = ", ".join(f"'{s}'" for s in TEST_SYMBOLS)
    log(f"\n{YELLOW}Cleanup SQL (run in Supabase):{RESET}")
    log(f"  DELETE FROM trading_signals WHERE symbol IN ({symbols});", DIM)


def main() -> int:
    print_header()

    # Load configuration
    log(f"{BOLD}=== CONFIGURATION ==={RESET}", CYAN)
    webhook_url, supabase_url, supabase_key, webhook_secret = load_config()

    # Initialize Supabase
    supabase = init_supabase(supabase_url, supabase_key)

    # Cleanup previous test data
    cleanup_test_signals(supabase)

    # Execute synchronous attack sequence
    if not execute_attack_sequence(supabase, webhook_url, webhook_secret):
        log_fail("Attack sequence failed")
        print_cleanup_sql()
        return 1

    # Verify overflow rejection
    results = verify_overflow_rejection(supabase)

    # Print report
    passed = print_test_report(results)

    # Cleanup instructions
    print_cleanup_sql()

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
