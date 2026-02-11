"""
Enhanced backtest engine with strict N+1 parity support.

Execution Modes:
1. process_orders_on_close=True (TradingView default)
   - Signal at bar N close
   - Fill at bar N close (with slippage)

2. process_orders_on_next_open=True (Strict N+1 parity)
   - Signal at bar N close
   - Fill at bar N+1 open (with slippage)
   - More realistic for live trading

This module extends the legacy engine.py with N+1 execution support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

import numpy as np
import pandas as pd

from app.engine import (
    Order,
    OrderSide,
    OrderType,
    Position,
    ClosedTrade,
    round_to_tick,
    apply_slippage_entry,
    apply_slippage_exit
)

logger = logging.getLogger(__name__)


@dataclass
class EnhancedBacktestEngine:
    """
    Enhanced backtest engine with configurable execution semantics.

    Key difference from legacy engine:
    - Supports process_orders_on_next_open mode
    - Signal at bar N → Fill at bar N+1 open
    - More realistic slippage modeling
    """

    tick_size: float
    slippage_ticks: int = 3
    initial_equity: float = 100_000.0
    commission_pct: float = 0.0
    pyramiding: int = 0
    max_bars_held: Optional[int] = 36

    # Execution mode
    process_orders_on_close: bool = True  # TradingView default
    process_orders_on_next_open: bool = False  # Strict N+1 parity

    # State
    equity: float = 0.0
    position: Optional[Position] = None
    closed_trades: List[ClosedTrade] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)

    # Pending orders (for N+1 execution)
    pending_orders: List[Order] = field(default_factory=list)

    def reset(self) -> None:
        """Reset engine state."""
        self.equity = self.initial_equity
        self.position = None
        self.closed_trades = []
        self.equity_curve = []
        self.pending_orders = []

    def _check_exits(
        self,
        bar_idx: int,
        bar_time: datetime,
        high: float,
        low: float,
        close: float,
    ) -> Optional[ClosedTrade]:
        """Check if SL/TP/time hit on this bar."""
        if self.position is None:
            return None

        pos = self.position
        exit_price = None
        reason = ""
        bars_held = bar_idx - pos.entry_bar_idx

        # Time-based exit
        if self.max_bars_held is not None and bars_held >= self.max_bars_held:
            exit_price = apply_slippage_exit(close, pos.side, self.slippage_ticks, self.tick_size)
            reason = "time"

        elif pos.side == OrderSide.LONG:
            # SL hit
            if low <= pos.stop_price and pos.stop_price > 0:
                exit_price = apply_slippage_exit(pos.stop_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "stop"
            # TP hit
            elif pos.limit_price is not None and high >= pos.limit_price:
                exit_price = apply_slippage_exit(pos.limit_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "limit"
        else:
            # Short
            if high >= pos.stop_price and pos.stop_price > 0:
                exit_price = apply_slippage_exit(pos.stop_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "stop"
            elif pos.limit_price is not None and low <= pos.limit_price:
                exit_price = apply_slippage_exit(pos.limit_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "limit"

        if exit_price is not None and reason:
            pnl = (exit_price - pos.entry_price) * pos.qty if pos.side == OrderSide.LONG else (pos.entry_price - exit_price) * pos.qty
            pnl *= (1 - self.commission_pct / 100)
            pnl_pct = (pnl / (pos.entry_price * pos.qty)) * 100 if pos.qty else 0

            trade = ClosedTrade(
                entry_time=pos.entry_time,
                exit_time=bar_time,
                side=pos.side,
                qty=pos.qty,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                bars_held=bars_held,
                reason=reason,
                entry_comment=pos.entry_comment,
                stop_price=pos.stop_price,
                limit_price=pos.limit_price,
                zone_bottom=pos.zone_bottom,
                zone_top=pos.zone_top,
            )
            self.position = None
            self.equity += pnl
            self.closed_trades.append(trade)
            return trade
        return None

    def _fill_pending_orders_at_open(
        self,
        bar_idx: int,
        bar_time: datetime,
        bar_open: float
    ) -> None:
        """
        Fill pending orders at bar open (N+1 execution).

        Called at start of bar N+1 to fill orders placed at bar N close.
        """
        if not self.pending_orders:
            return

        for order in self.pending_orders:
            if order.order_type != OrderType.ENTRY:
                continue

            if self.pyramiding == 0 and self.position is not None:
                continue

            # Fill at bar open (instead of previous bar close)
            fill_price = apply_slippage_entry(bar_open, order.side, self.slippage_ticks, self.tick_size)

            stop_price = order.stop_price
            limit_price = order.limit_price
            if stop_price is not None:
                stop_price = round_to_tick(stop_price, self.tick_size)
            if limit_price is not None:
                limit_price = round_to_tick(limit_price, self.tick_size)

            self.position = Position(
                side=order.side,
                qty=order.qty,
                entry_price=fill_price,
                entry_bar_idx=bar_idx,
                entry_time=bar_time,
                stop_price=stop_price or 0.0,
                limit_price=limit_price,
                entry_comment=order.comment or "",
                zone_bottom=getattr(order, "zone_bottom", None),
                zone_top=getattr(order, "zone_top", None),
            )

            logger.debug(
                f"Filled pending order at bar {bar_idx} open: "
                f"{order.side.value} {order.qty} @ {fill_price:.2f}"
            )

        # Clear pending orders after filling
        self.pending_orders = []

    def process_bar(
        self,
        bar_idx: int,
        bar: pd.Series,
        orders: List[Order],
    ) -> Optional[ClosedTrade]:
        """
        Process one bar with configurable execution semantics.

        Execution modes:
        1. process_orders_on_close=True (default)
           - Fill orders at bar close (legacy behavior)

        2. process_orders_on_next_open=True
           - Queue orders, fill at next bar open

        Returns closed trade if one was exited this bar.
        """
        bar_time = bar["time"]
        if isinstance(bar_time, (np.datetime64,)):
            bar_time = pd.Timestamp(bar_time).to_pydatetime()

        bar_open = float(bar["open"])
        high, low, close = float(bar["high"]), float(bar["low"]), float(bar["close"])

        # STEP 1: Fill pending orders at open (if using N+1 execution)
        if self.process_orders_on_next_open:
            self._fill_pending_orders_at_open(bar_idx, bar_time, bar_open)

        # STEP 2: Check exits (SL/TP)
        closed = self._check_exits(bar_idx, bar_time, high, low, close)

        # STEP 3: Process new entry orders
        if self.process_orders_on_close:
            # Fill at bar close (TradingView default)
            for order in orders:
                if order.order_type != OrderType.ENTRY:
                    continue
                if self.pyramiding == 0 and self.position is not None:
                    continue

                fill_price = apply_slippage_entry(close, order.side, self.slippage_ticks, self.tick_size)
                stop_price = order.stop_price
                limit_price = order.limit_price
                if stop_price is not None:
                    stop_price = round_to_tick(stop_price, self.tick_size)
                if limit_price is not None:
                    limit_price = round_to_tick(limit_price, self.tick_size)

                self.position = Position(
                    side=order.side,
                    qty=order.qty,
                    entry_price=fill_price,
                    entry_bar_idx=bar_idx,
                    entry_time=bar_time,
                    stop_price=stop_price or 0.0,
                    limit_price=limit_price,
                    entry_comment=order.comment or "",
                    zone_bottom=getattr(order, "zone_bottom", None),
                    zone_top=getattr(order, "zone_top", None),
                )

        elif self.process_orders_on_next_open:
            # Queue orders for next bar open
            self.pending_orders.extend(orders)

        # STEP 4: Update equity curve
        self.equity_curve.append((bar_idx, bar_time, self.equity))
        return closed

    def run(
        self,
        candles: pd.DataFrame,
        on_bar: Callable[[int, pd.Series, pd.DataFrame, bool], List[Order]],
    ) -> List[ClosedTrade]:
        """
        Run backtest over candles.

        on_bar(bar_idx, bar, history, has_position) -> list[Order]
        """
        self.reset()

        for i in range(len(candles)):
            bar = candles.iloc[i]
            history = candles.iloc[: i + 1]
            has_position = self.position is not None

            # Strategy generates signals at bar close
            orders = on_bar(i, bar, history, has_position)

            # Engine processes orders based on execution mode
            self.process_bar(i, bar, orders)

        return self.closed_trades


# ========== Convenience Functions ==========

def run_backtest_with_n_plus_1(
    candles: pd.DataFrame,
    strategy,
    config
) -> tuple:
    """
    Run backtest with strict N+1 execution (signal at N, fill at N+1 open).

    Args:
        candles: OHLC DataFrame
        strategy: SNDStrategy instance
        config: BacktestConfig instance

    Returns:
        (trades, equity_curve, engine)
    """
    engine = EnhancedBacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=config.slippage_ticks,
        initial_equity=config.account_size_usd,
        commission_pct=config.commission_pct,
        pyramiding=config.pyramiding,
        max_bars_held=config.max_bars_held,
        process_orders_on_close=False,
        process_orders_on_next_open=True  # Enable N+1 execution
    )

    def on_bar(bar_idx: int, bar: pd.Series, history: pd.DataFrame, has_position: bool):
        return strategy.on_bar(bar_idx, bar, history, has_position)

    trades = engine.run(candles, on_bar)
    return trades, engine.equity_curve, engine


def run_backtest_tradingview_mode(
    candles: pd.DataFrame,
    strategy,
    config
) -> tuple:
    """
    Run backtest with TradingView semantics (signal at N, fill at N close).

    Args:
        candles: OHLC DataFrame
        strategy: SNDStrategy instance
        config: BacktestConfig instance

    Returns:
        (trades, equity_curve, engine)
    """
    engine = EnhancedBacktestEngine(
        tick_size=config.tick_size,
        slippage_ticks=config.slippage_ticks,
        initial_equity=config.account_size_usd,
        commission_pct=config.commission_pct,
        pyramiding=config.pyramiding,
        max_bars_held=config.max_bars_held,
        process_orders_on_close=True,  # TradingView default
        process_orders_on_next_open=False
    )

    def on_bar(bar_idx: int, bar: pd.Series, history: pd.DataFrame, has_position: bool):
        return strategy.on_bar(bar_idx, bar, history, has_position)

    trades = engine.run(candles, on_bar)
    return trades, engine.equity_curve, engine
