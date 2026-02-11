#!/usr/bin/env python3
"""
Test different filter combinations to find what matches TradingView best.

Target: 35 trades, +$1,030, 57% win rate
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import BacktestConfig
from app.data import get_candles
from app.engine import BacktestEngine
from app.snd_strategy import SNDStrategy
import pandas as pd

def run_test(name, **overrides):
    """Run backtest with specific config overrides."""
    from_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 10, 23, 59, 59, tzinfo=timezone.utc)

    candles = get_candles(
        symbol="XAUUSD",
        from_date=from_date,
        to_date=to_date,
        timeframe="M5",
        data_dir=Path("data/backtest_candles"),
        metaapi_token=None,
        metaapi_account_id=None,
        symbol_aliases={},
        persist=False,
    )

    # Base config
    cfg = BacktestConfig(
        symbol="XAUUSD",
        timeframe="M5",
        tick_size=0.01,
        pip_size=0.01,
        start_date=from_date,
        end_date=to_date,
    )

    # Apply overrides
    for key, value in overrides.items():
        setattr(cfg, key, value)

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

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    net_pnl = sum(t.pnl for t in trades)
    win_rate = (len(wins) / len(trades) * 100) if trades else 0

    print(f"{name:40s} | {len(trades):3d} trades | ${net_pnl:8,.0f} | {win_rate:5.1f}% WR")
    return len(trades), net_pnl, win_rate

print("=" * 100)
print(f"{'Configuration':40s} | Trades | Net PnL | Win Rate")
print("=" * 100)

# Test different configurations
tests = [
    ("DEFAULT (max_trades=2, htf_flip=True, ai_q=60)", {}),
    ("No trade limit, htf_flip=False, ai_q=50", {"enable_trade_limit": False, "require_htf_flip": False, "ai_quality_threshold": 50}),
    ("No trade limit, htf_flip=True, ai_q=65", {"enable_trade_limit": False, "require_htf_flip": True, "ai_quality_threshold": 65}),
    ("No trade limit, htf_flip=False, ai_q=65", {"enable_trade_limit": False, "require_htf_flip": False, "ai_quality_threshold": 65}),
    ("No trade limit, htf_flip=False, ai_q=70", {"enable_trade_limit": False, "require_htf_flip": False, "ai_quality_threshold": 70}),
    ("max_trades=3, htf_flip=False, ai_q=60", {"max_trades_per_day": 3, "require_htf_flip": False}),
    ("max_trades=4, htf_flip=False, ai_q=60", {"max_trades_per_day": 4, "require_htf_flip": False}),
    ("max_trades=5, htf_flip=False, ai_q=55", {"max_trades_per_day": 5, "require_htf_flip": False, "ai_quality_threshold": 55}),
]

results = []
for name, overrides in tests:
    count, pnl, wr = run_test(name, **overrides)
    results.append((name, count, pnl, wr))

print("=" * 100)
print(f"{'TradingView Target':40s} |  35 trades | ${1030:8,.0f} | {57.14:5.1f}% WR")
print("=" * 100)

# Find closest match
best_match = min(results, key=lambda r: abs(r[1] - 35) + abs(r[2] - 1030) / 100 + abs(r[3] - 57.14))
print(f"\n✅ CLOSEST MATCH: {best_match[0]}")
print(f"   {best_match[1]} trades, ${best_match[2]:,.0f}, {best_match[3]:.1f}% WR")
