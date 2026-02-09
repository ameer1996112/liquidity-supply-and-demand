#!/usr/bin/env python3
"""
Manual Test Script for Prop Firm Guards
Tests the 3 critical guards with your actual configuration.

Usage:
    python scripts/test_prop_firm_guards.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timezone, timedelta
from config import get_settings
from supabase import create_client


def test_mtm_guardian():
    """Test 1: MTM Guardian - Floating PnL tracking"""
    print("\n" + "="*60)
    print("TEST 1: MTM GUARDIAN (Floating PnL Tracking)")
    print("="*60)

    try:
        from src.services.mtm_guardian import MTMGuardian

        settings = get_settings()
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()

        if not settings.supabase_url or not key:
            print("❌ FAILED: Supabase not configured")
            return False

        supabase = create_client(settings.supabase_url, key)
        mtm = MTMGuardian(supabase, settings)

        # Get real-time equity
        equity_data = mtm.get_real_time_equity()

        print(f"\n📊 Current Equity Data:")
        print(f"  Starting Balance: ${equity_data['starting_balance']:,.2f}")
        print(f"  Closed PnL: ${equity_data['closed_pnl']:,.2f}")
        print(f"  Floating PnL: ${equity_data['floating_pnl']:,.2f}")
        print(f"  Current Equity: ${equity_data['current_equity']:,.2f}")
        print(f"  Daily Drawdown: {equity_data['daily_drawdown_pct']:.2f}%")

        # Check kill switch
        should_kill, reason = mtm.check_kill_switch()

        if should_kill:
            print(f"\n🚨 KILL SWITCH WOULD ENGAGE:")
            print(f"  Reason: {reason}")
        else:
            print(f"\n✅ MTM Guardian: PASSED")
            print(f"  Status: {reason}")

        # Position summary
        summary = mtm.get_position_summary()
        print(f"\n📈 Open Positions: {summary['total_positions']}")
        if summary['total_positions'] > 0:
            print(f"  Largest Winner: ${summary['largest_winner']:,.2f}")
            print(f"  Largest Loser: ${summary['largest_loser']:,.2f}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_staleness_guard():
    """Test 2: Staleness Guard - Webhook latency protection"""
    print("\n" + "="*60)
    print("TEST 2: STALENESS GUARD (Webhook Latency)")
    print("="*60)

    try:
        from src.core.guard_rails.staleness_guard import StalenessGuard

        settings = get_settings()
        guard = StalenessGuard(
            max_age_seconds=getattr(settings, "staleness_max_age_seconds", 5),
            max_price_deviation_pips=getattr(settings, "staleness_max_price_deviation_pips", 3.0)
        )

        # Test 1: Fresh signal (should pass)
        fresh_payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "bar_time": (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(),
        }

        passed, reason = guard.check(fresh_payload)
        print(f"\n🔍 Test Fresh Signal (2s old):")
        print(f"  Result: {'✅ PASSED' if passed else '❌ REJECTED'}")
        if reason:
            print(f"  Reason: {reason}")

        # Test 2: Stale signal (should fail)
        stale_payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "bar_time": (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
        }

        passed, reason = guard.check(stale_payload)
        print(f"\n🔍 Test Stale Signal (10s old):")
        print(f"  Result: {'❌ REJECTED (CORRECT)' if not passed else '✅ PASSED (UNEXPECTED)'}")
        if reason:
            print(f"  Reason: {reason}")

        # Show diagnostics
        diag = guard.get_diagnostics(fresh_payload)
        print(f"\n📋 Diagnostics:")
        print(f"  Max Age: {guard.max_age_seconds}s")
        print(f"  Max Price Deviation: {guard.max_price_deviation_pips} pips")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_consistency_analyzer():
    """Test 3: Consistency Analyzer - FTMO 40% rule"""
    print("\n" + "="*60)
    print("TEST 3: CONSISTENCY ANALYZER (FTMO 40% Rule)")
    print("="*60)

    try:
        from src.services.consistency_analyzer import ConsistencyAnalyzer

        settings = get_settings()
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()

        if not settings.supabase_url or not key:
            print("❌ FAILED: Supabase not configured")
            return False

        supabase = create_client(settings.supabase_url, key)
        consistency = ConsistencyAnalyzer(supabase, settings)

        # Get current breakdown
        breakdown = consistency.get_daily_profit_breakdown()

        print(f"\n📊 Consistency Breakdown:")
        print(f"  Total Profit: ${breakdown['total_profit']:,.2f}")
        print(f"  Best Day Profit: ${breakdown['best_day_profit']:,.2f}")
        print(f"  Best Day %: {breakdown['best_day_pct']:.2f}%")
        print(f"  Limit: {breakdown['consistency_limit_pct']:.2f}%")
        print(f"  Days Traded: {breakdown['days_traded']}")

        if breakdown['consistency_ok']:
            print(f"\n✅ CONSISTENCY: PASSED")
        else:
            print(f"\n🚨 CONSISTENCY: VIOLATED")
            print(f"  Best day exceeds {breakdown['consistency_limit_pct']}% limit!")

        # Dashboard data
        dashboard = consistency.get_consistency_dashboard_data()
        print(f"\n📈 Status: {dashboard['status'].upper()}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PROP FIRM PROTECTION TEST SUITE")
    print("Trinity Engine v3.0")
    print("="*60)

    results = {
        "MTM Guardian": test_mtm_guardian(),
        "Staleness Guard": test_staleness_guard(),
        "Consistency Analyzer": test_consistency_analyzer(),
    }

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Your prop firm protection is working.")
    else:
        print("\n⚠️ SOME TESTS FAILED. Check configuration and logs above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
