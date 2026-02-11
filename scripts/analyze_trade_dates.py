#!/usr/bin/env python3
"""
Analyze trade distribution to identify TradingView's date range.

This script helps you figure out what date range TradingView is actually using
by showing trade counts per day/week/month.
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    # Load aggressive profile backtest results
    trades_file = Path("data/backtest/XAUUSD/trades_aggressive.csv")

    if not trades_file.exists():
        print(f"❌ Trades file not found: {trades_file}")
        print("Run the backtest first: python scripts/backtest_aggressive_profile.py")
        return

    df = pd.read_csv(trades_file)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["entry_date"] = df["entry_time"].dt.date
    df["entry_month"] = df["entry_time"].dt.to_period("M")
    df["entry_week"] = df["entry_time"].dt.to_period("W")

    total_trades = len(df)
    print(f"📊 TRADE DATE DISTRIBUTION ANALYSIS")
    print(f"{'='*70}\n")
    print(f"Total Trades: {total_trades}")
    print(f"Date Range: {df['entry_date'].min()} to {df['entry_date'].max()}")
    print(f"Duration: {(df['entry_date'].max() - df['entry_date'].min()).days} days\n")

    # Monthly distribution
    print(f"{'='*70}")
    print(f"MONTHLY BREAKDOWN")
    print(f"{'='*70}")
    monthly = df.groupby("entry_month").size().sort_index()
    for month, count in monthly.items():
        pct = count / total_trades * 100
        bar = "█" * int(pct / 2)
        print(f"{month}  {count:>3} trades ({pct:>5.1f}%) {bar}")

    # Weekly distribution (last 8 weeks for detail)
    print(f"\n{'='*70}")
    print(f"RECENT WEEKS (Last 8 weeks)")
    print(f"{'='*70}")
    weekly = df.groupby("entry_week").size().sort_index().tail(8)
    for week, count in weekly.items():
        pct = count / total_trades * 100
        bar = "█" * min(int(pct / 2), 30)
        print(f"{week}  {count:>3} trades ({pct:>5.1f}%) {bar}")

    # Daily distribution (last 30 days for detail)
    print(f"\n{'='*70}")
    print(f"RECENT DAYS (Last 30 days)")
    print(f"{'='*70}")
    daily = df.groupby("entry_date").size().sort_index().tail(30)
    for date, count in daily.items():
        pct = count / total_trades * 100
        bar = "█" * min(int(pct * 5), 30)
        print(f"{date}  {count:>2} trades ({pct:>4.1f}%) {bar}")

    # Identify potential TradingView date ranges
    print(f"\n{'='*70}")
    print(f"🎯 POTENTIAL TRADINGVIEW DATE RANGES")
    print(f"{'='*70}\n")

    # If TradingView has 35 trades, find windows with ~35 trades
    target_trades = 35

    # Check last N days
    for days in [7, 14, 21, 30, 60, 90]:
        cutoff_date = df['entry_date'].max() - pd.Timedelta(days=days)
        recent_trades = df[df['entry_date'] > cutoff_date]
        count = len(recent_trades)
        match_pct = abs(count - target_trades) / target_trades * 100

        if match_pct < 20:  # Within 20% of target
            emoji = "✅" if match_pct < 10 else "⚠️"
            print(f"{emoji} Last {days:>2} days: {count:>3} trades (Match: {100-match_pct:>5.1f}%)")
            print(f"   Date range: {recent_trades['entry_date'].min()} to {recent_trades['entry_date'].max()}")
        elif days <= 30:
            print(f"   Last {days:>2} days: {count:>3} trades (off by {match_pct:>5.1f}%)")

    # Check specific months
    print(f"\n📅 BY MONTH:")
    for month, count in monthly.tail(3).items():
        match_pct = abs(count - target_trades) / target_trades * 100
        emoji = "✅" if match_pct < 10 else "⚠️" if match_pct < 20 else "  "
        print(f"{emoji} {month}: {count:>3} trades (Match: {100-match_pct:>5.1f}%)")

    # Show win rate by month
    print(f"\n{'='*70}")
    print(f"WIN RATE BY MONTH")
    print(f"{'='*70}")
    for month in df["entry_month"].unique():
        month_df = df[df["entry_month"] == month]
        wins = (month_df["pnl"] > 0).sum()
        losses = (month_df["pnl"] < 0).sum()
        win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        print(f"{month}: {wins}W / {losses}L = {win_rate:>5.1f}% win rate")

    print(f"\n{'='*70}")
    print(f"💡 RECOMMENDATION")
    print(f"{'='*70}\n")
    print("Check your TradingView strategy settings:")
    print("1. Open the strategy settings panel")
    print("2. Go to '🎯 Quick Setup'")
    print("3. Check 'Enable Date Range Filter' and note the dates")
    print("4. If using default dates, TradingView might be showing:")
    print("   - Full range: 01 Jan 2023 - 19 Jan 2026 (Pine default)")
    print("   - Or a custom range you configured")
    print("\nThen re-run backtest with matching dates:")
    print("python scripts/backtest_aggressive_profile.py \\")
    print("  --from YYYY-MM-DD --to YYYY-MM-DD\n")

if __name__ == "__main__":
    main()
