"""
Trade Diagnostic Tool - Analyze why Python backtest differs from TradingView.

Performs deep analysis:
1. Entry price comparison (slippage check)
2. Stop loss placement analysis
3. Entry timing verification
4. Zone calculation validation
5. Quick stop-out analysis

Usage:
  python -m app.trade_diagnostic --symbol XAUUSD --from 2026-01-01 --to 2026-01-10
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def analyze_quick_stopouts(trades: pd.DataFrame) -> None:
    """Analyze trades that stopped out within 1-3 bars."""
    quick_stops = trades[(trades["reason"] == "stop") & (trades["bars_held"] <= 3)]

    if len(quick_stops) == 0:
        print("✅ No quick stop-outs detected")
        return

    print(f"\n⚠️  QUICK STOP-OUTS: {len(quick_stops)} / {len(trades)} trades ({len(quick_stops)/len(trades)*100:.1f}%)")
    print("=" * 80)

    for idx, t in quick_stops.head(10).iterrows():
        side = t["side"]
        entry = t["entry_price"]
        stop = t["stop_price"]
        exit_price = t["exit_price"]
        bars = t["bars_held"]
        model = t.get("entry_model", "?")

        # Calculate distances
        sl_distance = abs(entry - stop)
        sl_pips = sl_distance / 0.01  # Assuming XAUUSD pip = 0.01

        print(f"\nTrade: {side.upper()} {model}")
        print(f"  Entry: ${entry:.2f} | SL: ${stop:.2f} | Exit: ${exit_price:.2f}")
        print(f"  SL Distance: {sl_pips:.1f} pips | Bars held: {bars}")
        print(f"  Zone: ${t.get('zone_bottom', 0):.2f} - ${t.get('zone_top', 0):.2f}")

        # Diagnose issue
        if sl_pips < 5:
            print(f"  ❌ ISSUE: SL too tight ({sl_pips:.1f} pips)")
        if side == "long" and entry < stop:
            print(f"  ❌ ISSUE: Long SL above entry (should be below)")
        if side == "short" and entry > stop:
            print(f"  ❌ ISSUE: Short SL below entry (should be above)")

        # Check if entry is outside zone
        zb, zt = t.get("zone_bottom"), t.get("zone_top")
        if pd.notna(zb) and pd.notna(zt):
            if side == "long" and entry < zb:
                print(f"  ❌ ISSUE: Long entry BELOW demand zone (entry: ${entry:.2f}, zone bottom: ${zb:.2f})")
            elif side == "short" and entry > zt:
                print(f"  ❌ ISSUE: Short entry ABOVE supply zone (entry: ${entry:.2f}, zone top: ${zt:.2f})")


def analyze_entry_prices(trades: pd.DataFrame) -> None:
    """Analyze entry price patterns and slippage."""
    print("\n📊 ENTRY PRICE ANALYSIS")
    print("=" * 80)

    for side in ["long", "short"]:
        side_trades = trades[trades["side"] == side]
        if len(side_trades) == 0:
            continue

        avg_entry = side_trades["entry_price"].mean()
        avg_zone_bottom = side_trades["zone_bottom"].mean()
        avg_zone_top = side_trades["zone_top"].mean()

        print(f"\n{side.upper()} trades ({len(side_trades)}):")
        print(f"  Avg entry price: ${avg_entry:.2f}")
        print(f"  Avg zone bottom: ${avg_zone_bottom:.2f}")
        print(f"  Avg zone top: ${avg_zone_top:.2f}")

        # Check if entries are consistently outside zones
        if side == "long":
            outside = side_trades[side_trades["entry_price"] < side_trades["zone_bottom"]]
            if len(outside) > 0:
                print(f"  ⚠️  {len(outside)} entries BELOW demand zone")
        else:
            outside = side_trades[side_trades["entry_price"] > side_trades["zone_top"]]
            if len(outside) > 0:
                print(f"  ⚠️  {len(outside)} entries ABOVE supply zone")


def analyze_stop_losses(trades: pd.DataFrame) -> None:
    """Analyze stop loss placement patterns."""
    print("\n🛑 STOP LOSS ANALYSIS")
    print("=" * 80)

    for side in ["long", "short"]:
        side_trades = trades[trades["side"] == side]
        if len(side_trades) == 0:
            continue

        # Calculate SL distances in pips
        sl_distances = []
        for _, t in side_trades.iterrows():
            dist = abs(t["entry_price"] - t["stop_price"]) / 0.01
            sl_distances.append(dist)

        avg_sl = sum(sl_distances) / len(sl_distances) if sl_distances else 0
        min_sl = min(sl_distances) if sl_distances else 0
        max_sl = max(sl_distances) if sl_distances else 0

        print(f"\n{side.upper()} SL distances:")
        print(f"  Avg: {avg_sl:.1f} pips")
        print(f"  Min: {min_sl:.1f} pips")
        print(f"  Max: {max_sl:.1f} pips")

        if avg_sl < 10:
            print(f"  ❌ CRITICAL: Avg SL is very tight ({avg_sl:.1f} pips) - likely to get stopped out")


def analyze_entry_models(trades: pd.DataFrame) -> None:
    """Analyze performance by entry model."""
    print("\n🎯 ENTRY MODEL PERFORMANCE")
    print("=" * 80)

    models = trades["entry_model"].unique()
    for model in models:
        model_trades = trades[trades["entry_model"] == model]
        wins = model_trades[model_trades["pnl"] > 0]
        losses = model_trades[model_trades["pnl"] <= 0]

        win_rate = len(wins) / len(model_trades) * 100 if len(model_trades) > 0 else 0
        net_pnl = model_trades["pnl"].sum()
        avg_bars = model_trades["bars_held"].mean()

        print(f"\n{model}:")
        print(f"  Total: {len(model_trades)} | Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"  Net P&L: ${net_pnl:.2f}")
        print(f"  Avg bars held: {avg_bars:.1f}")

        # Check for quick stops
        quick = model_trades[(model_trades["reason"] == "stop") & (model_trades["bars_held"] <= 2)]
        if len(quick) > 0:
            print(f"  ⚠️  {len(quick)} quick stop-outs (≤2 bars)")


def analyze_time_based_exits(trades: pd.DataFrame) -> None:
    """Analyze time-based exits (max bars held)."""
    time_exits = trades[trades["reason"] == "time"]

    print("\n⏰ TIME-BASED EXITS")
    print("=" * 80)

    if len(time_exits) == 0:
        print("None (all trades exited via SL/TP)")
        return

    print(f"Total: {len(time_exits)} / {len(trades)} ({len(time_exits)/len(trades)*100:.1f}%)")
    avg_pnl = time_exits["pnl"].mean()
    print(f"Avg P&L: ${avg_pnl:.2f}")

    if avg_pnl < 0:
        print("⚠️  Time exits are mostly losses - consider adjusting max_bars_held or TP levels")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic tool for backtest analysis")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest"))
    args = parser.parse_args()

    # Load trades
    trades_path = args.output_dir / args.symbol / "trades.csv"
    if not trades_path.exists():
        print(f"❌ No trades found at {trades_path}")
        print("Run backtest first: python -m app.backtest_run --from 2026-01-01 --to 2026-02-10")
        return

    trades = pd.read_csv(trades_path)
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    trades["exit_time"] = pd.to_datetime(trades["exit_time"])

    # Filter to date range
    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, tzinfo=timezone.utc)
    trades = trades[(trades["entry_time"] >= from_date) & (trades["entry_time"] <= to_date)]

    print(f"\n{'='*80}")
    print(f"BACKTEST DIAGNOSTIC REPORT - {args.symbol}")
    print(f"{args.from_date} to {args.to_date}")
    print(f"{'='*80}")

    # Run diagnostics
    analyze_quick_stopouts(trades)
    analyze_entry_prices(trades)
    analyze_stop_losses(trades)
    analyze_entry_models(trades)
    analyze_time_based_exits(trades)

    # Summary
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")

    quick_stops = trades[(trades["reason"] == "stop") & (trades["bars_held"] <= 3)]
    if len(quick_stops) / len(trades) > 0.5:
        print("❌ Over 50% of trades are quick stop-outs. Check:")
        print("   1. Stop loss buffer (should be 1-2 pips minimum)")
        print("   2. Entry price calculation (might have excessive slippage)")
        print("   3. Zone calculation (entries might be outside zones)")

    avg_sl_pips = []
    for _, t in trades.iterrows():
        avg_sl_pips.append(abs(t["entry_price"] - t["stop_price"]) / 0.01)
    avg_sl = sum(avg_sl_pips) / len(avg_sl_pips) if avg_sl_pips else 0

    if avg_sl < 10:
        print(f"❌ Average SL is very tight ({avg_sl:.1f} pips). Consider:")
        print("   1. Increasing stop_loss_buffer_pips in config")
        print("   2. Checking zone size calculation")

    win_rate = len(trades[trades["pnl"] > 0]) / len(trades) * 100 if len(trades) > 0 else 0
    if win_rate < 30:
        print(f"❌ Low win rate ({win_rate:.1f}%). This suggests:")
        print("   1. Entry logic might differ from TradingView Pine")
        print("   2. Zone creation might be different")
        print("   3. Entry models (FLIP/BOC/DIR_CLOSE) might not match Pine")


if __name__ == "__main__":
    main()
