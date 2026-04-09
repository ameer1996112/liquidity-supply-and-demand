"""
models.py — BacktestResult dataclass.
"""

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BacktestResult:
    """Single backtest result for a parameter combination."""
    symbol: str
    params: dict
    net_profit: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    profitable_trades: int = 0
    score: float = 0.0       # Composite optimization score
    timestamp: str = ""

    def calculate_score(self) -> None:
        """
        Composite score: PF * sqrt(trades) * (1 - DD%/100)²

        DD penalty is squared to heavily penalise high drawdown,
        which is the priority for prop-firm accounts.
        """
        if self.total_trades < 10 or self.profit_factor <= 0:
            self.score = 0.0
            return
        trade_factor = math.sqrt(self.total_trades)
        dd_penalty = max(0.0, 1.0 - self.max_drawdown_pct / 100.0)
        self.score = self.profit_factor * trade_factor * (dd_penalty ** 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (for JSON checkpoint / CSV)."""
        return {
            "symbol": self.symbol,
            "params": self.params,
            "net_profit": self.net_profit,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "profitable_trades": self.profitable_trades,
            "score": self.score,
            "timestamp": self.timestamp,
        }
