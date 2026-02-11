"""
Demo script: FX Replay System

Demonstrates all new features:
1. Fast Numba engine (20-50× speedup)
2. Enhanced data loader (Parquet → FXCM → MetaApi)
3. Strict N+1 parity (signal at N, execute at N+1 open)
4. Interactive Streamlit dashboard

Usage:
    python scripts/demo_fx_replay.py --mode [fast|legacy|n_plus_1|streamlit]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import BacktestConfig
from app.data_loader import get_candles_auto
from app.engine import BacktestEngine
from app.engine_core import FastBacktestEngine
from app.engine_enhanced import run_backtest_with_n_plus_1, run_backtest_tradingview_mode
from app.outputs import compute_summary, print_summary
from app.snd_strategy import SNDStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def run_legacy_engine(candles, config):
    """Run with legacy Python engine (slow, for baseline)."""
    logger.info("🐢 Running LEGACY engine (Python loop)")
    start = time.time()

    engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=config.max_bars_held,
    )

    strategy = SNDStrategy(config=config)

    def on_bar(bar_idx, bar, history, has_position):
        return strategy.on_bar(bar_idx, bar, history, has_position)

    trades = engine.run(candles, on_bar)
    runtime = time.time() - start

    logger.info(f"✅ Legacy engine completed in {runtime:.2f}s ({len(candles) / runtime:.0f} bars/sec)")
    return trades, engine.equity_curve, runtime


def run_fast_engine(candles, config):
    """Run with Numba-optimized engine (fast, 20-50× speedup)."""
    logger.info("🚀 Running FAST engine (Numba JIT)")
    start = time.time()

    engine = FastBacktestEngine(config=config)
    trades = engine.run(candles)

    runtime = time.time() - start
    perf = engine.get_performance_summary()

    logger.info(
        f"✅ Fast engine completed in {runtime:.2f}s ({perf['bars_per_second']:.0f} bars/sec, "
        f"~{perf['speedup_estimate']:.1f}× speedup)"
    )

    return trades, engine.equity_curve, runtime


def run_n_plus_1_engine(candles, config):
    """Run with strict N+1 parity (signal at N, fill at N+1 open)."""
    logger.info("📊 Running N+1 PARITY engine (signal at N, fill at N+1 open)")
    start = time.time()

    strategy = SNDStrategy(config=config)
    trades, equity_curve, engine = run_backtest_with_n_plus_1(candles, strategy, config)

    runtime = time.time() - start

    logger.info(f"✅ N+1 engine completed in {runtime:.2f}s")
    return trades, equity_curve, runtime


def main():
    parser = argparse.ArgumentParser(description="Demo FX Replay features")
    parser.add_argument("--mode", choices=["fast", "legacy", "n_plus_1", "compare", "streamlit"], default="fast")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--from", dest="from_date", default="2026-01-01")
    parser.add_argument("--to", dest="to_date", default="2026-02-10")
    parser.add_argument("--timeframe", default="M5")
    args = parser.parse_args()

    # Dates
    from_dt = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_dt = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, tzinfo=timezone.utc)

    # Config
    config = BacktestConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        tick_size=0.01 if "XAU" in args.symbol else 0.00001,
        pip_size=0.01 if "XAU" in args.symbol else 0.0001,
        start_date=from_dt,
        end_date=to_dt,
    )

    logger.info(f"📦 Loading candles: {args.symbol} {args.timeframe} ({args.from_date} to {args.to_date})")

    # Load data (auto-detect source: Parquet → FXCM → MetaApi)
    try:
        candles = get_candles_auto(
            symbol=args.symbol,
            from_date=from_dt,
            to_date=to_dt,
            timeframe=args.timeframe
        )
        logger.info(f"✅ Loaded {len(candles)} candles")
    except Exception as e:
        logger.error(f"❌ Failed to load candles: {e}")
        logger.info("Tip: Set FXCM_API_TOKEN or META_API_TOKEN in .env")
        sys.exit(1)

    # Run backtest based on mode
    if args.mode == "streamlit":
        logger.info("🎨 Launching Streamlit dashboard...")
        logger.info("Run: streamlit run app/app.py")
        sys.exit(0)

    elif args.mode == "compare":
        # A/B test: Legacy vs Fast
        logger.info("⚖️  A/B Testing: Legacy vs Fast engines")
        logger.info("=" * 60)

        # Legacy
        trades_legacy, eq_legacy, time_legacy = run_legacy_engine(candles, config)
        summary_legacy = compute_summary(trades_legacy, eq_legacy)

        logger.info("\n" + "=" * 60)

        # Fast
        trades_fast, eq_fast, time_fast = run_fast_engine(candles, config)
        summary_fast = compute_summary(trades_fast, eq_fast)

        # Compare
        logger.info("\n" + "=" * 60)
        logger.info("COMPARISON RESULTS")
        logger.info("=" * 60)

        logger.info(f"\nLegacy: {len(trades_legacy)} trades, {time_legacy:.2f}s")
        logger.info(f"Fast:   {len(trades_fast)} trades, {time_fast:.2f}s")
        logger.info(f"Speedup: {time_legacy / time_fast:.1f}×")

        if summary_legacy.get("net_profit") != summary_fast.get("net_profit"):
            logger.warning("⚠️  Results differ! Check parity.")

    elif args.mode == "legacy":
        trades, equity_curve, _ = run_legacy_engine(candles, config)
        summary = compute_summary(trades, equity_curve)
        print_summary(summary)

    elif args.mode == "fast":
        trades, equity_curve, _ = run_fast_engine(candles, config)
        summary = compute_summary(trades, equity_curve)
        print_summary(summary)

    elif args.mode == "n_plus_1":
        trades, equity_curve, _ = run_n_plus_1_engine(candles, config)
        summary = compute_summary(trades, equity_curve)
        print_summary(summary)

        logger.info("\nNote: N+1 execution fills orders at NEXT bar open (more realistic)")
        logger.info("Compare with 'fast' mode to see difference in fill prices.")


if __name__ == "__main__":
    main()
