#!/usr/bin/env python3
"""
End-to-End Test Suite with Discord Notifications
Runs automated tests and reports results to Discord
"""

import requests
import time
import os
from datetime import datetime
from supabase import create_client, Client
import sys
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
BASE_URL = os.getenv("WEBHOOK_URL", "https://grand-learning-production-bc96.up.railway.app")
PASSPHRASE = os.getenv("WEBHOOK_PASSPHRASE", "YOUR_WEBHOOK_PASSPHRASE")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Test configuration
TEST_ZONE_ID = 99999
TIMEOUT = 10

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'

def print_test(name):
    print(f"\n{Colors.BLUE}🧪 TEST: {name}{Colors.END}")

def print_pass(msg):
    print(f"{Colors.GREEN}✅ PASS: {msg}{Colors.END}")

def print_fail(msg):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")

def print_warn(msg):
    print(f"{Colors.YELLOW}⚠️  WARN: {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.CYAN}ℹ️  INFO: {msg}{Colors.END}")

# Discord notification functions
def send_discord_notification(title, description, color, fields=None, footer=None):
    """Send formatted embed to Discord webhook"""
    if not DISCORD_WEBHOOK_URL:
        print_warn("Discord webhook URL not set, skipping notification")
        return

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {
            "text": footer or f"Trading System Tests • {os.getenv('RAILWAY_ENVIRONMENT', 'local')}"
        }
    }

    if fields:
        embed["fields"] = fields

    payload = {
        "embeds": [embed]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code == 204:
            print_pass("Discord notification sent")
        else:
            print_warn(f"Discord notification failed: {response.status_code}")
    except Exception as e:
        print_warn(f"Failed to send Discord notification: {e}")

def send_test_start():
    """Notify Discord that tests are starting"""
    send_discord_notification(
        title="🧪 E2E Tests Started",
        description=f"Running automated tests on `{BASE_URL}`",
        color=0x3498db,  # Blue
        fields=[
            {"name": "Environment", "value": os.getenv("RAILWAY_ENVIRONMENT", "local"), "inline": True},
            {"name": "Trigger", "value": os.getenv("RAILWAY_DEPLOYMENT_ID", "Manual"), "inline": True},
            {"name": "Timestamp", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), "inline": False}
        ]
    )

def send_test_results(results, duration):
    """Send test results summary to Discord"""
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    success_rate = (passed / total * 100) if total > 0 else 0

    # Determine color based on results
    if passed == total:
        color = 0x2ecc71  # Green
        emoji = "✅"
        status = "ALL TESTS PASSED"
    elif passed == 0:
        color = 0xe74c3c  # Red
        emoji = "❌"
        status = "ALL TESTS FAILED"
    else:
        color = 0xf39c12  # Orange
        emoji = "⚠️"
        status = "SOME TESTS FAILED"

    # Build fields for each test
    fields = []
    for name, result in results.items():
        fields.append({
            "name": f"{'✅' if result else '❌'} {name}",
            "value": "Passed" if result else "**Failed**",
            "inline": True
        })

    # Add summary field
    fields.append({
        "name": "📊 Summary",
        "value": f"**{passed}/{total}** tests passed ({success_rate:.0f}%)\n⏱️ Duration: {duration:.1f}s",
        "inline": False
    })

    send_discord_notification(
        title=f"{emoji} E2E Tests Complete: {status}",
        description=f"Test suite finished with **{passed}/{total}** passing tests",
        color=color,
        fields=fields
    )

def send_critical_failure(test_name, error):
    """Send alert for critical test failures"""
    error_str = str(error)
    if len(error_str) > 1000:
        error_str = error_str[:1000] + "..."

    send_discord_notification(
        title="🚨 Critical Test Failure",
        description=f"Test **{test_name}** failed with critical error",
        color=0xe74c3c,  # Red
        fields=[
            {"name": "Error", "value": f"```{error_str}```", "inline": False},
            {"name": "Action Required", "value": "Check logs and verify system health immediately", "inline": False}
        ]
    )

