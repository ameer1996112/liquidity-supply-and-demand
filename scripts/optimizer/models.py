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
        Prop-firm Calmar score: (net_profit / max_drawdown) × √trades

        Hard rejects (score = 0):
          - max_drawdown_pct > PROP_FIRM_MAX_DD_PCT (10%)  — fails prop-firm limit
          - total_trades < 10                              — insufficient sample
          - net_profit <= 0                                — unprofitable
          - max_drawdown <= 0                              — no drawdown data (invalid)

        For passing results: Calmar ratio × √trades rewards strategies
        that generate high return-per-risk with many trades, which is
        exactly what prop firms evaluate.
        """
        from .config import PROP_FIRM_MAX_DD_PCT

        if (
            self.total_trades < 10
            or self.net_profit <= 0
            or self.max_drawdown <= 0
            or self.max_drawdown_pct > PROP_FIRM_MAX_DD_PCT
        ):
            self.score = 0.0
            return

        calmar = self.net_profit / self.max_drawdown
        self.score = calmar * math.sqrt(self.total_trades)

    def is_prop_firm_compliant(self) -> bool:
        """Return True if this result passes the prop-firm DD limit."""
        from .config import PROP_FIRM_MAX_DD_PCT
        return self.max_drawdown_pct <= PROP_FIRM_MAX_DD_PCT and self.net_profit > 0

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
