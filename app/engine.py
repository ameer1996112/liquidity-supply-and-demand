"""
TradingView-like execution engine: bar-by-bar backtest.

Semantics:
- calc_on_every_tick=False: evaluate strategy once per bar (on bar close)
- process_orders_on_close=True: orders placed on bar N are filled at bar N's close
- Slippage in ticks: long entry = close + slippage*tick_size, short = close - slippage*tick_size
- pyramiding=0: only one open position
- All fill prices rounded to tick_size
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


@dataclass
class Order:
    """Order placed by strategy (filled at bar close with slippage)."""
    side: OrderSide
    order_type: OrderType
    qty: float
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    comment: str = ""
    zone_bottom: Optional[float] = None
    zone_top: Optional[float] = None


@dataclass
class Position:
    """Open position."""
    side: OrderSide
    qty: float
    entry_price: float
    entry_bar_idx: int
    entry_time: datetime
    stop_price: float
    limit_price: Optional[float] = None
    zone_id: Optional[int] = None
    entry_comment: str = ""
    zone_bottom: Optional[float] = None
    zone_top: Optional[float] = None


@dataclass
class ClosedTrade:
    """Closed trade for reporting."""
    entry_time: datetime
    exit_time: datetime
    side: OrderSide
    qty: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    bars_held: int
    reason: str  # "stop", "limit", "close", "time"
    entry_comment: str = ""  # FLIP, BREAK_CANDLE, DIR_CLOSE
    stop_price: float = 0.0
    limit_price: Optional[float] = None
    zone_bottom: Optional[float] = None
    zone_top: Optional[float] = None


def round_to_tick(price: float, tick_size: float) -> float:
    """Round price to tick size."""
    if tick_size <= 0:
        return price
    return round(price / tick_size) * tick_size


def apply_slippage_entry(close: float, side: OrderSide, slippage_ticks: int, tick_size: float) -> float:
    """Apply slippage for entry: long = close + slippage, short = close - slippage."""
    slip = slippage_ticks * tick_size
    if side == OrderSide.LONG:
        return round_to_tick(close + slip, tick_size)
    return round_to_tick(close - slip, tick_size)


def apply_slippage_exit(price: float, side: OrderSide, slippage_ticks: int, tick_size: float) -> float:
    """Apply slippage for exit: long exit = price - slippage (selling), short exit = price + slippage (buying)."""
    slip = slippage_ticks * tick_size
    if side == OrderSide.LONG:
        return round_to_tick(price - slip, tick_size)
    return round_to_tick(price + slip, tick_size)


@dataclass
class BacktestEngine:
    """
    Event-driven backtest engine matching TradingView Pine semantics.
    """

    tick_size: float
    slippage_ticks: int = 3
    initial_equity: float = 100_000.0
    commission_pct: float = 0.0
    pyramiding: int = 0  # 0 = only one position
    max_bars_held: Optional[int] = 36  # Time-based exit (Pine default). None = no limit.

    # State
    equity: float = 0.0
    position: Optional[Position] = None
    closed_trades: List[ClosedTrade] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)  # (bar_idx, time, equity)

    def reset(self) -> None:
        """Reset engine state."""
        self.equity = self.initial_equity
        self.position = None
        self.closed_trades = []
        self.equity_curve = []

    def _check_exits(
        self,
        bar_idx: int,
        bar_time: datetime,
        high: float,
        low: float,
        close: float,
    ) -> Optional[ClosedTrade]:
        """Check if SL/TP/time hit on this bar. Returns ClosedTrade if exited."""
        if self.position is None:
            return None

        pos = self.position
        exit_price = None
        reason = ""
        bars_held = bar_idx - pos.entry_bar_idx

        # Time-based exit (Pine: strategy.close_all when bars_held >= max_bars_held)
        if self.max_bars_held is not None and bars_held >= self.max_bars_held:
            exit_price = apply_slippage_exit(close, pos.side, self.slippage_ticks, self.tick_size)
            reason = "time"

        elif pos.side == OrderSide.LONG:
            if low <= pos.stop_price and pos.stop_price > 0:
                exit_price = apply_slippage_exit(pos.stop_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "stop"
            elif pos.limit_price is not None and high >= pos.limit_price:
                exit_price = apply_slippage_exit(pos.limit_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "limit"
        else:
            if high >= pos.stop_price and pos.stop_price > 0:
                exit_price = apply_slippage_exit(pos.stop_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "stop"
            elif pos.limit_price is not None and low <= pos.limit_price:
                exit_price = apply_slippage_exit(pos.limit_price, pos.side, self.slippage_ticks, self.tick_size)
                reason = "limit"

        if exit_price is not None and reason:
            pnl = (exit_price - pos.entry_price) * pos.qty if pos.side == OrderSide.LONG else (pos.entry_price - exit_price) * pos.qty
            pnl *= (1 - self.commission_pct / 100)  # Commission
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

    def process_bar(
        self,
        bar_idx: int,
        bar: pd.Series,
        orders: List[Order],
    ) -> Optional[ClosedTrade]:
        """
        Process one bar: check exits first, then apply new entries (process_orders_on_close).

        orders: list of orders from strategy.on_bar()
        Returns closed trade if one was exited this bar.
        """
        bar_time = bar["time"]
        if isinstance(bar_time, (np.datetime64,)):
            bar_time = pd.Timestamp(bar_time).to_pydatetime()
        high, low, close = float(bar["high"]), float(bar["low"]), float(bar["close"])

        # 1. Check exits (SL/TP) on this bar
        closed = self._check_exits(bar_idx, bar_time, high, low, close)

        # 2. Apply entry orders (process_orders_on_close: fill at bar close)
        for order in orders:
            if order.order_type != OrderType.ENTRY:
                continue
            if self.pyramiding == 0 and self.position is not None:
                continue  # No stacking

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
        history: candles up to and including current bar (for lookback).
        """
        self.reset()
        history = []

        for i in range(len(candles)):
            bar = candles.iloc[i]
            history = candles.iloc[: i + 1]
            has_position = self.position is not None

            orders = on_bar(i, bar, history, has_position)
            self.process_bar(i, bar, orders)

        return self.closed_trades
