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
    verified_symbol: str = ""
    net_profit: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    drawdown_source: str = ""
    profitable_trades: int = 0
    score: float = 0.0       # Composite optimization score
    timestamp: str = ""
    decision: dict[str, Any] = field(default_factory=dict)
    forward_metrics: dict[str, Any] = field(default_factory=dict)
    validation_metrics: dict[str, Any] = field(default_factory=dict)
    stress_results: list[dict[str, Any]] = field(default_factory=list)

    def calculate_score(self) -> None:
        """
        Scoring formula for prop-firm optimization.

        IMPORTANT: The strategy tester shows ALL-TIME max drawdown over the
        entire backtest (years). Prop firm limits apply to a 30-60 day window,
        which is typically 3-5x lower than the all-time backtest max DD.
        Therefore we do NOT hard-reject on DD — we use it as a heavy penalty.

        Formula:  PF × √trades × (1 - DD%/100)²

        Hard rejects (score = 0):
          - total_trades < 10   — insufficient sample
          - net_profit <= 0     — strategy is losing money
          - max_drawdown <= 0   — no drawdown data (invalid read)

        DD penalty (soft, not a hard cutoff):
          - (1 - DD%/100)² terms heavily penalises high-drawdown configs.
          - At DD=10%: penalty = 0.81   (minor)
          - At DD=20%: penalty = 0.64   (moderate)
          - At DD=40%: penalty = 0.36   (severe)
          - At DD=60%: penalty = 0.16   (nearly zero)

        Prop-firm compliance reporting (is_prop_firm_compliant) uses a separate
        threshold to flag results that are likely safe for the evaluation window.
        This does NOT affect scoring or which params are selected.
        """
        if (
            self.total_trades < 10
            or self.net_profit <= 0
            or self.max_drawdown <= 0
        ):
            self.score = 0.0
            return

        dd_pct = min(self.max_drawdown_pct, 99.0)   # cap to avoid negative score
        dd_penalty = max(0.0, 1.0 - dd_pct / 100.0) ** 2
        self.score = self.profit_factor * math.sqrt(self.total_trades) * dd_penalty

    def is_prop_firm_compliant(self) -> bool:
        """Return True if this result passes the prop-firm DD limit."""
        from .config import PROP_FIRM_MAX_DD_PCT
        return self.max_drawdown_pct <= PROP_FIRM_MAX_DD_PCT and self.net_profit > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (for JSON checkpoint / CSV)."""
        return {
            "symbol": self.symbol,
            "params": self.params,
            "verified_symbol": self.verified_symbol,
            "net_profit": self.net_profit,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "drawdown_source": self.drawdown_source,
            "profitable_trades": self.profitable_trades,
            "score": self.score,
            "timestamp": self.timestamp,
            "decision": self.decision,
            "forward_metrics": self.forward_metrics,
            "validation_metrics": self.validation_metrics,
            "stress_results": self.stress_results,
        }
