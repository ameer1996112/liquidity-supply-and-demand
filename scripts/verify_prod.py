#!/usr/bin/env python3
"""
Production Verification Script for Railway Deployment
======================================================
Verifies that the Trading Bot API and Worker are running correctly.

Usage:
    python scripts/verify_prod.py [RAILWAY_URL]

Example:
    python scripts/verify_prod.py https://my-trading-bot.up.railway.app
"""

import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package not installed.")
    print("Install with: pip install requests")
    sys.exit(1)


# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header():
    print(f"""
{CYAN}╔══════════════════════════════════════════════════════════╗
║       🚀 Railway Production Verification Script 🚀         ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")


def test_health(base_url: str) -> tuple[bool, float, Optional[dict]]:
    """Test the /health endpoint."""
    url = f"{base_url.rstrip('/')}/health"
    try:
        start = time.perf_counter()
        response = requests.get(url, timeout=10)
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            return True, latency_ms, response.json()
        else:
            return False, latency_ms, {"error": f"Status {response.status_code}"}
    except requests.exceptions.Timeout:
        return False, 0, {"error": "Request timed out (10s)"}
    except requests.exceptions.ConnectionError as e:
        return False, 0, {"error": f"Connection failed: {e}"}
    except Exception as e:
        return False, 0, {"error": str(e)}


def test_webhook_auth(base_url: str) -> tuple[bool, float, int]:
    """Test that /webhook rejects requests without secret (expects 401)."""
    url = f"{base_url.rstrip('/')}/webhook"
    try:
        start = time.perf_counter()
        response = requests.post(
            url,
            json={"action": "test"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        latency_ms = (time.perf_counter() - start) * 1000

        # We EXPECT 401 - that means auth is working
        return response.status_code == 401, latency_ms, response.status_code
    except requests.exceptions.Timeout:
        return False, 0, 0
    except requests.exceptions.ConnectionError:
        return False, 0, 0
    except Exception:
        return False, 0, 0


def test_readiness(base_url: str) -> tuple[bool, float, Optional[dict]]:
    """Test the /ready endpoint (if exists)."""
    url = f"{base_url.rstrip('/')}/ready"
    try:
        start = time.perf_counter()
        response = requests.get(url, timeout=10)
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            return True, latency_ms, response.json()
        else:
            return False, latency_ms, {"status_code": response.status_code}
    except Exception:
        return False, 0, None


def print_result(test_name: str, passed: bool, latency_ms: float, details: str = ""):
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    latency_str = f"({latency_ms:.0f}ms)" if latency_ms > 0 else ""
    print(f"  {status} {test_name} {CYAN}{latency_str}{RESET}")
    if details:
        print(f"         {details}")


def main():
    print_header()

    # Get Railway URL
    if len(sys.argv) > 1:
        railway_url = sys.argv[1]
    else:
        print(f"{YELLOW}Enter your Railway URL:{RESET}")
        railway_url = input("  > ").strip()

    if not railway_url:
        print(f"{RED}ERROR: No URL provided{RESET}")
        sys.exit(1)

    # Ensure https://
    if not railway_url.startswith("http"):
        railway_url = f"https://{railway_url}"

    print(f"\n{BOLD}Target:{RESET} {CYAN}{railway_url}{RESET}\n")
    print(f"{BOLD}Running Tests...{RESET}\n")

    all_passed = True

    # Test 1: Health Check
    print(f"{BOLD}1. Health Check (/health){RESET}")
    health_ok, health_latency, health_data = test_health(railway_url)
    print_result(
        "API Responding",
        health_ok,
        health_latency,
        f"Response: {health_data}" if health_data else ""
    )
    all_passed &= health_ok

    # Test 2: Webhook Auth
    print(f"\n{BOLD}2. Webhook Security (/webhook){RESET}")
    auth_ok, auth_latency, status_code = test_webhook_auth(railway_url)
    print_result(
        "Auth Guard Active (expects 401)",
        auth_ok,
        auth_latency,
        f"Status: {status_code}" + (" ✓ Correctly rejected" if auth_ok else " ⚠️ Unexpected status")
    )
    all_passed &= auth_ok

    # Test 3: Readiness (optional - many deployments don't have this)
    print(f"\n{BOLD}3. Readiness Check (/ready){RESET}")
    ready_ok, ready_latency, ready_data = test_readiness(railway_url)
    if ready_data is None or (isinstance(ready_data, dict) and ready_data.get("status_code") == 404):
        print(f"  {YELLOW}⏭️  SKIP{RESET} Endpoint not implemented (optional)")
    else:
        print_result(
            "Database & Redis Connected",
            ready_ok,
            ready_latency,
            f"Response: {ready_data}" if ready_data else ""
        )
        all_passed &= ready_ok

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════════════╗
║              ✅ SYSTEM ONLINE - ALL TESTS PASSED           ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")
    else:
        print(f"""
{RED}{BOLD}╔══════════════════════════════════════════════════════════╗
║              ❌ SYSTEM ISSUES DETECTED                     ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")
        sys.exit(1)

    # Worker verification instructions
    print(f"""{BOLD}📋 Worker Verification (Manual Step){RESET}
{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}

The Worker runs as a background process. To verify it's alive:

{BOLD}Option 1: Railway CLI{RESET}
  $ railway logs --service worker

{BOLD}Option 2: Railway Dashboard{RESET}
  1. Go to: https://railway.app/project/{YELLOW}<your-project-id>{RESET}
  2. Click on the Worker service
  3. Check the "Logs" tab

{BOLD}Look for these log messages:{RESET}
  {GREEN}✓{RESET} "Worker started with AI Guardian ENABLED"
     or "Worker started with AI Guardian DISABLED"
  {GREEN}✓{RESET} "Listening for signals from Redis..."
  {GREEN}✓{RESET} "Processing signal: BUY/SELL ..."

{BOLD}If logs show connection errors:{RESET}
  {RED}✗{RESET} Check REDIS_URL environment variable
  {RED}✗{RESET} Ensure Redis service is running in Railway
""")


if __name__ == "__main__":
    main()
