#!/usr/bin/env python3
"""
Run backtest with EXACT TradingView Aggressive Profile settings.

This script matches the Pine script "Aggressive (Paper Trading)" profile settings
from SND_Strategy.pine lines 434-447.

Aggressive Profile Settings (XAUUSD):
- pvtMax: 10 (more liquidity levels)
- liq_pivot_len: 3 (faster pivot detection)
- liq_max_distance_pips_gold: 500.0
- liq_entry_max_dist: 100.0
- ai_quality_threshold: 50 (lower threshold = more trades)
- min_entry_grade: "C" (accept lower grades)
- min_return_strength: 0 (no return speed filter)
- risk_per_trade_pct: 0.5
- risk_reward_ratio: 1.5
- max_trades_per_day: 2
- min_tp_distance_pips: 5.0
- require_htf_flip: False (line 482)
- filter_dead_zone: True (line 480)
- filter_trading_hours: True (line 481)
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import BacktestConfig
from app.data import get_candles
from app.engine import BacktestEngine
from app.outputs import compute_summary, print_summary, write_trades_csv, write_equity_csv
from app.snd_strategy import SNDStrategy
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Run backtest with Aggressive Profile settings")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol (default: XAUUSD)")
    parser.add_argument("--from", dest="from_date", default="2025-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default="2026-02-10", help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="M5", help="Timeframe (default: M5)")
    parser.add_argument("--tv-trades", type=int, default=35, help="Expected TradingView trade count for comparison")
    parser.add_argument("--tv-profit", type=float, default=1030, help="Expected TradingView profit for comparison")
    parser.add_argument("--tv-winrate", type=float, default=57.14, help="Expected TradingView win rate for comparison")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    # Detect symbol type
    is_gold = "XAU" in args.symbol or "GOLD" in args.symbol
    is_index = any(x in args.symbol.upper() for x in ["NAS", "US100", "NDX", "SPX", "US500", "US30", "DJI"])

    # Load candles
    print(f"📊 Loading {args.symbol} {args.timeframe} data from {args.from_date} to {args.to_date}...")
    candles = get_candles(
        symbol=args.symbol,
        from_date=from_date,
        to_date=to_date,
        timeframe=args.timeframe,
        data_dir=Path("data/historical"),  # Use the fetched historical data
        metaapi_token=None,
        metaapi_account_id=None,
        symbol_aliases={},
        persist=False,
    )
    print(f"✅ Loaded {len(candles)} candles\n")

    # EXACT Aggressive Profile Configuration (Pine lines 434-447)
    cfg = BacktestConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        tick_size=0.01 if is_gold else 0.00001,
        pip_size=0.01 if is_gold else 0.0001,
        contract_size=100.0 if is_gold else 100000.0,
        start_date=from_date,
        end_date=to_date,

        # AGGRESSIVE PROFILE SETTINGS (exact match to Pine)
        config_profile="Aggressive (Paper Trading)",

        # Liquidity Detection (Pine 434-447)
        pvt_max=10,  # More liquidity levels
        liq_pivot_len=3,  # Faster pivots
        liq_max_distance_pips_forex=20.0,
        liq_max_distance_pips_gold=500.0,
        liq_max_distance_pips_index=5000.0,
        liq_entry_max_dist=100.0,  # Zone-to-liquidity max distance
        require_major_liquidity=False,  # Allow minor pivots (Pine 477: only Conservative/Balanced require major)

        # Quality Filters (Pine 440-442)
        ai_quality_threshold=50,  # Lower threshold = more trades
        min_entry_grade="C",  # Accept lower grades
        min_return_strength=0,  # No return speed filter
        enable_grade_filter=False,  # Pine 479: only Conservative/Balanced use grade filter

        # Risk Management (Pine 443-447)
        risk_per_trade_pct=0.5,
        risk_reward_ratio=1.5,
        use_custom_rr=False,  # Use SL-based RR (Pine 444 doesn't set custom)
        min_tp_distance_pips=5.0,
        stop_loss_buffer_pips=1.0,  # Pine 483

        # Trade Limits (Pine 446)
        enable_trade_limit=True,
        max_trades_per_day=2,

        # Entry Filters (Pine 480-482)
        require_htf_flip=False,  # Aggressive does NOT require HTF FLIP
        filter_dead_zone=True,  # Block xx:50-xx:00
        filter_trading_hours=True,  # 7-22 UTC
        trading_start_hour=7,
        trading_end_hour=22,

        # Structure Detection (Pine 478)
        structure_mode="Relaxed (Wicks)",  # Not Conservative, so use Relaxed

        # Zone Detection
        invalidate_on_wick=True,
        max_zones=20,
        min_body_perc=50.0,
        use_one_candle_liquidity=True,

        # Advanced
        use_break_even=False,
        max_bars_held=36,
        enable_double_tp=False,
        use_fvg_confirmation=False,
        enable_accuracy_zones=True,

        # Account
        account_size_usd=50000.0,
        initial_equity=50000.0,

        # Date filter
        enable_date_filter=True,
        min_bar_index_for_entries=100,  # Skip first 100 bars (Pine 395)
    )

    print(f"⚙️  AGGRESSIVE PROFILE SETTINGS:")
    print(f"   Profile: {cfg.config_profile}")
    print(f"   pvtMax: {cfg.pvt_max} (more liquidity levels)")
    print(f"   liq_pivot_len: {cfg.liq_pivot_len} (faster pivots)")
    print(f"   AI quality threshold: {cfg.ai_quality_threshold} (lower = more trades)")
    print(f"   Min entry grade: {cfg.min_entry_grade}")
    print(f"   Min return strength: {cfg.min_return_strength} (no filter)")
    print(f"   Risk/Reward: 1:{cfg.risk_reward_ratio} (SL-based)")
    print(f"   Max trades/day: {cfg.max_trades_per_day}")
    print(f"   Require HTF FLIP: {cfg.require_htf_flip}")
    print(f"   Filter dead zone: {cfg.filter_dead_zone}")
    print(f"   Trading hours: {cfg.trading_start_hour}:00 - {cfg.trading_end_hour}:00 UTC")
    print(f"   Liq entry max dist: {cfg.liq_entry_max_dist} pips")
    print(f"   Liq max distance (gold): {cfg.liq_max_distance_pips_gold} pips\n")

    # Run backtest
    print("🔄 Running backtest with EXACT Aggressive Profile...\n")

    engine = BacktestEngine(
        tick_size=cfg.tick_size,
        slippage_ticks=3,
        initial_equity=cfg.account_size_usd,
        max_bars_held=cfg.max_bars_held,
    )

    strategy = SNDStrategy(config=cfg)

    def on_bar(bar_idx: int, bar: pd.Series, history: pd.DataFrame, has_position: bool):
        return strategy.on_bar(bar_idx, bar, history, has_position)

    trades = engine.run(candles, on_bar)

    # Calculate summary
    summary = compute_summary(trades, engine.equity_curve)

    # Print results
    print_summary(summary)

    # Save to CSV
    out_dir = Path(f"data/backtest/{args.symbol}")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_trades_csv(trades, out_dir / "trades_aggressive.csv")
    write_equity_csv(engine.equity_curve, out_dir / "equity_aggressive.csv")
    print(f"\n💾 Saved trades to: {out_dir / 'trades_aggressive.csv'}")

    # Comparison with TradingView
    print(f"\n{'='*70}")
    print(f"📊 COMPARISON WITH TRADINGVIEW (AGGRESSIVE PROFILE)")
    print(f"{'='*70}")
    print(f"{'Metric':<25} {'This Backtest':>15} {'TradingView':>15} {'Match':>10}")
    print(f"{'-'*70}")
    print(f"{'Trades':<25} {len(trades):>15} {args.tv_trades:>15} {len(trades)/args.tv_trades*100:>9.0f}%")
    print(f"{'Net Profit':<25} ${summary.net_profit:>14,.2f} ${args.tv_profit:>14,.2f} {summary.net_profit/args.tv_profit*100 if args.tv_profit != 0 else 0:>9.0f}%")
    print(f"{'Win Rate':<25} {summary.win_rate:>14.1f}% {args.tv_winrate:>14.1f}% {summary.win_rate/args.tv_winrate*100:>9.0f}%")
    print(f"{'='*70}\n")

    # Diagnosis
    match_pct = len(trades) / args.tv_trades * 100 if args.tv_trades > 0 else 0
    if 90 <= match_pct <= 110 and summary.net_profit > 0:
        print("✅ EXCELLENT: Close match to TradingView! Aggressive profile configured correctly.\n")
    elif 70 <= match_pct <= 130:
        print("⚠️  GOOD: Reasonable match. Minor differences expected due to data source/timing.\n")
    elif len(trades) > args.tv_trades * 2:
        print("❌ WARNING: Too many trades. Possible issues:")
        print("   1. TradingView might be using different date range")
        print("   2. Data source differences (different candle data)")
        print("   3. Pine script settings may have been customized\n")
    else:
        print("❌ WARNING: Too few trades. Check:")
        print("   1. Date range matches TradingView")
        print("   2. Aggressive profile is selected in TradingView")
        print("   3. No manual overrides in Pine settings\n")

    # Additional stats
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    print("📈 Additional Statistics:")
    print(f"   Profit Factor: {summary.profit_factor:.2f}")
    print(f"   Max Drawdown: ${summary.max_drawdown:,.2f}")
    print(f"   Avg Win: ${avg_win:,.2f}")
    print(f"   Avg Loss: ${avg_loss:,.2f}")
    print(f"   Avg Bars Held: {summary.avg_bars_held:.1f}\n")

if __name__ == "__main__":
    main()
