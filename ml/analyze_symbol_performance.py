#!/usr/bin/env python3
"""
Analyze per-symbol performance from training data to identify profitable pairs.
Helps you decide which symbols to whitelist and which to filter out.
"""
import pandas as pd
import numpy as np
from pathlib import Path

def analyze_symbols(data_path="ml/training_data.csv"):
    """Analyze performance by symbol."""
    print("=" * 80)
    print("📊 PER-SYMBOL PERFORMANCE ANALYSIS")
    print("=" * 80)
    print()

    df = pd.read_csv(data_path)

    # Check if we have symbol data
    # We need to extract symbol from the original backtest files since training_data.csv
    # doesn't have symbol column
    print("⚠️  NOTE: training_data.csv doesn't contain symbol information.")
    print("   We need to analyze the original backtest files.")
    print()

    # Analyze combined data first
    total_trades = len(df)
    total_wins = df['outcome'].sum()
    total_losses = total_trades - total_wins
    win_rate = total_wins / total_trades

    print(f"📈 COMBINED (ALL SYMBOLS):")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {total_wins} ({win_rate:.1%})")
    print(f"   Losses: {total_losses} ({(1-win_rate):.1%})")
    print()

    # Calculate expected value at different R:R ratios
    print("💰 Expected Value by R:R Ratio:")
    for rr in [1.5, 2.0, 2.5, 3.0]:
        ev = (win_rate * rr) - ((1 - win_rate) * 1)
        status = "✅ PROFITABLE" if ev > 0 else "❌ UNPROFITABLE"
        print(f"   R:R {rr}:1 → EV = {ev:+.3f} {status}")
    print()

    print("=" * 80)
    print("🔍 ANALYZING INDIVIDUAL SYMBOLS")
    print("=" * 80)
    print()
    print("To analyze individual symbols, we need to:")
    print("1. Re-parse the original backtest CSV files")
    print("2. Extract symbol from filename or Symbol column")
    print("3. Calculate per-symbol win rate and profitability")
    print()

    return df


