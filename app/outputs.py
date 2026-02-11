"""
Outputs: trades.csv, equity curve, summary metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.engine import ClosedTrade, OrderSide


@dataclass
class BacktestSummary:
    """Summary metrics."""
    net_profit: float
    gross_profit: float
    gross_loss: float
    win_count: int
    loss_count: int
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    avg_trade: float
    avg_bars_held: float


def trades_to_dataframe(trades: List[ClosedTrade]) -> pd.DataFrame:
    """Convert closed trades to DataFrame."""
    rows = []
    for t in trades:
        rows.append({
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "side": t.side.value,
            "qty": t.qty,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "bars_held": t.bars_held,
            "reason": t.reason,
            "entry_model": t.entry_comment,
            "stop_price": t.stop_price,
            "limit_price": t.limit_price,
            "zone_bottom": t.zone_bottom,
            "zone_top": t.zone_top,
        })
    return pd.DataFrame(rows)


def compute_summary(trades: List[ClosedTrade], equity_curve: List[tuple]) -> BacktestSummary:
    """Compute summary metrics."""
    if not trades:
        return BacktestSummary(
            net_profit=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            win_count=0,
            loss_count=0,
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            avg_trade=0.0,
            avg_bars_held=0.0,
        )

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    net_profit = gross_profit - gross_loss
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # Max drawdown from equity curve
    max_dd = 0.0
    peak = 0.0
    for _, _, eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    return BacktestSummary(
        net_profit=net_profit,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        win_count=len(wins),
        loss_count=len(losses),
        total_trades=len(trades),
        win_rate=len(wins) / len(trades) * 100 if trades else 0.0,
        profit_factor=profit_factor,
        max_drawdown=max_dd,
        avg_trade=net_profit / len(trades) if trades else 0.0,
        avg_bars_held=sum(t.bars_held for t in trades) / len(trades) if trades else 0.0,
    )


def write_trades_csv(trades: List[ClosedTrade], path: Path) -> None:
    """Write trades to CSV."""
    df = trades_to_dataframe(trades)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_equity_csv(equity_curve: List[tuple], path: Path) -> None:
    """Write equity curve to CSV."""
    df = pd.DataFrame(equity_curve, columns=["bar_idx", "time", "equity"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def print_summary(summary: BacktestSummary) -> None:
    """Print summary to stdout."""
    print("\n=== BACKTEST SUMMARY ===")
    print(f"Net Profit:     {summary.net_profit:,.2f}")
    print(f"Gross Profit:   {summary.gross_profit:,.2f}")
    print(f"Gross Loss:     {summary.gross_loss:,.2f}")
    print(f"Total Trades:   {summary.total_trades}")
    print(f"Win Rate:       {summary.win_rate:.1f}%")
    print(f"Profit Factor:  {summary.profit_factor:.2f}")
    print(f"Max Drawdown:   {summary.max_drawdown:,.2f}")
    print(f"Avg Trade:      {summary.avg_trade:,.2f}")
    print(f"Avg Bars Held:  {summary.avg_bars_held:.1f}")