# Initialize Supabase client
print_info("Initializing Supabase client...")
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL or SUPABASE_ANON_KEY not set")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print_pass("Supabase client initialized")
except Exception as e:
    print_fail(f"Failed to connect to Supabase: {e}")
    send_critical_failure("Supabase Connection", e)
    sys.exit(1)

# Test 1: Health Check
def test_health_check():
    print_test("Health Check")
    try:
        print_info(f"Checking {BASE_URL}/health")
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", "Status not healthy"
        print_pass(f"Server is healthy: {data}")
        return True
    except Exception as e:
        print_fail(f"Health check failed: {e}")
        return False

# Test 2: Entry Webhook with Full AI Features
def test_entry_webhook():
    print_test("Entry Webhook (V7.1 Features)")

    payload = {
        "passphrase": PASSPHRASE,
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.08500,
        "sl": 1.08400,
        "tp": 1.08700,
        "size": 0.10,
        "zone_id": TEST_ZONE_ID,
        "zone_type": "demand",
        "zone_top": 1.08520,
        "zone_bottom": 1.08480,
        "rr_ratio": 2.0,
        "sl_pips": 10.0,
        "entry_model": "FLIP",
        "liq_swept": True,
        "target_swept": True,
        "caused_sweep": True,
        "is_accuracy": False,
        # V7.1 AI Features (18 total)
        "score": 75.5,
        "freshness": 1,
        "session": 2,
        "atr_ratio": 0.85,
        "trend": 1,
        "rsi": 58.5,
        "htf_trend": 1,
        "rvol": 1.35,
        "adx": 28.3,
        "touch_count": 1,
        "base_quality": 82.0,
        "departure_strength": 78.5,
        "liquidity_distance": 15.2,
        "liquidity_spread": 45.8,
        "return_strength": 88.5
    }

    try:
        print_info(f"Sending entry webhook for zone_id={TEST_ZONE_ID}")
        response = requests.post(
            f"{BASE_URL}/webhook",
            json=payload,
            timeout=TIMEOUT
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print_info(f"Response: {data}")

        assert data.get("status") == "success", f"Status not success: {data.get('message')}"

        # Note: API doesn't return zone_id in response, it will be verified in database
        if data.get("alert_id"):
            print_pass(f"Entry webhook accepted (alert_id: {data['alert_id']})")
        else:
            print_pass(f"Entry webhook accepted")
        return True

    except Exception as e:
        print_fail(f"Entry webhook failed: {e}")
        if hasattr(e, 'response'):
            print_fail(f"Response: {e.response.text}")
        return False

# Test 3: Database Entry Verification
def test_database_entry():
    print_test("Database Entry Verification")
    print_info("Waiting 2 seconds for database write...")
    time.sleep(2)

    try:
        print_info(f"Querying trading_signals table for zone_id={TEST_ZONE_ID}")
        response = supabase.table("trading_signals") \
            .select("*") \
            .eq("zone_id", TEST_ZONE_ID) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        assert len(response.data) == 1, "Entry not found in database"
        entry = response.data[0]

        # Validate critical fields
        assert entry["symbol"] == "EURUSD", "Symbol mismatch"
        assert entry["side"] == "buy", "Side mismatch"
        assert entry["entry"] == 1.08500, "Entry price mismatch"
        assert entry["zone_type"] == "demand", "Zone type mismatch"
        print_pass("Critical fields validated")

        # Validate V7.1 features
        v7_features = [
            "score", "freshness", "session", "atr_ratio", "trend", "rsi",
            "htf_trend", "rvol", "adx", "touch_count", "base_quality",
            "departure_strength", "liquidity_distance", "liquidity_spread",
            "return_strength"
        ]

        missing_features = [f for f in v7_features if entry.get(f) is None]
        if missing_features:
            print_warn(f"Missing features: {missing_features}")
        else:
            print_pass("All 18 V7.1 features present")

        # Validate liquidity flags
        assert entry["liq_swept"] == True, "liq_swept flag mismatch"
        assert entry["target_swept"] == True, "target_swept flag mismatch"
        assert entry["caused_sweep"] == True, "caused_sweep flag mismatch"
        print_pass("Liquidity flags validated")

        print_pass(f"Entry verified in database: zone_id={entry['zone_id']}, created_at={entry['created_at']}")
        return True

    except Exception as e:
        print_fail(f"Database entry verification failed: {e}")
        traceback.print_exc()
        return False

# Test 4: Exit Webhook
def test_exit_webhook():
    print_test("Exit Webhook")

    payload = {
        "event_type": "exit",
        "passphrase": PASSPHRASE,
        "zone_id": TEST_ZONE_ID,
        "outcome": "win",
        "bars_held": 18,
        "close_price": 1.08700,
        "pnl_r": 2.0,
        "exit_type": "tp_hit",
        "mae_pips": 3.5,
        "close_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        print_info(f"Sending exit webhook for zone_id={TEST_ZONE_ID}")
        response = requests.post(
            f"{BASE_URL}/webhook/exit",
            json=payload,
            timeout=TIMEOUT
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        assert data.get("status") == "success", f"Status not success: {data.get('message')}"
        assert data.get("zone_id") == TEST_ZONE_ID, "Zone ID mismatch"
        assert data.get("outcome") == "win", "Outcome mismatch"

        print_pass(f"Exit webhook accepted")
        return True

    except Exception as e:
        print_fail(f"Exit webhook failed: {e}")
        if hasattr(e, 'response'):
            print_fail(f"Response: {e.response.text}")
        return False

# Test 5: Database Exit Verification
def test_database_exit():
    print_test("Database Exit Verification")
    print_info("Waiting 2 seconds for database write...")
    time.sleep(2)

    try:
        print_info(f"Querying trading_signals table for zone_id={TEST_ZONE_ID} with exit data")
        response = supabase.table("trading_signals") \
            .select("*") \
            .eq("zone_id", TEST_ZONE_ID) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        assert len(response.data) == 1, "Trade not found in database"
        trade_data = response.data[0]

        # Validate exit telemetry fields were updated
        assert trade_data["zone_id"] == TEST_ZONE_ID, "Zone ID mismatch"
        assert trade_data["outcome"] == "win", "Outcome mismatch"
        assert trade_data["bars_held"] == 18, "Bars held mismatch"
        assert trade_data["pnl_r"] == 2.0, "P&L mismatch"
        assert trade_data["exit_type"] == "tp_hit", "Exit type mismatch"
        assert trade_data["mae_pips"] == 3.5, "MAE mismatch"
        assert trade_data["status"] == "closed", "Status should be 'closed' after exit"

        print_pass(f"Exit verified in database: zone_id={trade_data['zone_id']}, outcome={trade_data['outcome']}")
        return True

    except Exception as e:
        print_fail(f"Database exit verification failed: {e}")
        traceback.print_exc()
        return False

# Test 6: Data Integrity Check
def test_data_integrity():
    print_test("Data Integrity (Entry + Exit in Same Record)")

    try:
        print_info("Fetching complete trade data (entry + exit)")
        response = supabase.table("trading_signals").select("*").eq("zone_id", TEST_ZONE_ID).execute()

        assert len(response.data) == 1, "Trade not found"
        trade = response.data[0]

        # Validate that both entry and exit data exist in the same record
        assert trade["zone_id"] == TEST_ZONE_ID, "Zone ID mismatch"
        print_pass("Trade found with correct zone_id")

        # Validate entry data exists
        assert trade["symbol"] == "EURUSD", "Entry symbol missing"
        assert trade["side"] == "buy", "Entry side missing"
        assert trade["entry"] == 1.085, "Entry price missing"
        print_pass("Entry data validated")

        # Validate exit data exists
        assert trade["outcome"] is not None, "Exit outcome missing"
        assert trade["close_price"] is not None, "Exit close_price missing"
        assert trade["close_time"] is not None, "Exit close_time missing"
        print_pass("Exit data validated")

        # Validate timestamps (close_time should be after created_at)
        entry_time = datetime.fromisoformat(trade["created_at"].replace('Z', '+00:00'))
        exit_time = datetime.fromisoformat(trade["close_time"].replace('Z', '+00:00'))
        assert exit_time >= entry_time, "Exit timestamp before entry timestamp"
        print_pass("Timestamps valid (exit after entry)")

        print_pass("Data integrity verified: Entry and Exit in same record")
        return True

    except Exception as e:
        print_fail(f"Data integrity check failed: {e}")
        traceback.print_exc()
        return False

# Test 7: Cleanup Test Data
def test_cleanup():
    print_test("Cleanup Test Data")

    try:
        print_info(f"Deleting test data for zone_id={TEST_ZONE_ID}")

        # Delete test trade (includes both entry and exit data)
        supabase.table("trading_signals").delete().eq("zone_id", TEST_ZONE_ID).execute()
        print_pass("Test trade deleted")

        # Verify deletion
        response = supabase.table("trading_signals").select("zone_id").eq("zone_id", TEST_ZONE_ID).execute()

        assert len(response.data) == 0, "Test trade not deleted"

        print_pass("Cleanup verified: Test data removed")
        return True

    except Exception as e:
        print_fail(f"Cleanup failed: {e}")
        traceback.print_exc()
        return False

# Main test runner with Discord integration
def run_all_tests():
    print("\n" + "="*70)
    print(f"{Colors.CYAN}{'🚀 TRADING SYSTEM E2E TEST SUITE':^70}{Colors.END}")
    print("="*70)
    print(f"Target:      {BASE_URL}")
    print(f"Time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'local')}")
    print("="*70)

    # Validate configuration
    if not PASSPHRASE or PASSPHRASE == "YOUR_WEBHOOK_PASSPHRASE":
        print_fail("WEBHOOK_PASSPHRASE not set or still using default")
        print_info("Set environment variable: export WEBHOOK_PASSPHRASE=your_passphrase")
        return 1

    if not DISCORD_WEBHOOK_URL:
        print_warn("DISCORD_WEBHOOK_URL not set, Discord notifications disabled")
        print_info("Set environment variable: export DISCORD_WEBHOOK_URL=your_webhook_url")

    # Send start notification
    send_test_start()

    start_time = time.time()

    tests = [
        ("Health Check", test_health_check),
        ("Entry Webhook", test_entry_webhook),
        ("Database Entry", test_database_entry),
        ("Exit Webhook", test_exit_webhook),
        ("Database Exit", test_database_exit),
        ("Data Integrity", test_data_integrity),
        ("Cleanup", test_cleanup),
    ]

    results = {}
    critical_failure = None

    for name, test_func in tests:
        try:
            results[name] = test_func()
            if not results[name] and name in ["Health Check", "Database Entry"]:
                critical_failure = (name, "Test failed - check logs for details")
        except Exception as e:
            print_fail(f"Test '{name}' crashed: {e}")
            traceback.print_exc()
            results[name] = False
            if name in ["Health Check", "Database Entry"]:
                critical_failure = (name, e)
        time.sleep(1)  # Pause between tests

    duration = time.time() - start_time

    # Summary
    print("\n" + "="*70)
    print(f"{Colors.CYAN}{'📊 TEST SUMMARY':^70}{Colors.END}")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status} - {name}")

    print("="*70)
    print(f"Result: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"Duration: {duration:.1f}s")
    print("="*70)

    # Send results notification
    send_test_results(results, duration)

    # Send critical failure alert if needed
    if critical_failure:
        send_critical_failure(critical_failure[0], critical_failure[1])

    if passed == total:
        print(f"\n{Colors.GREEN}✅ ALL TESTS PASSED - SYSTEM OPERATIONAL{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}❌ SOME TESTS FAILED - CHECK LOGS ABOVE{Colors.END}\n")
        return 1

if __name__ == "__main__":
    try:
        exit_code = run_all_tests()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test suite interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.END}")
        traceback.print_exc()
        sys.exit(1)