def analyze_from_backtests(backtest_dir="~/Downloads"):
    """Analyze performance directly from individual backtest files."""
    import glob
    import re

    backtest_dir = Path(backtest_dir).expanduser()
    files = glob.glob(str(backtest_dir / "backtest_*.csv"))

    if not files:
        print(f"❌ No backtest files found in {backtest_dir}")
        print("   Expected: backtest_xauusd.csv, backtest_gbpjpy.csv, etc.")
        return

    print("=" * 80)
    print("📊 PER-SYMBOL PERFORMANCE ANALYSIS (from original backtests)")
    print("=" * 80)
    print()

    results = []

    for file_path in sorted(files):
        # Extract symbol from filename
        filename = Path(file_path).stem  # backtest_xauusd
        symbol = filename.replace("backtest_", "").upper()

        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig', on_bad_lines='skip')

            # Count entry rows only (skip exit rows)
            entry_rows = df[df['Type'].str.contains('Entry', case=False, na=False)]

            total_trades = len(entry_rows)
            if total_trades == 0:
                continue

            # Determine wins/losses from Net P&L
            try:
                pnl_col = None
                for col in ['Net P&L USD', 'Net P&L %', 'Profit', 'P&L']:
                    if col in entry_rows.columns:
                        pnl_col = col
                        break

                if pnl_col:
                    if '%' in pnl_col:
                        # Percentage column - parse percentage
                        pnl = entry_rows[pnl_col].astype(str).str.replace('%', '').astype(float)
                    else:
                        pnl = entry_rows[pnl_col]

                    wins = (pnl > 0).sum()
                    losses = (pnl <= 0).sum()
                    win_rate = wins / total_trades
                else:
                    # Can't determine P&L
                    wins = 0
                    losses = 0
                    win_rate = 0.0
            except:
                wins = 0
                losses = 0
                win_rate = 0.0

            # Calculate EV at different R:R ratios
            ev_2to1 = (win_rate * 2) - ((1 - win_rate) * 1)
            ev_3to1 = (win_rate * 3) - ((1 - win_rate) * 1)

            profitable_2to1 = ev_2to1 > 0
            profitable_3to1 = ev_3to1 > 0

            results.append({
                'symbol': symbol,
                'trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'ev_2to1': ev_2to1,
                'ev_3to1': ev_3to1,
                'profitable_2to1': profitable_2to1,
                'profitable_3to1': profitable_3to1,
            })

        except Exception as e:
            print(f"⚠️  Error parsing {filename}: {e}")
            continue

    if not results:
        print("❌ No valid backtest data found")
        return

    # Create DataFrame and sort by profitability
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('ev_2to1', ascending=False)

    print(f"\nFound {len(df_results)} symbols with backtest data:\n")

    print("Symbol    | Trades | Win Rate | EV (2:1) | EV (3:1) | Profitable?")
    print("-" * 80)
    for _, row in df_results.iterrows():
        status_2to1 = "✅ YES" if row['profitable_2to1'] else "❌ NO"
        status_3to1 = "✅ YES" if row['profitable_3to1'] else "❌ NO"

        print(f"{row['symbol']:10s} | {row['trades']:6d} | {row['win_rate']:7.1%} | "
              f"{row['ev_2to1']:+7.3f} {status_2to1:6s} | {row['ev_3to1']:+7.3f} {status_3to1}")

    print()
    print("=" * 80)
    print("📋 RECOMMENDATIONS")
    print("=" * 80)
    print()

    # Profitable at 2:1
    profitable_2to1 = df_results[df_results['profitable_2to1']]
    if len(profitable_2to1) > 0:
        print("✅ WHITELIST (Profitable at 2:1 R:R):")
        for symbol in profitable_2to1['symbol']:
            print(f"   - {symbol}")
        print()
    else:
        print("❌ No symbols profitable at 2:1 R:R")
        print()

    # Unprofitable at 2:1
    unprofitable_2to1 = df_results[~df_results['profitable_2to1']]
    if len(unprofitable_2to1) > 0:
        print("❌ BLACKLIST (Unprofitable at 2:1 R:R):")
        for symbol in unprofitable_2to1['symbol']:
            print(f"   - {symbol}")
        print()

    # Additional insights
    print("💡 INSIGHTS:")
    if len(profitable_2to1) > 0:
        best = df_results.iloc[0]
        print(f"   📈 Best performer: {best['symbol']} ({best['win_rate']:.1%} WR, EV={best['ev_2to1']:+.3f})")

    if len(unprofitable_2to1) > 0:
        worst = df_results.iloc[-1]
        print(f"   📉 Worst performer: {worst['symbol']} ({worst['win_rate']:.1%} WR, EV={worst['ev_2to1']:+.3f})")

    avg_win_rate = df_results['win_rate'].mean()
    print(f"   📊 Average win rate: {avg_win_rate:.1%}")

    print()
    print("=" * 80)
    print("🚀 NEXT STEPS")
    print("=" * 80)
    print()
    print("1. **Use symbol-specific parameters in Pine Script**")
    print("   - See SYMBOL_OPTIMIZATION_GUIDE.md")
    print("   - Optimize unprofitable symbols or exclude them")
    print()
    print("2. **Add symbol whitelist to backend**")
    print("   - Update src/worker.py with PROFITABLE_SYMBOLS list")
    print("   - Only trade symbols with EV > 0")
    print()
    print("3. **Train per-symbol AI models**")
    print("   - Separate model for each profitable symbol")
    print("   - Can improve ROC-AUC from 0.55 to 0.65-0.75")
    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--from-backtests":
        analyze_from_backtests()
    else:
        print("Usage:")
        print("  python ml/analyze_symbol_performance.py --from-backtests")
        print()
        print("This will analyze ~/Downloads/backtest_*.csv files")
        print("and show which symbols are profitable.")
        print()
        analyze_from_backtests()
