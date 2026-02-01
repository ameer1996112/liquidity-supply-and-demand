#!/usr/bin/env python3
"""
TradingView Webhook Simulator
==============================
Simulates a TradingView alert to verify end-to-end connectivity with the Railway backend.

Features:
  1. Loads WEBHOOK_SECRET and WEBHOOK_URL from .env
  2. Sends a test payload mimicking a real TradingView alert
  3. Prints the request body and server response
  4. Optionally verifies the row was created in Supabase

Usage:
  python scripts/simulate_tv_event.py
  python scripts/simulate_tv_event.py --verify-db
  python scripts/simulate_tv_event.py --dry-run

Environment Variables (from .env):
  WEBHOOK_URL     - Your Railway backend URL (e.g., https://your-api.up.railway.app)
  WEBHOOK_SECRET  - The passphrase for authentication
  SUPABASE_URL    - Supabase project URL (for --verify-db)
  SUPABASE_ANON_KEY or SUPABASE_KEY - Supabase key (for --verify-db)
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# =============================================================================
# ANSI Colors for Terminal Output
# =============================================================================
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

def success(msg: str) -> None:
    print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS]{Colors.RESET} {msg}")

def error(msg: str) -> None:
    print(f"{Colors.RED}{Colors.BOLD}[ERROR]{Colors.RESET} {msg}")

def warning(msg: str) -> None:
    print(f"{Colors.YELLOW}{Colors.BOLD}[WARNING]{Colors.RESET} {msg}")

def info(msg: str) -> None:
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {msg}")

def header(msg: str) -> None:
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}{Colors.RESET}\n")

# =============================================================================
# Load Environment Variables
# =============================================================================
def load_env() -> dict:
    """Load environment variables from .env files."""
    # Try multiple .env locations
    env_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "backend" / ".env",
        Path.cwd() / ".env",
    ]

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            info(f"Loaded environment from: {env_path}")
            break
    else:
        warning("No .env file found - using system environment variables")

    config = {
        "webhook_url": os.getenv("WEBHOOK_URL", "").rstrip("/"),
        "webhook_secret": os.getenv("WEBHOOK_SECRET", ""),
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_key": os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", ""),
    }

    return config

# =============================================================================
# Test Payload Generation
# =============================================================================
def create_test_payload(symbol: str = "TV_TEST_BTC") -> dict:
    """
    Create a test payload that mimics a real TradingView alert.

    This payload is designed to:
    - Pass authentication (passphrase is added separately)
    - Pass Risk Guardian (size=0.01 < 0.30 limit)
    - Pass Correlation Guardian (if <3 active positions)
    - Challenge ML Guardian (may be approved/rejected based on model)
    """
    timestamp = int(datetime.now().timestamp())

    return {
        # Required fields
        "symbol": symbol,
        "side": "buy",
        "entry": 50000.0,
        "sl": 49500.0,
        "tp": 51000.0,
        "size": 0.01,  # Small size to pass Risk Guardian

        # Zone metadata
        "zone_id": timestamp,
        "zone_type": "demand",
        "zone_top": 50050.0,
        "zone_bottom": 49950.0,
        "zone_size_pips": 100.0,

        # Entry model & quality
        "entry_model": "FLIP",
        "score": 95.0,
        "freshness": 1,
        "base_quality": 90.0,

        # AI Features (in "Super String" format)
        "signal": "F:score=95 | F:source=TV | F:freshness=1 | F:liq_swept=1 | F:departure_strength=75 | F:return_strength=85",

        # Price action flags
        "liq_swept": True,
        "target_swept": True,
        "caused_sweep": True,
        "is_accuracy": False,

        # Market context
        "trend": 1,
        "htf_trend": 1,
        "session": 2,
        "atr_ratio": 0.85,
        "rsi": 55.0,
        "adx": 28.0,
        "rvol": 1.35,

        # Telemetry
        "run_mode": "PAPER",
        "run_id": "tv-simulator-test",
        "trade_key": f"{symbol}_{timestamp}",
        "bar_time": datetime.utcnow().isoformat() + "Z",

        # Additional features
        "departure_strength": 75.0,
        "return_strength": 85.0,
        "liquidity_distance": 15.0,
        "liquidity_spread": 45.0,
        "touch_count": 1,
    }

# =============================================================================
# Send Webhook Request
# =============================================================================
def send_webhook(config: dict, payload: dict, dry_run: bool = False) -> dict | None:
    """
    Send a POST request to the webhook endpoint.

    Args:
        config: Environment configuration
        payload: The webhook payload
        dry_run: If True, print payload but don't send

    Returns:
        Response data dict or None on failure
    """
    webhook_url = config["webhook_url"]
    webhook_secret = config["webhook_secret"]

    if not webhook_url:
        error("WEBHOOK_URL not configured in .env")
        return None

    # Add passphrase to payload (TradingView style)
    full_payload = payload.copy()
    if webhook_secret:
        full_payload["passphrase"] = webhook_secret

    # Build endpoint URL
    endpoint = f"{webhook_url}/webhook"

    # Headers mimicking TradingView
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TradingView-Webhook",
    }

    # Optionally add secret in header too (belt and suspenders)
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret

    # Print request details
    header("REQUEST DETAILS")
    info(f"Endpoint: {endpoint}")
    info(f"Method: POST")
    info(f"Headers:")
    for k, v in headers.items():
        if k == "X-Webhook-Secret":
            print(f"    {k}: {'*' * 8}...")
        else:
            print(f"    {k}: {v}")

    print(f"\n{Colors.CYAN}Request Body:{Colors.RESET}")
    # Pretty print, but mask passphrase
    display_payload = full_payload.copy()
    if "passphrase" in display_payload:
        display_payload["passphrase"] = "****REDACTED****"
    print(json.dumps(display_payload, indent=2))

    if dry_run:
        warning("DRY RUN - Request not sent")
        return None

    # Send request
    header("SENDING REQUEST")

    try:
        response = requests.post(
            endpoint,
            json=full_payload,
            headers=headers,
            timeout=30,
        )

        # Print response
        print(f"{Colors.CYAN}Response Status:{Colors.RESET} {response.status_code}")
        print(f"{Colors.CYAN}Response Headers:{Colors.RESET}")
        for k, v in response.headers.items():
            print(f"    {k}: {v}")

        print(f"\n{Colors.CYAN}Response Body:{Colors.RESET}")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except json.JSONDecodeError:
            print(response.text)
            response_json = {"raw": response.text}

        # Evaluate result
        header("RESULT")

        if response.status_code == 200:
            status = response_json.get("status", "unknown")
            if status == "queued":
                success("CONNECTION SUCCESS - Signal queued for worker processing")
                return response_json
            elif status == "success":
                success(f"CONNECTION SUCCESS - Alert saved (ID: {response_json.get('alert_id')})")
                return response_json
            elif status == "filtered":
                warning(f"Signal filtered: {response_json.get('reason', response_json.get('reasons'))}")
                return response_json
            else:
                success(f"Connection OK - Status: {status}")
                return response_json

        elif response.status_code == 401:
            error("AUTH FAILED - Invalid webhook secret (passphrase)")
            error("Check that WEBHOOK_SECRET in .env matches the server's WEBHOOK_SECRET")
            return None

        elif response.status_code == 422:
            error("VALIDATION FAILED - Invalid payload format")
            error(f"Details: {response_json}")
            return None

        else:
            error(f"UNEXPECTED STATUS: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        error("REQUEST TIMEOUT - Server did not respond within 30 seconds")
        return None

    except requests.exceptions.ConnectionError as e:
        error(f"CONNECTION FAILED - Could not reach server")
        error(f"URL: {endpoint}")
        error(f"Details: {e}")
        return None

    except Exception as e:
        error(f"UNEXPECTED ERROR: {e}")
        return None

# =============================================================================
# Verify in Supabase
# =============================================================================
def verify_in_database(config: dict, symbol: str) -> bool:
    """
    Check if the test signal was saved to Supabase.

    Args:
        config: Environment configuration
        symbol: The symbol to search for

    Returns:
        True if found, False otherwise
    """
    header("DATABASE VERIFICATION")

    if not config["supabase_url"] or not config["supabase_key"]:
        warning("Supabase credentials not configured - skipping DB verification")
        warning("Set SUPABASE_URL and SUPABASE_ANON_KEY in .env to enable")
        return False

    try:
        from supabase import create_client

        info(f"Connecting to Supabase...")
        client = create_client(config["supabase_url"], config["supabase_key"])

        info(f"Searching for symbol: {symbol}")

        # Query for recent entries with our test symbol
        response = (
            client.table("trading_signals")
            .select("id, symbol, side, status, created_at, notes, ml_win_probability")
            .eq("symbol", symbol)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )

        if response.data:
            success(f"Found {len(response.data)} record(s) for {symbol}:")
            for row in response.data:
                print(f"\n    {Colors.GREEN}ID:{Colors.RESET} {row.get('id')}")
                print(f"    {Colors.CYAN}Symbol:{Colors.RESET} {row.get('symbol')}")
                print(f"    {Colors.CYAN}Side:{Colors.RESET} {row.get('side')}")
                print(f"    {Colors.CYAN}Status:{Colors.RESET} {row.get('status')}")
                print(f"    {Colors.CYAN}ML Prob:{Colors.RESET} {row.get('ml_win_probability')}")
                print(f"    {Colors.CYAN}Notes:{Colors.RESET} {row.get('notes')}")
                print(f"    {Colors.CYAN}Created:{Colors.RESET} {row.get('created_at')}")
            return True
        else:
            warning(f"No records found for symbol: {symbol}")
            warning("The worker may not have processed the signal yet, or it was rejected")
            return False

    except ImportError:
        error("supabase-py not installed. Run: pip install supabase")
        return False

    except Exception as e:
        error(f"Database query failed: {e}")
        return False

# =============================================================================
# Main Entry Point
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Simulate a TradingView webhook alert",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/simulate_tv_event.py              # Send test signal
  python scripts/simulate_tv_event.py --verify-db  # Send and verify in Supabase
  python scripts/simulate_tv_event.py --dry-run    # Show payload without sending
  python scripts/simulate_tv_event.py --symbol XAUUSD_TEST  # Custom symbol
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload without sending the request"
    )
    parser.add_argument(
        "--verify-db",
        action="store_true",
        help="Verify the signal was saved to Supabase after sending"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="TV_TEST_BTC",
        help="Symbol to use for the test signal (default: TV_TEST_BTC)"
    )

    args = parser.parse_args()

    # Header
    print(f"""
{Colors.MAGENTA}{Colors.BOLD}
  _____ ____      _    ____ ___ _   _  ______     _____ _______        __
 |_   _|  _ \    / \  |  _ \_ _| \ | |/ ___\ \   / /_ _| ____\ \      / /
   | | | |_) |  / _ \ | | | | ||  \| | |  _ \ \ / / | ||  _|  \ \ /\ / /
   | | |  _ <  / ___ \| |_| | || |\  | |_| | \ V /  | || |___  \ V  V /
   |_| |_| \_\/_/   \_\____/___|_| \_|\____|  \_/  |___|_____|  \_/\_/

     W E B H O O K   S I M U L A T O R   v1.0
{Colors.RESET}
""")

    # Load config
    config = load_env()

    # Show config summary
    header("CONFIGURATION")
    info(f"WEBHOOK_URL: {config['webhook_url'] or '(not set)'}")
    info(f"WEBHOOK_SECRET: {'****' + config['webhook_secret'][-4:] if len(config['webhook_secret']) > 4 else '(not set)'}")
    info(f"SUPABASE_URL: {config['supabase_url'][:40] + '...' if config['supabase_url'] else '(not set)'}")
    info(f"Test Symbol: {args.symbol}")

    # Create payload
    payload = create_test_payload(symbol=args.symbol)

    # Send request
    result = send_webhook(config, payload, dry_run=args.dry_run)

    # Verify in database if requested
    if args.verify_db and result:
        print()
        info("Waiting 3 seconds for worker to process...")
        import time
        time.sleep(3)
        verify_in_database(config, args.symbol)

    # Exit with appropriate code
    if args.dry_run:
        sys.exit(0)
    elif result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
