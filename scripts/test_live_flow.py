#!/usr/bin/env python3
"""
🧪 End-to-End Smoke Test for Trading System
============================================
Simulates TradingView webhook signals to verify the full pipeline:
  Backend → Redis → Worker (AI Guardian) → Supabase → Dashboard

Usage:
  python scripts/test_live_flow.py
"""

import requests
import time
import sys
from datetime import datetime

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║       🧪 TRADING SYSTEM E2E SMOKE TEST                        ║
║       Simulates TradingView Webhook Signals                   ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")


def get_config():
    """Prompt user for configuration."""
    print(f"{YELLOW}📋 Configuration{RESET}")
    print("-" * 50)

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


def send_signal(url: str, secret: str, payload: dict, label: str) -> dict:
    """Send a webhook signal and return the response."""
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    endpoint = f"{url}/webhook"

    print(f"{CYAN}📤 Sending: {label}{RESET}")
    print(f"   Endpoint: {endpoint}")
    print(f"   Symbol: {payload['symbol']} | Side: {payload['side'].upper()}")
    print(f"   Entry: {payload['entry']} | SL: {payload['sl']} | TP: {payload['tp']}")

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        result = {
            "status_code": response.status_code,
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }

        if response.status_code == 200:
            body = result["body"]
            status = body.get("status", "unknown")
            if status == "success":
                print(f"   {GREEN}✓ ACCEPTED (alert_id: {body.get('alert_id')}){RESET}")
            elif status == "queued":
                print(f"   {GREEN}✓ QUEUED for worker processing{RESET}")
            elif status == "filtered":
                reason = body.get("reason", body.get("reasons", ["Unknown"]))
                print(f"   {YELLOW}⚠ FILTERED: {reason}{RESET}")
            else:
                print(f"   {GREEN}✓ Response: {status}{RESET}")
        else:
            print(f"   {RED}✗ HTTP {response.status_code}: {result['body']}{RESET}")

        return result

    except requests.exceptions.ConnectionError:
        print(f"   {RED}✗ CONNECTION FAILED - Is the backend running?{RESET}")
        return {"status_code": 0, "error": "Connection failed"}
    except Exception as e:
        print(f"   {RED}✗ ERROR: {e}{RESET}")
        return {"status_code": 0, "error": str(e)}


def create_perfect_buy_signal():
    """
    Creates a HIGH PROBABILITY signal that should be APPROVED by AI Guardian.

    ✓ liq_swept=True      → Passes Inducement Rule
    ✓ departure_strength=78 → Aggressive arrival (passes Arrival Rule)
    ✓ entry_model=FLIP    → Clean rejection pattern
    ✓ R:R = 2.0           → Good risk/reward
    """
    return {
        # Core fields (required)
        "symbol": "BTCUSD",
        "side": "buy",
        "entry": 50000.0,
        "sl": 49500.0,
        "tp": 51000.0,
        "size": 0.01,

        # Zone identification
        "zone_id": int(datetime.now().timestamp()),  # Unique ID
        "zone_type": "demand",
        "zone_top": 50050.0,
        "zone_bottom": 49950.0,

        # AI Guardian - Critical fields
        "liq_swept": True,           # ✓ CRITICAL: Inducement swept
        "departure_strength": 78.5,   # ✓ Aggressive arrival (>60)
        "return_strength": 88.5,      # ✓ Strong return to zone
        "entry_model": "FLIP",        # ✓ Clean rejection wick

        # Quality metrics
        "score": 82.0,               # High quality zone
        "freshness": 1,              # First touch
        "base_quality": 85.0,

        # Market context
        "trend": 1,                  # With trend
        "htf_trend": 1,              # Higher timeframe aligned
        "session": 2,                # Active session
        "atr_ratio": 0.85,
        "rsi": 55.0,
        "adx": 28.0,
        "rvol": 1.35,

        # Additional context
        "target_swept": True,
        "caused_sweep": True,
        "is_accuracy": False,
        "touch_count": 1,
        "liquidity_distance": 15.0,
        "liquidity_spread": 45.0,
    }


