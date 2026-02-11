#!/usr/bin/env python3
"""
Run backtest with EXACT TradingView Aggressive Profile settings.

Aggressive Profile (from Pine Script lines 434-447):
- pvtMax = 10 (more liquidity lines)
- liq_pivot_len = 3 (more sensitive pivots)
- liq_max_distance_pips_gold = 500.0 (looser filters)
- liq_entry_max_dist = 100.0 (allow further zones)
- ai_quality_threshold = 50 (lower bar)
- min_entry_grade = "C" (accept lower grades)
- min_return_strength = 0 (no return speed filter)
- max_trades_per_day = 2
- min_tp_distance_pips = 5.0
- require_htf_flip = False (Aggressive doesn't require it)
- filter_dead_zone = True
- filter_trading_hours = True (7-22 UTC)
- risk_reward_ratio = 1.5 (or SL-based for gold)
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
    parser = argparse.ArgumentParser(description="Run Aggressive Profile backtest (exact TV match)")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol (default: XAUUSD)")
    parser.add_argument("--from", dest="from_date", default="2025-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default="2026-02-10", help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="M5", help="Timeframe (default: M5)")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    # Load candles
    print(f"📊 Loading {args.symbol} {args.timeframe} data from {args.from_date} to {args.to_date}...")
    candles = get_candles(
        symbol=args.symbol,
        from_date=from_date,
        to_date=to_date,
        timeframe=args.timeframe,
        data_dir=Path("data/backtest_candles"),
        metaapi_token=None,
        metaapi_account_id=None,
        symbol_aliases={},
        persist=False,
    )
    print(f"✅ Loaded {len(candles)} candles\n")

    # ⚡ AGGRESSIVE PROFILE - EXACT MATCH TO PINE SCRIPT
    cfg = BacktestConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        tick_size=0.01,
        pip_size=0.01,
        start_date=from_date,
        end_date=to_date,

        # === AGGRESSIVE PROFILE SETTINGS ===
        # Lines 434-447 in SND_Strategy.pine
        pvt_max=10,                                    # ← Pine: pvtMax := 10
        liq_pivot_len=3,                               # ← Pine: liq_pivot_len := 3
        liq_max_distance_pips_gold=500.0,              # ← Pine: liq_max_distance_pips_gold := 500.0
        liq_entry_max_dist=100.0,                      # ← Pine: liq_entry_max_dist := 100.0
        ai_quality_threshold=50,                       # ← Pine: ai_quality_threshold := 50
        min_entry_grade="C",                           # ← Pine: min_entry_grade := "C"
        min_return_strength=0,                         # ← Pine: min_return_strength := 0
        max_trades_per_day=2,                          # ← Pine: max_trades_per_day := 2
        min_tp_distance_pips=5.0,                      # ← Pine: min_tp_distance_pips := 5.0
        risk_reward_ratio=1.5,                         # ← Pine: risk_reward_ratio := 1.5
        risk_per_trade_pct=0.5,                        # ← Pine: risk_per_trade_pct := 0.5

        # Lines 476-483: Common settings
        require_htf_flip=False,                        # ← Pine: require_htf_flip := is_conservative or is_balanced (NOT Aggressive)
        filter_dead_zone=True,                         # ← Pine: filter_dead_zone := ... or is_aggressive
        filter_trading_hours=True,                     # ← Pine: filter_trading_hours := ... or is_aggressive
        trading_start_hour=7,                          # ← UTC
        trading_end_hour=22,                           # ← UTC
        stop_loss_buffer_pips=1.0,                     # ← Pine: stop_loss_buffer_pips := 1.0

        # Advanced settings (keep defaults)
        require_major_liquidity=False,                 # ← Pine: require_major_liquidity := is_conservative or is_balanced (NOT Aggressive)
        structure_mode="Relaxed (Wicks)",              # ← Pine: structure_mode := is_conservative ? "Standard (Bodies)" : "Relaxed (Wicks)"
        enable_grade_filter=False,                     # ← Pine: enable_grade_filter := is_conservative or is_balanced (NOT Aggressive)
        enable_trade_limit=True,                       # ← Enable daily limit
        invalidate_on_wick=True,
        max_zones=20,
        min_body_perc=50.0,
        use_one_candle_liquidity=True,
        liq_max_distance_pips_forex=20.0,              # ← Not used for XAUUSD, but Pine: liq_max_distance_pips_forex := 20.0
        liq_max_distance_pips_index=5000.0,
        use_custom_rr=False,                           # ← Use SL-based rules for Gold
        take_profit_pips=0.0,
        min_position_size_units=1000,
        max_position_size_lots=10.0,
        use_break_even=False,
        max_bars_held=36,
        enable_double_tp=False,
        use_fvg_confirmation=False,
        enable_accuracy_zones=True,
        enable_date_filter=True,
        min_bar_index_for_entries=100,
        max_daily_loss_pct=2.0,
        max_daily_profit_pct=5.0,
        enable_ai_quality_filter=True,
    )

    print(f"⚡ AGGRESSIVE PROFILE SETTINGS (Exact TV Match):")
    print(f"{'='*60}")
    print(f"   - pvtMax (Liquidity Lines): {cfg.pvt_max}")
    print(f"   - Pivot Strength: {cfg.liq_pivot_len}")
    print(f"   - Max Liq Distance (Gold): {cfg.liq_max_distance_pips_gold} pips")
    print(f"   - Max Zone-to-Liq Distance: {cfg.liq_entry_max_dist} pips")
    print(f"   - AI Quality Threshold: {cfg.ai_quality_threshold}")
    print(f"   - Min Entry Grade: {cfg.min_entry_grade}")
    print(f"   - Min Return Strength: {cfg.min_return_strength}")
    print(f"   - Trade Limit: {cfg.max_trades_per_day}/day")
    print(f"   - HTF FLIP Required: {cfg.require_htf_flip}")
    print(f"   - Risk:Reward Ratio: {cfg.risk_reward_ratio} (SL-based for gold)")
    print(f"   - Trading Hours: {cfg.trading_start_hour}:00 - {cfg.trading_end_hour}:00 UTC")
    print(f"   - Dead Zone Filter: {cfg.filter_dead_zone}")
    print(f"{'='*60}\n")

    # Run backtest
    print("🔄 Running backtest with Aggressive Profile...\n")

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
    write_trades_csv(trades, out_dir / "trades.csv")
    write_equity_csv(engine.equity_curve, out_dir / "equity.csv")
    print(f"\n💾 Saved trades to: {out_dir / 'trades.csv'}")

    # Comparison with previous run
    print(f"\n{'='*60}")
    print(f"📊 RESULTS")
    print(f"{'='*60}")
    print(f"Total Trades: {len(trades)}")
    print(f"Net Profit: ${summary.net_profit:,.2f}")
    print(f"Win Rate: {summary.win_rate:.1f}%")
    print(f"Profit Factor: {summary.profit_factor:.2f}")
    print(f"Max Drawdown: ${summary.max_drawdown:,.2f}")
    print(f"{'='*60}\n")

    print("✅ Backtest complete with Aggressive Profile settings!")
    print("\nNext steps:")
    print("1. Compare with your TradingView results")
    print("2. Visualize: streamlit run app/visualizer.py")
    print("3. If still different, check TradingView's exact date range in strategy settings")

if __name__ == "__main__":
    main()
