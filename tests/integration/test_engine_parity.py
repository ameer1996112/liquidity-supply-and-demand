"""
Integration tests for engine parity (Fast vs Legacy).

Ensures that the Numba-optimized FastBacktestEngine produces identical results
to the legacy Python BacktestEngine.

Run with: pytest tests/integration/test_engine_parity.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from app.config import BacktestConfig
from app.engine import BacktestEngine
from app.engine_core import FastBacktestEngine
from app.snd_strategy import SNDStrategy


def generate_sample_candles(n_bars: int = 1000, symbol: str = "XAUUSD") -> pd.DataFrame:
    """
    Generate synthetic candle data for testing.

    Args:
        n_bars: Number of candles to generate
        symbol: Symbol name (XAUUSD or EURUSD)

    Returns:
        DataFrame with columns: time, open, high, low, close, volume
    """
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


@pytest.fixture
def sample_candles_xauusd():
    """Generate 1000 bars of XAUUSD M5 data."""
    return generate_sample_candles(n_bars=1000, symbol="XAUUSD")


@pytest.fixture
def sample_config_xauusd():
    """Create test config for XAUUSD."""
    return BacktestConfig(
        symbol="XAUUSD",
        timeframe="M5",
        tick_size=0.01,
        pip_size=0.01,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        risk_per_trade_pct=0.5,
        stop_loss_buffer_pips=1.0,
        ai_quality_threshold=50,  # Lower threshold for testing
        require_htf_flip=False,  # Disable for simpler testing
        enable_ai_quality_filter=True,
        account_size_usd=50000.0,
    )


def test_engine_parity_trade_count(sample_candles_xauusd, sample_config_xauusd):
    """
    Test that both engines produce the same number of trades.

    This is the most basic parity check.
    """
    candles = sample_candles_xauusd
    config = sample_config_xauusd

    # Legacy engine
    legacy_engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    legacy_strategy = SNDStrategy(config=config)

    def on_bar(bar_idx, bar, history, has_position):
        return legacy_strategy.on_bar(bar_idx, bar, history, has_position)

    legacy_trades = legacy_engine.run(candles, on_bar)

    # Fast engine
    fast_engine = FastBacktestEngine(config=config)
    fast_trades = fast_engine.run(candles)

    # Compare trade count
    assert len(legacy_trades) == len(fast_trades), \
        f"Trade count mismatch: legacy={len(legacy_trades)}, fast={len(fast_trades)}"

    print(f"✓ Both engines produced {len(legacy_trades)} trades")


def test_engine_parity_entry_times(sample_candles_xauusd, sample_config_xauusd):
    """
    Test that both engines enter trades at the same times.

    Entry time is the most critical parity check.
    """
    candles = sample_candles_xauusd
    config = sample_config_xauusd

    # Legacy engine
    legacy_engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    legacy_strategy = SNDStrategy(config=config)
    legacy_trades = legacy_engine.run(candles, legacy_strategy.on_bar)

    # Fast engine
    fast_engine = FastBacktestEngine(config=config)
    fast_trades = fast_engine.run(candles)

    # Compare entry times
    assert len(legacy_trades) == len(fast_trades)

    for i, (leg, fast) in enumerate(zip(legacy_trades, fast_trades)):
        assert leg.entry_time == fast.entry_time, \
            f"Trade {i}: Entry time mismatch: legacy={leg.entry_time}, fast={fast.entry_time}"

    print(f"✓ All {len(legacy_trades)} entry times match")


def test_engine_parity_entry_prices(sample_candles_xauusd, sample_config_xauusd):
    """
    Test that both engines use the same entry prices.

    Entry price should include slippage and be identical.
    """
    candles = sample_candles_xauusd
    config = sample_config_xauusd

    # Legacy engine
    legacy_engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    legacy_strategy = SNDStrategy(config=config)
    legacy_trades = legacy_engine.run(candles, legacy_strategy.on_bar)

    # Fast engine
    fast_engine = FastBacktestEngine(config=config)
    fast_trades = fast_engine.run(candles)

    assert len(legacy_trades) == len(fast_trades)

    for i, (leg, fast) in enumerate(zip(legacy_trades, fast_trades)):
        price_diff = abs(leg.entry_price - fast.entry_price)
        tolerance = config.tick_size * 2  # Allow small rounding differences

        assert price_diff < tolerance, \
            f"Trade {i}: Entry price diff {price_diff:.4f} > tolerance {tolerance:.4f} " \
            f"(legacy={leg.entry_price:.2f}, fast={fast.entry_price:.2f})"

    print(f"✓ All {len(legacy_trades)} entry prices match (within {tolerance:.4f})")


def test_engine_parity_pnl(sample_candles_xauusd, sample_config_xauusd):
    """
    Test that both engines calculate the same PnL.

    This is the ultimate parity check - if PnL matches, the engines are equivalent.
    """
    candles = sample_candles_xauusd
    config = sample_config_xauusd

    # Legacy engine
    legacy_engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    legacy_strategy = SNDStrategy(config=config)
    legacy_trades = legacy_engine.run(candles, legacy_strategy.on_bar)

    # Fast engine
    fast_engine = FastBacktestEngine(config=config)
    fast_trades = fast_engine.run(candles)

    assert len(legacy_trades) == len(fast_trades)

    # Compare individual trade PnL
    total_pnl_diff = 0.0
    for i, (leg, fast) in enumerate(zip(legacy_trades, fast_trades)):
        pnl_diff = abs(leg.pnl - fast.pnl)
        pnl_diff_pct = (pnl_diff / abs(leg.pnl)) * 100 if leg.pnl != 0 else 0.0

        # Allow <0.1% difference due to floating point rounding
        assert pnl_diff_pct < 0.1, \
            f"Trade {i}: PnL diff {pnl_diff_pct:.2f}% > 0.1% " \
            f"(legacy=${leg.pnl:.2f}, fast=${fast.pnl:.2f})"

        total_pnl_diff += pnl_diff

    # Compare total PnL
    legacy_total_pnl = sum(t.pnl for t in legacy_trades)
    fast_total_pnl = sum(t.pnl for t in fast_trades)
    total_pnl_diff_pct = abs(legacy_total_pnl - fast_total_pnl) / abs(legacy_total_pnl) * 100 \
        if legacy_total_pnl != 0 else 0.0

    assert total_pnl_diff_pct < 0.1, \
        f"Total PnL diff {total_pnl_diff_pct:.2f}% > 0.1% " \
        f"(legacy=${legacy_total_pnl:.2f}, fast=${fast_total_pnl:.2f})"

    print(f"✓ All {len(legacy_trades)} PnLs match (total diff: ${total_pnl_diff:.2f})")


def test_engine_parity_side(sample_candles_xauusd, sample_config_xauusd):
    """Test that both engines trade the same direction (long/short)."""
    candles = sample_candles_xauusd
    config = sample_config_xauusd

    # Legacy engine
    legacy_engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    legacy_strategy = SNDStrategy(config=config)
    legacy_trades = legacy_engine.run(candles, legacy_strategy.on_bar)

    # Fast engine
    fast_engine = FastBacktestEngine(config=config)
    fast_trades = fast_engine.run(candles)

    assert len(legacy_trades) == len(fast_trades)

    for i, (leg, fast) in enumerate(zip(legacy_trades, fast_trades)):
        assert leg.side == fast.side, \
            f"Trade {i}: Side mismatch: legacy={leg.side}, fast={fast.side}"

    print(f"✓ All {len(legacy_trades)} sides match")


@pytest.mark.parametrize("n_bars", [100, 500, 1000])
def test_engine_parity_various_lengths(n_bars, sample_config_xauusd):
    """Test parity across different candle counts."""
    candles = generate_sample_candles(n_bars=n_bars, symbol="XAUUSD")
    config = sample_config_xauusd

    # Legacy engine
    legacy_engine = BacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=3,
        initial_equity=config.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=36,
    )
    legacy_strategy = SNDStrategy(config=config)
    legacy_trades = legacy_engine.run(candles, legacy_strategy.on_bar)

    # Fast engine
    fast_engine = FastBacktestEngine(config=config)
    fast_trades = fast_engine.run(candles)

    # Basic parity check
    assert len(legacy_trades) == len(fast_trades), \
        f"{n_bars} bars: Trade count mismatch"

    print(f"✓ {n_bars} bars: {len(legacy_trades)} trades, parity confirmed")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