def create_bad_setup_signal():
    """
    Creates a LOW PROBABILITY signal that should be REJECTED by AI Guardian.

    ✗ liq_swept=False        → FAILS Inducement Rule (CRITICAL)
    ✗ departure_strength=25  → Compressed arrival (FAILS Arrival Rule)
    ✗ score=35               → Low quality zone
    """
    return {
        # Core fields (required)
        "symbol": "ETHUSD",
        "side": "sell",
        "entry": 3000.0,
        "sl": 3050.0,
        "tp": 2900.0,
        "size": 0.1,

        # Zone identification
        "zone_id": int(datetime.now().timestamp()) + 1,  # Different ID
        "zone_type": "supply",
        "zone_top": 3010.0,
        "zone_bottom": 2990.0,

        # AI Guardian - Fields that should trigger rejection
        "liq_swept": False,          # ✗ CRITICAL FAIL: No inducement
        "departure_strength": 25.0,   # ✗ Compressed arrival (<40)
        "return_strength": 30.0,      # ✗ Weak return
        "entry_model": "BREAK_CANDLE", # ✗ Questionable pattern

        # Quality metrics - all weak
        "score": 35.0,               # Low quality
        "freshness": 0,              # Retrace (not first touch)
        "base_quality": 40.0,

        # Market context - counter-trend
        "trend": -1,                 # Against trend
        "htf_trend": -1,             # Higher timeframe misaligned
        "session": 3,                # Quiet session
        "atr_ratio": 1.5,            # Overextended
        "rsi": 75.0,                 # Overbought
        "adx": 15.0,                 # Weak trend
        "rvol": 0.6,                 # Low volume

        # Additional context
        "target_swept": False,
        "caused_sweep": False,
        "is_accuracy": False,
        "touch_count": 3,            # Multiple touches (weak)
        "liquidity_distance": 50.0,
        "liquidity_spread": 80.0,
    }


def main():
    print_header()

    # Get configuration
    url, secret = get_config()

    print(f"{BOLD}🚀 Starting Test Sequence{RESET}")
    print("=" * 50)
    print()

    # Signal 1: Perfect Buy Setup (should be APPROVED)
    print(f"{GREEN}{BOLD}[TEST 1] Perfect Buy Setup - Expected: AI APPROVE{RESET}")
    print("-" * 50)
    perfect_signal = create_perfect_buy_signal()
    result1 = send_signal(url, secret, perfect_signal, "BTC High-Probability Buy")
    print()

    # Wait between signals
    print(f"{YELLOW}⏳ Waiting 2 seconds before next signal...{RESET}")
    time.sleep(2)
    print()

    # Signal 2: Bad Setup (should be REJECTED)
    print(f"{RED}{BOLD}[TEST 2] Bad Setup - Expected: AI REJECT{RESET}")
    print("-" * 50)
    bad_signal = create_bad_setup_signal()
    result2 = send_signal(url, secret, bad_signal, "ETH Low-Probability Sell")
    print()

    # Summary
    print("=" * 50)
    print(f"{CYAN}{BOLD}📊 TEST SUMMARY{RESET}")
    print("=" * 50)

    success_count = 0

    # Check Signal 1
    if result1.get("status_code") == 200:
        body = result1.get("body", {})
        status = body.get("status")
        if status == "success":
            print(f"{GREEN}✓ Signal 1 (BTCUSD): Accepted as expected{RESET}")
            success_count += 1
        elif status == "queued":
            print(f"{GREEN}✓ Signal 1 (BTCUSD): Queued for worker processing{RESET}")
            success_count += 1
        elif status == "filtered":
            print(f"{RED}✗ Signal 1 (BTCUSD): Filtered (unexpected - check AI config){RESET}")
        else:
            print(f"{YELLOW}? Signal 1 (BTCUSD): {body}{RESET}")
    else:
        print(f"{RED}✗ Signal 1 (BTCUSD): Failed to send{RESET}")

    # Check Signal 2
    if result2.get("status_code") == 200:
        body = result2.get("body", {})
        status = body.get("status")
        if status == "filtered":
            print(f"{GREEN}✓ Signal 2 (ETHUSD): Filtered as expected (AI working!){RESET}")
            success_count += 1
        elif status == "queued":
            print(f"{YELLOW}⚠ Signal 2 (ETHUSD): Queued (AI filtering happens in worker){RESET}")
            success_count += 1
        elif status == "success":
            print(f"{YELLOW}⚠ Signal 2 (ETHUSD): Accepted (AI filter may be disabled){RESET}")
            success_count += 0.5
        else:
            print(f"{YELLOW}? Signal 2 (ETHUSD): {body}{RESET}")
    else:
        print(f"{RED}✗ Signal 2 (ETHUSD): Failed to send{RESET}")

    print()

    # Final verdict
    if success_count >= 2:
        print(f"{GREEN}{BOLD}🎉 BACKEND OK! Signals queued successfully.{RESET}")
        # Check if status was "queued" - worker might not be running
        if result1.get("body", {}).get("status") == "queued":
            print()
            print(f"{YELLOW}{BOLD}⚠️  IMPORTANT: Signals are QUEUED, not processed yet.{RESET}")
            print(f"{YELLOW}   The WORKER service must be running to process signals.{RESET}")
            print(f"{YELLOW}   Check if worker.py is deployed and running on Railway.{RESET}")
    elif success_count >= 1:
        print(f"{YELLOW}{BOLD}⚠️  PARTIAL SUCCESS - Check the logs for details.{RESET}")
    else:
        print(f"{RED}{BOLD}❌ TESTS FAILED - Check backend connectivity and logs.{RESET}")

    print()
    print(f"{CYAN}📺 Now check your Dashboard at your frontend URL{RESET}")
    print(f"{CYAN}📋 See TESTING_GUIDE.md for what to look for in logs{RESET}")
    print()


if __name__ == "__main__":
    main()
