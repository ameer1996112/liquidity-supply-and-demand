#!/usr/bin/env python3
"""
🛡️ Trinity Engine Compliance Test Suite
========================================
QA validation script for the Funded Account Guardian system.

Tests:
1. The "Gambler" Test    - Risk per trade > 1% (risk_rejected)
2. The "Hoarder" Test    - Max positions exceeded (correlation_rejected)
3. The "Double Dip" Test - Currency correlation (correlation_rejected)
4. The "Fat Finger" Test - Invalid price data (adapter_rejected or validation error)

Usage:
    python scripts/test_trinity_compliance.py

Author: QA Compliance Engineer
Version: 1.0.0
"""

import requests
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def print_header():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════╗
║     🛡️  TRINITY ENGINE COMPLIANCE TEST SUITE                      ║
║     Funded Account Guardian - QA Validation                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Tests:                                                           ║
║  [1] The "Gambler" Test    - Max Risk Per Trade (1%)              ║
║  [2] The "Hoarder" Test    - Max Positions (3)                    ║
║  [3] The "Double Dip" Test - Currency Correlation                 ║
║  [4] The "Fat Finger" Test - Invalid Price Data                   ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
""")


def get_config() -> Tuple[str, str]:
    """Prompt user for configuration."""
    print(f"{YELLOW}📋 Configuration{RESET}")
    print("-" * 60)

    # Backend URL
    default_url = "http://localhost:8000"
    url = input(f"Backend URL [{default_url}]: ").strip()
    if not url:
        url = default_url
    url = url.rstrip("/")

    # Webhook Secret
    secret = input("Webhook Secret (press Enter if none): ").strip()

    print()
    return url, secret


def send_signal(url: str, secret: str, payload: dict, label: str) -> Dict[str, Any]:
    """Send a webhook signal and return the response."""
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    endpoint = f"{url}/webhook"

    print(f"{CYAN}   📤 Sending: {label}{RESET}")
    print(f"      Symbol: {payload.get('symbol', 'N/A')} | Side: {payload.get('side', 'N/A').upper()}")
    print(f"      Entry: {payload.get('entry', 'N/A')} | SL: {payload.get('sl', 'N/A')} | Size: {payload.get('size', 'N/A')}")

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        result = {
            "status_code": response.status_code,
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }

        if response.status_code == 200:
            print(f"      {GREEN}✓ HTTP 200 - Queued for processing{RESET}")
        elif response.status_code == 422:
            print(f"      {YELLOW}⚠ HTTP 422 - Validation Error{RESET}")
        elif response.status_code == 400:
            print(f"      {YELLOW}⚠ HTTP 400 - Bad Request{RESET}")
        else:
            print(f"      {RED}✗ HTTP {response.status_code}{RESET}")

        return result

    except requests.exceptions.ConnectionError:
        print(f"      {RED}✗ CONNECTION FAILED - Is the backend running?{RESET}")
        return {"status_code": 0, "error": "Connection failed"}
    except Exception as e:
        print(f"      {RED}✗ ERROR: {e}{RESET}")
        return {"status_code": 0, "error": str(e)}


def create_base_signal(symbol: str, side: str, entry: float, sl: float, tp: float, size: float) -> dict:
    """Create a base signal payload."""
    return {
        "symbol": symbol,
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "size": size,
        "zone_id": int(datetime.now().timestamp() * 1000),
        "zone_type": "demand" if side == "buy" else "supply",
        "liq_swept": True,
        "departure_strength": 75.0,
        "return_strength": 80.0,
        "entry_model": "FLIP",
        "score": 80.0,
        "freshness": 1,
        "trend": 1 if side == "buy" else -1,
        "run_mode": "TEST",
        "run_id": "trinity-compliance-test",
    }


# ══════════════════════════════════════════════════════════════════
# TEST 1: THE "GAMBLER" TEST
# ══════════════════════════════════════════════════════════════════


def test_gambler(url: str, secret: str) -> Tuple[bool, str]:
    """
    The "Gambler" Test - Risk per trade exceeds 1% of equity.

    Sends a signal with an oversized position that would risk 5% of equity.

    Expected: Worker rejects with status='risk_rejected',
              Notes contain "ANTI-GAMBLING" or "Max Risk"
    """
    print(f"\n{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{MAGENTA}{BOLD}[TEST 1] THE 'GAMBLER' TEST{RESET}")
    print(f"{MAGENTA}Scenario: Trade with 5% equity risk (violates 1% max){RESET}")
    print(f"{MAGENTA}Expected: status='risk_rejected', note contains 'ANTI-GAMBLING'{RESET}")
    print(f"{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")

    # Create an oversized position
    # With $10,000 account and 1% max risk = $100 max
    # This signal risks ~$500 (5% of equity) - way over limit
    signal = create_base_signal(
        symbol="TEST_GAMBLER",
        side="buy",
        entry=100.00,      # Entry price
        sl=90.00,          # Stop loss 10 points away
        tp=120.00,         # Take profit
        size=5.0,          # 5 lots - way too big!
    )
    # Override with explicit high risk
    signal["risk_percent"] = 5.0  # Explicitly request 5% risk

    result = send_signal(url, secret, signal, "Oversized Gambler Signal (5% risk)")

    # Signal will be queued - worker does the rejection
    if result.get("status_code") == 200:
        print(f"\n   {CYAN}ℹ️  Signal queued - Worker will evaluate risk{RESET}")
        print(f"   {CYAN}   Check Supabase for status='risk_rejected'{RESET}")
        return True, "Queued for risk evaluation"
    else:
        return False, f"Failed to queue: {result}"


# ══════════════════════════════════════════════════════════════════
# TEST 2: THE "HOARDER" TEST
# ══════════════════════════════════════════════════════════════════


def test_hoarder(url: str, secret: str) -> Tuple[bool, str]:
    """
    The "Hoarder" Test - Exceeds max positions limit (3).

    Sends 4 signals for different assets. The 4th should be rejected.

    Expected: Signals 1-3 queued, Signal 4 rejected with
              status='correlation_rejected', note contains 'MAX POSITIONS'
    """
    print(f"\n{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{MAGENTA}{BOLD}[TEST 2] THE 'HOARDER' TEST{RESET}")
    print(f"{MAGENTA}Scenario: Open 4 positions (violates max 3 positions){RESET}")
    print(f"{MAGENTA}Expected: 4th signal = status='correlation_rejected'{RESET}")
    print(f"{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")

    test_assets = [
        ("TEST_HOARD_A", "buy", 1.0000, 0.9950, 1.0100),
        ("TEST_HOARD_B", "sell", 1.5000, 1.5050, 1.4900),
        ("TEST_HOARD_C", "buy", 2.0000, 1.9950, 2.0100),
        ("TEST_HOARD_D", "sell", 2.5000, 2.5050, 2.4900),  # This should be rejected
    ]

    results = []
    for i, (symbol, side, entry, sl, tp) in enumerate(test_assets, 1):
        signal = create_base_signal(
            symbol=symbol,
            side=side,
            entry=entry,
            sl=sl,
            tp=tp,
            size=0.01,  # Small size to pass risk check
        )
        # Make zone_id unique for each
        signal["zone_id"] = int(datetime.now().timestamp() * 1000) + i

        print(f"\n   {CYAN}Signal {i}/4:{RESET}")
        result = send_signal(url, secret, signal, f"Hoarder Signal {i}: {symbol}")
        results.append(result)

        # Small delay between signals
        time.sleep(0.5)

    # Check results
    queued_count = sum(1 for r in results if r.get("status_code") == 200)

    print(f"\n   {CYAN}ℹ️  {queued_count}/4 signals queued{RESET}")
    print(f"   {CYAN}   Worker will reject 4th due to max positions{RESET}")
    print(f"   {CYAN}   Check Supabase for TEST_HOARD_D with status='correlation_rejected'{RESET}")

    return queued_count >= 3, f"Queued {queued_count}/4 signals"


# ══════════════════════════════════════════════════════════════════
# TEST 3: THE "DOUBLE DIP" TEST
# ══════════════════════════════════════════════════════════════════


def test_double_dip(url: str, secret: str) -> Tuple[bool, str]:
    """
    The "Double Dip" Test - Currency over-exposure.

    Sends Long EURUSD followed by Long GBPUSD (both short USD).

    Expected: Second signal may be flagged by correlation manager
              for double USD exposure (depends on config)
    """
    print(f"\n{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{MAGENTA}{BOLD}[TEST 3] THE 'DOUBLE DIP' TEST{RESET}")
    print(f"{MAGENTA}Scenario: Long EURUSD + Long GBPUSD (double short USD){RESET}")
    print(f"{MAGENTA}Expected: 2nd signal may be 'correlation_rejected' for USD exposure{RESET}")
    print(f"{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")

    # Signal 1: Long EURUSD (short USD)
    signal1 = create_base_signal(
        symbol="TEST_EURUSD",
        side="buy",
        entry=1.0850,
        sl=1.0800,
        tp=1.0950,
        size=0.01,
    )
    signal1["zone_id"] = int(datetime.now().timestamp() * 1000) + 100

    print(f"\n   {CYAN}Signal 1: Long EUR/USD (Short USD){RESET}")
    result1 = send_signal(url, secret, signal1, "Long EURUSD")

    time.sleep(0.5)

    # Signal 2: Long GBPUSD (also short USD) - correlation risk!
    signal2 = create_base_signal(
        symbol="TEST_GBPUSD",
        side="buy",
        entry=1.2650,
        sl=1.2600,
        tp=1.2750,
        size=0.01,
    )
    signal2["zone_id"] = int(datetime.now().timestamp() * 1000) + 101

    print(f"\n   {CYAN}Signal 2: Long GBP/USD (Also Short USD - Correlation Risk!){RESET}")
    result2 = send_signal(url, secret, signal2, "Long GBPUSD (Double USD Exposure)")

    print(f"\n   {CYAN}ℹ️  Both signals queued{RESET}")
    print(f"   {CYAN}   If correlation rules are strict, 2nd may be rejected{RESET}")
    print(f"   {CYAN}   Check Supabase for TEST_GBPUSD status{RESET}")

    return True, "Correlation test queued"


# ══════════════════════════════════════════════════════════════════
# TEST 4: THE "FAT FINGER" TEST
# ══════════════════════════════════════════════════════════════════


def test_fat_finger(url: str, secret: str) -> Tuple[bool, str]:
    """
    The "Fat Finger" Test - Invalid price data.

    Sends signals with invalid data:
    - SL = 0 (invalid)
    - Entry = 0 (invalid)
    - Negative prices

    Expected: HTTP 422 validation error OR status='adapter_rejected'
    """
    print(f"\n{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{MAGENTA}{BOLD}[TEST 4] THE 'FAT FINGER' TEST{RESET}")
    print(f"{MAGENTA}Scenario: Invalid price data (SL=0, Entry=0){RESET}")
    print(f"{MAGENTA}Expected: HTTP 422 or status='adapter_rejected'{RESET}")
    print(f"{MAGENTA}{BOLD}═══════════════════════════════════════════════════════════════{RESET}")

    # Test 4a: Zero stop loss
    print(f"\n   {CYAN}Test 4a: Zero Stop Loss{RESET}")
    signal_zero_sl = {
        "symbol": "TEST_FATFINGER_A",
        "side": "buy",
        "entry": 100.00,
        "sl": 0,           # Invalid!
        "tp": 110.00,
        "size": 0.01,
        "zone_id": int(datetime.now().timestamp() * 1000) + 200,
    }
    result_a = send_signal(url, secret, signal_zero_sl, "Zero SL Signal")

    time.sleep(0.3)

    # Test 4b: Zero entry
    print(f"\n   {CYAN}Test 4b: Zero Entry Price{RESET}")
    signal_zero_entry = {
        "symbol": "TEST_FATFINGER_B",
        "side": "buy",
        "entry": 0,        # Invalid!
        "sl": 90.00,
        "tp": 110.00,
        "size": 0.01,
        "zone_id": int(datetime.now().timestamp() * 1000) + 201,
    }
    result_b = send_signal(url, secret, signal_zero_entry, "Zero Entry Signal")

    time.sleep(0.3)

    # Test 4c: Negative price
    print(f"\n   {CYAN}Test 4c: Negative Price{RESET}")
    signal_negative = {
        "symbol": "TEST_FATFINGER_C",
        "side": "buy",
        "entry": -100.00,  # Invalid!
        "sl": -110.00,
        "tp": -90.00,
        "size": 0.01,
        "zone_id": int(datetime.now().timestamp() * 1000) + 202,
    }
    result_c = send_signal(url, secret, signal_negative, "Negative Price Signal")

    # Count validation failures
    validation_errors = sum(
        1 for r in [result_a, result_b, result_c]
        if r.get("status_code") in [400, 422]
    )

    print(f"\n   {CYAN}ℹ️  {validation_errors}/3 caught by API validation{RESET}")
    print(f"   {CYAN}   Remaining will be caught by Market Adapter{RESET}")

    return validation_errors >= 1, f"{validation_errors}/3 validation errors"


# ══════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════════════════


def print_cleanup_sql():
    """Print SQL to clean up test records."""
    print(f"""
{YELLOW}{BOLD}═══════════════════════════════════════════════════════════════{RESET}
{YELLOW}{BOLD}🧹 CLEANUP SQL{RESET}
{YELLOW}Run this in Supabase SQL Editor to remove test records:{RESET}
{YELLOW}{BOLD}═══════════════════════════════════════════════════════════════{RESET}

