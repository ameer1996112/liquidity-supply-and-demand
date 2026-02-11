"""
High-performance backtest engine using Numba-compiled kernels.

Replaces legacy BacktestEngine with NumPy/Numba-accelerated version.
Expected speedup: 20-50x for 10,000 bars.

Week 1: Functional parity with legacy engine
Week 2: Full optimization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
import time

import numpy as np
import pandas as pd

from app.config import BacktestConfig
from app.engine import ClosedTrade, OrderSide
from app.zone_manager import ZoneManager
from app.numba_kernels import run_backtest_numba

logger = logging.getLogger(__name__)


@dataclass
class FastBacktestEngine:
    """
    High-performance backtest engine using Numba JIT compilation.

    Architecture:
    - Python layer: Orchestration, data conversion, result formatting
    - Numba layer: Hot path bar-by-bar processing (compiled to native code)
    - NumPy layer: Pre-allocated arrays for zones, equity curve, trades
    """

    config: BacktestConfig

    # State
    zone_manager: ZoneManager = field(default=None, init=False)
    closed_trades: List[ClosedTrade] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def __post_init__(self):
        """Initialize zone manager."""
        self.zone_manager = ZoneManager(max_zones=1000)

    def reset(self) -> None:
        """Reset engine state for new backtest run."""
        self.zone_manager.reset()
        self.closed_trades = []
        self.equity_curve = []
        self.runtime_seconds = 0.0

    def run(self, candles_df: pd.DataFrame) -> List[ClosedTrade]:
        """
        Run backtest over candles using Numba-optimized kernel.

        Args:
            candles_df: DataFrame with columns: time, open, high, low, close

        Returns:
            List of ClosedTrade objects
        """
        start_time = time.time()

        self.reset()

        # Convert Pandas → NumPy (one-time cost)
        logger.info("Converting DataFrame to NumPy arrays...")
        candles_np = candles_df[['open', 'high', 'low', 'close']].to_numpy(dtype=np.float32)
        times_np = candles_df['time'].values.astype('datetime64[s]').astype(np.int64)

        # Pre-allocate arrays
        n_bars = len(candles_np)
        equity_curve_np = np.zeros((n_bars, 2), dtype=np.float64)

        # Create config tuple for Numba (no dataclasses allowed)
        config_tuple = self._create_config_tuple()

        # Call Numba kernel (hot path)
        logger.info(f"Running Numba backtest kernel on {n_bars} bars...")
        kernel_start = time.time()

        trades_np, final_zone_count, equity_curve_np = run_backtest_numba(
            candles_np,
            times_np,
            self.zone_manager.zones,
            config_tuple,
            equity_curve_np
        )

        kernel_time = time.time() - kernel_start
        logger.info(f"Numba kernel completed in {kernel_time:.2f}s ({n_bars / kernel_time:.0f} bars/sec)")

        # Update zone manager with final count from Numba kernel
        self.zone_manager.zone_count = final_zone_count

        # Convert NumPy results → Python objects
        logger.info(f"Converting {len(trades_np)} trades to Python objects...")
        self.closed_trades = self._convert_trades_to_python(trades_np, candles_df)
        self.equity_curve = self._convert_equity_curve(equity_curve_np)

        self.runtime_seconds = time.time() - start_time
        logger.info(f"Total runtime: {self.runtime_seconds:.2f}s")

        # Log zone statistics
        demand_count, supply_count = self.zone_manager.get_active_count()
        logger.info(f"Final zone count: {final_zone_count} ({demand_count} demand, {supply_count} supply)")

        return self.closed_trades

    def _create_config_tuple(self) -> tuple:
        """
        Create Numba-compatible config tuple.

        Numba requires primitive types (no dataclasses in JIT functions).

        Returns:
            Tuple: (tick_size, pip_size, slippage_ticks, sl_buffer, risk_pct,
                   account_size, quality_threshold, min_bar, is_gold, require_htf_flip)
        """
        return (
            float(self.config.tick_size),
            float(self.config.pip_size),
            int(self.config.slippage_ticks),
            float(self.config.stop_loss_buffer_pips),
            float(self.config.risk_per_trade_pct),
            float(self.config.account_size_usd),
            float(self.config.ai_quality_threshold),
            int(self.config.min_bar_index_for_entries),
            bool(self.config.is_gold()),
            bool(self.config.require_htf_flip),
        )

    def _convert_trades_to_python(
        self,
        trades_np: np.ndarray,
        candles_df: pd.DataFrame
    ) -> List[ClosedTrade]:
        """
        Convert NumPy trade array to ClosedTrade objects.

        Args:
            trades_np: (M, 8) array [entry_bar, exit_bar, entry_price, exit_price,
                                     pnl, is_long, reason, zone_idx]
            candles_df: Original candle DataFrame (for timestamps)

        Returns:
            List of ClosedTrade objects
        """
        trades = []

        for row in trades_np:
            entry_bar = int(row[0])
            exit_bar = int(row[1])
            entry_price = float(row[2])
            exit_price = float(row[3])
            pnl = float(row[4])
            is_long = bool(row[5])
            reason_code = int(row[6])
            zone_idx = int(row[7])

            # Map reason code to string
            reason_map = {0: "stop", 1: "limit", 2: "time"}
            reason = reason_map.get(reason_code, "unknown")

            # Get timestamps from original DataFrame
            entry_time = candles_df.iloc[entry_bar]['time']
            exit_time = candles_df.iloc[exit_bar]['time']

            # Convert to datetime if needed
            if isinstance(entry_time, (np.datetime64,)):
                entry_time = pd.Timestamp(entry_time).to_pydatetime()
            if isinstance(exit_time, (np.datetime64,)):
                exit_time = pd.Timestamp(exit_time).to_pydatetime()

            # Calculate derived metrics
            qty = 100.0  # Default qty (can be stored in trades_np if needed)
            bars_held = exit_bar - entry_bar
            pnl_pct = (pnl / (entry_price * qty)) * 100 if qty > 0 else 0.0

            # Get zone info (if available)
            zone_bottom = np.nan
            zone_top = np.nan
            if zone_idx < len(self.zone_manager.zones):
                zone_bottom = float(self.zone_manager.zones[zone_idx]['bottom'])
                zone_top = float(self.zone_manager.zones[zone_idx]['top'])

            trades.append(ClosedTrade(
                entry_time=entry_time,
                exit_time=exit_time,
                side=OrderSide.LONG if is_long else OrderSide.SHORT,
                qty=qty,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                bars_held=bars_held,
                reason=reason,
                entry_comment="FLIP",  # Week 2: store entry model in trades_np
                stop_price=0.0,  # Week 2: store SL/TP in trades_np if needed
                limit_price=0.0,
                zone_bottom=zone_bottom,
                zone_top=zone_top,
            ))

        return trades

    def _convert_equity_curve(self, equity_curve_np: np.ndarray) -> List[tuple]:
        """
        Convert NumPy equity curve to Python list.

        Args:
            equity_curve_np: (N, 2) array [timestamp, equity]

        Returns:
            List of (bar_idx, datetime, equity) tuples
        """
        equity_curve = []

        for i, row in enumerate(equity_curve_np):
            timestamp = int(row[0])
            equity = float(row[1])

            # Convert Unix timestamp to datetime
            dt = pd.Timestamp(timestamp, unit='s').to_pydatetime()

            equity_curve.append((i, dt, equity))

        return equity_curve

    def get_performance_summary(self) -> dict:
        """
        Get performance summary dictionary.

        Returns:
            Dict with runtime, bars/sec, speedup estimate
        """
        if not self.equity_curve:
            return {}

        n_bars = len(self.equity_curve)
        bars_per_sec = n_bars / self.runtime_seconds if self.runtime_seconds > 0 else 0

        # Estimate speedup vs legacy (legacy ~100-300 bars/sec)
        legacy_baseline = 150  # bars/sec
        speedup_estimate = bars_per_sec / legacy_baseline if bars_per_sec > 0 else 0

        return {
            'n_bars': n_bars,
            'n_trades': len(self.closed_trades),
            'runtime_seconds': self.runtime_seconds,
            'bars_per_second': bars_per_sec,
            'speedup_estimate': speedup_estimate,
        }
