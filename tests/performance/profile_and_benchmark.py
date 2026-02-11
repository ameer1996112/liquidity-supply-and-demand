"""
Profiling and benchmarking script for engine performance.

Usage:
    # Profile current implementation
    python tests/performance/profile_and_benchmark.py --profile

    # Benchmark speedup
    python tests/performance/profile_and_benchmark.py --benchmark

    # Both
    python tests/performance/profile_and_benchmark.py --profile --benchmark
"""

import argparse
import cProfile
import pstats
import time
from datetime import datetime, timezone, timedelta
from io import StringIO

import numpy as np
import pandas as pd

from app.config import BacktestConfig
from app.engine import BacktestEngine
from app.engine_core import FastBacktestEngine
from app.snd_strategy import SNDStrategy


def generate_sample_candles(n_bars: int = 10000, symbol: str = "XAUUSD") -> pd.DataFrame:
    """Generate synthetic candle data for testing."""
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Generate realistic price movement
    base_price = 2000.0 if "XAU" in symbol else 1.1000
    volatility = 10.0 if "XAU" in symbol else 0.0010

    times = []
    opens = []
    highs = []
    lows = []
    closes = []

    current_price = base_price
    current_time = start_time

    for i in range(n_bars):
        # Random walk
        change = np.random.randn() * volatility
        open_price = current_price
        close_price = current_price + change

        # High/low with realistic spread
        high_price = max(open_price, close_price) + abs(np.random.randn() * volatility * 0.3)
        low_price = min(open_price, close_price) - abs(np.random.randn() * volatility * 0.3)

        times.append(current_time)
        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(close_price)

        current_price = close_price
        current_time += timedelta(minutes=5)  # M5 timeframe

    return pd.DataFrame({
        'time': times,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': [100] * n_bars,
    })


def profile_legacy_engine(candles: pd.DataFrame, config: BacktestConfig) -> None:
    """Profile legacy engine with cProfile."""
    print("\n" + "="*80)
    print("PROFILING LEGACY ENGINE")
    print("="*80)

    profiler = cProfile.Profile()

    engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    strategy = SNDStrategy(config=config)

    profiler.enable()
    trades = engine.run(candles, strategy.on_bar)
    profiler.disable()

    # Print statistics
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(30)  # Top 30 functions

    print(s.getvalue())
    print(f"\nTotal trades: {len(trades)}")


def profile_fast_engine(candles: pd.DataFrame, config: BacktestConfig) -> None:
    """Profile fast engine with cProfile."""
    print("\n" + "="*80)
    print("PROFILING FAST ENGINE")
    print("="*80)

    profiler = cProfile.Profile()

    engine = FastBacktestEngine(config=config)

    profiler.enable()
    trades = engine.run(candles)
    profiler.disable()

    # Print statistics
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(30)  # Top 30 functions

    print(s.getvalue())
    print(f"\nTotal trades: {len(trades)}")