{GREEN}DELETE FROM trading_signals WHERE symbol LIKE 'TEST_%';{RESET}

{DIM}-- Or to verify before deletion:{RESET}
{DIM}SELECT id, symbol, status, notes, created_at{RESET}
{DIM}FROM trading_signals{RESET}
{DIM}WHERE symbol LIKE 'TEST_%'{RESET}
{DIM}ORDER BY created_at DESC;{RESET}
""")


def print_verification_queries():
    """Print SQL queries to verify test results."""
    print(f"""
{CYAN}{BOLD}═══════════════════════════════════════════════════════════════{RESET}
{CYAN}{BOLD}🔍 VERIFICATION QUERIES{RESET}
{CYAN}Run these in Supabase SQL Editor to verify results:{RESET}
{CYAN}{BOLD}═══════════════════════════════════════════════════════════════{RESET}

{GREEN}-- Check all test signals and their status{RESET}
SELECT symbol, status, notes, created_at
FROM trading_signals
WHERE symbol LIKE 'TEST_%'
ORDER BY created_at DESC;

{GREEN}-- Count by status{RESET}
SELECT status, COUNT(*) as count
FROM trading_signals
WHERE symbol LIKE 'TEST_%'
GROUP BY status;

{GREEN}-- Find risk rejections (Gambler test){RESET}
SELECT symbol, status, notes
FROM trading_signals
WHERE symbol = 'TEST_GAMBLER'
  AND status = 'risk_rejected';

