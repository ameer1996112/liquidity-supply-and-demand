"""
Unit tests for backtest system: candle alignment, tick rounding, slippage, engine.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.data import _normalize_candles
from app.engine import (
    BacktestEngine,
    ClosedTrade,
    Order,
    OrderSide,
    OrderType,
    apply_slippage_entry,
    apply_slippage_exit,
    round_to_tick,
)
from app.snd_utils import get_auto_pip_size, is_bullish, is_bearish


def test_round_to_tick():
    """Tick rounding."""
    assert round_to_tick(2650.123, 0.01) == 2650.12
    assert round_to_tick(2650.126, 0.01) == 2650.13
    assert abs(round_to_tick(1.23456, 0.0001) - 1.2346) < 1e-9


def test_slippage_entry():
    """Entry slippage: long = close + slip, short = close - slip."""
    close = 2650.0
    tick = 0.01
    slip = 3
    long_fill = apply_slippage_entry(close, OrderSide.LONG, slip, tick)
    short_fill = apply_slippage_entry(close, OrderSide.SHORT, slip, tick)
    assert abs(long_fill - 2650.03) < 1e-9
    assert abs(short_fill - 2649.97) < 1e-9


def test_slippage_exit():
    """Exit slippage: long exit = price - slip (selling)."""
    price = 2650.0
    tick = 0.01
    slip = 3
    long_exit = apply_slippage_exit(price, OrderSide.LONG, slip, tick)
    short_exit = apply_slippage_exit(price, OrderSide.SHORT, slip, tick)
    assert abs(long_exit - 2649.97) < 1e-9
    assert abs(short_exit - 2650.03) < 1e-9


def test_get_auto_pip_size():
    """Pip size by symbol."""
    assert get_auto_pip_size("XAUUSD", 0.01) == 0.01
    assert get_auto_pip_size("EURUSD", 0.0001) == 0.0001
    assert get_auto_pip_size("USDJPY", 0.01) == 0.01


def test_candle_normalization():
    """Candle schema and dedup."""
    df = pd.DataFrame({
        "time": ["2026-01-01 00:00:00", "2026-01-01 00:05:00", "2026-01-01 00:05:00"],  # dup
        "open": [2650.0, 2651.0, 2651.1],
        "high": [2652.0, 2653.0, 2653.0],
        "low": [2649.0, 2650.0, 2650.0],
        "close": [2651.0, 2652.0, 2652.0],
    })
    out = _normalize_candles(df)
    assert len(out) == 2  # dedup keeps last
    assert list(out.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert out["time"].is_monotonic_increasing


def test_engine_deterministic():
    """Minimal deterministic backtest."""
    # 20 bars, no strategy entries - just verify engine runs
    np.random.seed(42)
    n = 20
    base = 2650.0
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"),
        "open": base + np.cumsum(np.random.randn(n) * 0.5),
        "high": base + np.cumsum(np.random.randn(n) * 0.5) + 1,
        "low": base + np.cumsum(np.random.randn(n) * 0.5) - 1,
        "close": base + np.cumsum(np.random.randn(n) * 0.5),
        "volume": np.ones(n) * 100,
    })
    candles["high"] = candles[["open", "high", "close"]].max(axis=1)
    candles["low"] = candles[["open", "low", "close"]].min(axis=1)

    engine = BacktestEngine(tick_size=0.01, slippage_ticks=3)

    def on_bar(bar_idx, bar, history, has_position):
        return []

    trades = engine.run(candles, on_bar)
    assert len(trades) == 0
    assert len(engine.equity_curve) == n


def test_engine_single_entry_exit():
    """Single long entry, exit at TP (TP hit before SL on bar with both in range)."""
    # Bar 2: entry at close 2651. High 2655 (TP), Low 2648 (above SL 2645). TP hit first.
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=10, freq="5min", tz="UTC"),
        "open": [2650.0] * 10,
        "high": [2655.0] * 10,
        "low": [2648.0] * 10,
        "close": [2650.0, 2651.0, 2652.0, 2653.0, 2654.0, 2655.0, 2655.0, 2655.0, 2655.0, 2655.0],
        "volume": [100] * 10,
    })

    engine = BacktestEngine(tick_size=0.01, slippage_ticks=0)

    def on_bar(bar_idx, bar, history, has_position):
        if bar_idx == 1 and not has_position:
            return [Order(
                side=OrderSide.LONG,
                order_type=OrderType.ENTRY,
                qty=10,
                stop_price=2645.0,
                limit_price=2655.0,
            )]
        return []

    trades = engine.run(candles, on_bar)
    assert len(trades) == 1
    assert trades[0].reason == "limit"
    assert trades[0].side == OrderSide.LONG
    assert trades[0].pnl > 0