def benchmark_engines(n_bars_list: list = [1000, 5000, 10000]) -> None:
    """Benchmark both engines at different bar counts."""
    print("\n" + "="*80)
    print("PERFORMANCE BENCHMARK")
    print("="*80)

    config = BacktestConfig(
        symbol="XAUUSD",
        timeframe="M5",
        tick_size=0.01,
        pip_size=0.01,
        risk_per_trade_pct=0.5,
        stop_loss_buffer_pips=1.0,
        ai_quality_threshold=50,
        require_htf_flip=False,
        account_size_usd=50000.0,
    )

    results = []

    for n_bars in n_bars_list:
        print(f"\n{'-'*80}")
        print(f"Testing with {n_bars:,} bars")
        print(f"{'-'*80}")

        candles = generate_sample_candles(n_bars=n_bars)

        # Benchmark Legacy
        print(f"\n  Legacy Engine:")
        legacy_engine = BacktestEngine(
            tick_size=config.tick_size,
            slippage_ticks=3,
            initial_equity=config.account_size_usd,
            commission_pct=0.0,
            pyramiding=0,
            max_bars_held=36,
        )
        legacy_strategy = SNDStrategy(config=config)

        start = time.time()
        legacy_trades = legacy_engine.run(candles, legacy_strategy.on_bar)
        legacy_time = time.time() - start

        legacy_bars_per_sec = n_bars / legacy_time if legacy_time > 0 else 0
        print(f"    Time: {legacy_time:.2f}s")
        print(f"    Trades: {len(legacy_trades)}")
        print(f"    Speed: {legacy_bars_per_sec:.0f} bars/sec")

        # Benchmark Fast
        print(f"\n  Fast Engine:")
        fast_engine = FastBacktestEngine(config=config)

        start = time.time()
        fast_trades = fast_engine.run(candles)
        fast_time = time.time() - start

        fast_bars_per_sec = n_bars / fast_time if fast_time > 0 else 0
        speedup = legacy_time / fast_time if fast_time > 0 else 0

        print(f"    Time: {fast_time:.2f}s")
        print(f"    Trades: {len(fast_trades)}")
        print(f"    Speed: {fast_bars_per_sec:.0f} bars/sec")
        print(f"    Speedup: {speedup:.1f}x")

        # Check parity
        trade_count_match = len(legacy_trades) == len(fast_trades)
        parity_status = "✅ PASS" if trade_count_match else "❌ FAIL"
        print(f"    Parity: {parity_status}")

        results.append({
            'n_bars': n_bars,
            'legacy_time': legacy_time,
            'fast_time': fast_time,
            'legacy_trades': len(legacy_trades),
            'fast_trades': len(fast_trades),
            'speedup': speedup,
            'parity': trade_count_match,
        })

    # Summary table
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n{'Bars':<10} {'Legacy':<12} {'Fast':<12} {'Speedup':<12} {'Trades':<12} {'Parity'}")
    print("-"*80)

    for r in results:
        parity_icon = "✅" if r['parity'] else "❌"
        print(f"{r['n_bars']:<10,} {r['legacy_time']:<12.2f} {r['fast_time']:<12.2f} "
              f"{r['speedup']:<12.1f} {r['fast_trades']:<12} {parity_icon}")

    # Performance targets
    print("\n" + "="*80)
    print("WEEK 2 PERFORMANCE TARGETS")
    print("="*80)

    target_10k = results[-1] if results else None
    if target_10k and target_10k['n_bars'] == 10000:
        target_time = 0.5  # Target: <0.5s for 10k bars
        target_speedup = 20  # Target: 20x minimum

        time_status = "✅ PASS" if target_10k['fast_time'] < target_time else "❌ FAIL"
        speedup_status = "✅ PASS" if target_10k['speedup'] >= target_speedup else "❌ FAIL"

        print(f"10k bars in <0.5s:  {time_status}  (actual: {target_10k['fast_time']:.2f}s)")
        print(f"20x speedup min:    {speedup_status}  (actual: {target_10k['speedup']:.1f}x)")

    print("")


def main():
    parser = argparse.ArgumentParser(description="Profile and benchmark engines")
    parser.add_argument("--profile", action="store_true", help="Run cProfile profiling")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmarks")
    parser.add_argument("--bars", type=int, default=10000, help="Number of bars for profiling")
    args = parser.parse_args()

    if not args.profile and not args.benchmark:
        # Default: run both
        args.profile = True
        args.benchmark = True

    config = BacktestConfig(
        symbol="XAUUSD",
        timeframe="M5",
        tick_size=0.01,
        pip_size=0.01,
        risk_per_trade_pct=0.5,
        stop_loss_buffer_pips=1.0,
        ai_quality_threshold=50,
        require_htf_flip=False,
        account_size_usd=50000.0,
    )

    if args.profile:
        candles = generate_sample_candles(n_bars=args.bars)
        profile_legacy_engine(candles, config)
        profile_fast_engine(candles, config)

    if args.benchmark:
        benchmark_engines(n_bars_list=[1000, 5000, 10000])


if __name__ == "__main__":
    main()
