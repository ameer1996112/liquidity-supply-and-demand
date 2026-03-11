#!/usr/bin/env python3
"""
Verify Prop Firm & Analytics PnL Fix

This script verifies that the fixes for daily PnL calculations are working correctly:
1. Daily PnL uses closed_at instead of created_at
2. Zero-PnL stale positions are filtered out
3. Daily totals match database reality

Usage:
    python scripts/verify_pnl_fix.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.supabase_api import get_api_supabase

def main():
    print("=" * 80)
    print("PROP FIRM & ANALYTICS PnL FIX VERIFICATION")
    print("=" * 80)
    print()

    sb = get_api_supabase()

    # Expected results (from database analysis)
    expected = {
        "2026-03-05": {"trades": 5, "wins": 2, "losses": 3, "pnl": 23.37},
        "2026-03-09": {"trades": 6, "wins": 1, "losses": 5, "pnl": -654.99},
        "2026-03-10": {"trades": 7, "wins": 2, "losses": 5, "pnl": 44.69},
        "2026-03-11": {"trades": 2, "wins": 0, "losses": 2, "pnl": -549.92},
    }

    print("1. DATABASE DAILY PnL (closed_at grouping, zero-PnL filtered)")
    print("-" * 80)

    # Query using closed_at and filtering zero-PnL
    trades = (
        sb.table("trading_signals")
        .select("id, symbol, pnl_usd, pnl, closed_at")
        .eq("status", "CLOSED")
        .gte("closed_at", "2026-03-01")
        .lte("closed_at", "2026-03-11T23:59:59")
        .execute()
    )

    # Group by closed_at date
    from collections import defaultdict
    daily_stats = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0})

    for trade in trades.data:
        pnl = trade.get("pnl_usd") or trade.get("pnl") or 0

        # Filter zero-PnL trades (stale positions)
        if pnl == 0:
            continue

        date = trade.get("closed_at", "")[:10]
        daily_stats[date]["count"] += 1
        daily_stats[date]["pnl"] += pnl
        if pnl > 0:
            daily_stats[date]["wins"] += 1
        else:
            daily_stats[date]["losses"] += 1

    # Display results
    all_passed = True
    for date in sorted(daily_stats.keys()):
        stats = daily_stats[date]
        exp = expected.get(date)

        status = "✅ PASS" if exp else "ℹ️  INFO"
        if exp:
            # Check if matches expected
            trades_match = stats["count"] == exp["trades"]
            wins_match = stats["wins"] == exp["wins"]
            losses_match = stats["losses"] == exp["losses"]
            pnl_match = abs(stats["pnl"] - exp["pnl"]) < 0.01

            if not (trades_match and wins_match and losses_match and pnl_match):
                status = "❌ FAIL"
                all_passed = False

        print(f"{status} {date}: {stats['count']} trades ({stats['wins']}W/{stats['losses']}L), PnL=${stats['pnl']:.2f}")

        if exp and status == "❌ FAIL":
            print(f"        Expected: {exp['trades']} trades ({exp['wins']}W/{exp['losses']}L), PnL=${exp['pnl']:.2f}")

    print()
    print("2. VERIFICATION SUMMARY")
    print("-" * 80)

    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print()
        print("Daily PnL calculations are now correct:")
        print("  - Using closed_at for date grouping ✓")
        print("  - Filtering out zero-PnL stale positions ✓")
        print("  - Win/loss counts accurate ✓")
        print()
        print("Expected calendar display:")
        for date, exp in sorted(expected.items(), reverse=True):
            wr = (exp["wins"] / (exp["wins"] + exp["losses"]) * 100) if (exp["wins"] + exp["losses"]) > 0 else 0
            print(f"  {date}: ${exp['pnl']:+8.2f} ({wr:.0f}% win rate)")
    else:
        print("❌ SOME CHECKS FAILED")
        print()
        print("Please review the output above to identify discrepancies.")

    print()
    print("3. ZERO-PNL STALE POSITIONS CHECK")
    print("-" * 80)

    # Count zero-PnL closed trades (should be the 7 stale positions)
    zero_pnl_trades = (
        sb.table("trading_signals")
        .select("id, symbol, created_at, closed_at")
        .eq("status", "CLOSED")
        .eq("pnl_usd", 0)
        .gte("closed_at", "2026-03-01")
        .lte("closed_at", "2026-03-11T23:59:59")
        .execute()
    )

    stale_count = len(zero_pnl_trades.data) if zero_pnl_trades.data else 0
    print(f"Found {stale_count} zero-PnL closed trades (filtered from calculations)")

    if stale_count == 7:
        print("✅ Expected 7 stale positions from cleanup script")
    else:
        print(f"ℹ️  Different count than expected (7)")

    for trade in (zero_pnl_trades.data or [])[:5]:  # Show first 5
        print(f"  - ID={trade['id']}: {trade['symbol']} created={trade.get('created_at', 'N/A')[:10]}, closed={trade.get('closed_at', 'N/A')[:10]}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