{GREEN}-- Find correlation rejections (Hoarder test){RESET}
SELECT symbol, status, notes
FROM trading_signals
WHERE symbol LIKE 'TEST_HOARD_%'
  AND status = 'correlation_rejected';

{GREEN}-- Find adapter/validation failures (Fat Finger test){RESET}
SELECT symbol, status, notes
FROM trading_signals
WHERE symbol LIKE 'TEST_FATFINGER_%';
""")


def main():
    print_header()

    # Get configuration
    url, secret = get_config()

    print(f"{BOLD}🚀 Starting Trinity Engine Compliance Tests{RESET}")
    print("=" * 60)

    results = []

    # Run all tests
    tests = [
        ("Gambler", test_gambler),
        ("Hoarder", test_hoarder),
        ("Double Dip", test_double_dip),
        ("Fat Finger", test_fat_finger),
    ]

    for name, test_fn in tests:
        try:
            passed, message = test_fn(url, secret)
            results.append((name, passed, message))
        except Exception as e:
            results.append((name, False, f"Error: {e}"))

        # Delay between test suites
        time.sleep(1)

    # Print summary
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{CYAN}{BOLD}📊 COMPLIANCE TEST SUMMARY{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    passed_count = 0
    for name, passed, message in results:
        status = f"{GREEN}✓ QUEUED{RESET}" if passed else f"{RED}✗ FAILED{RESET}"
        print(f"  [{status}] {name}: {message}")
        if passed:
            passed_count += 1

    print(f"\n  {BOLD}Total: {passed_count}/{len(results)} tests queued successfully{RESET}")

    # Important note about worker
    print(f"""
{YELLOW}{BOLD}═══════════════════════════════════════════════════════════════{RESET}
{YELLOW}{BOLD}⚠️  IMPORTANT: SIGNALS ARE QUEUED, NOT YET PROCESSED{RESET}
{YELLOW}═══════════════════════════════════════════════════════════════{RESET}

The Trinity Engine validation happens in the WORKER, not the API.
The API only queues signals to Redis.

{CYAN}To see rejection results:{RESET}
1. Ensure the worker is running: {GREEN}python -m backend.worker{RESET}
2. Wait 5-10 seconds for processing
3. Query Supabase to see rejection statuses

{CYAN}Expected results in Supabase:{RESET}
• TEST_GAMBLER     → status='risk_rejected' (anti-gambling rule)
• TEST_HOARD_D     → status='correlation_rejected' (max positions)
• TEST_GBPUSD      → status='correlation_rejected' (USD exposure) [maybe]
• TEST_FATFINGER_* → status='adapter_rejected' or filtered
""")

    # Print verification queries
    print_verification_queries()

    # Print cleanup SQL
    print_cleanup_sql()

    print(f"{CYAN}✨ Compliance test complete!{RESET}\n")


if __name__ == "__main__":
    main()
