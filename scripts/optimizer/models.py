"""
models.py — BacktestResult dataclass.
"""

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any


class NoDataForRangeError(RuntimeError):
    """Raised when TradingView cannot provide data for the requested date window."""


def params_digest(params: dict[str, Any]) -> str:
    """Stable digest for the exact params attached to a result."""
    payload = json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class ResultTruth:
    """Evidence-backed trust verdict for optimizer outputs."""

    schema_version: int = 1
    evidence_required: bool = False
    stage: str = "legacy"
    trust_status: str = "legacy_unverified"
    params_digest: str = ""
    source_params_digest: str = ""
    requested_symbol: str = ""
    requested_broker: str = ""
    requested_range: str = ""
    custom_start_date: str = ""
    custom_end_date: str = ""
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)

    @classmethod
    def production(
        cls,
        *,
        stage: str,
        params: dict[str, Any],
        requested_symbol: str,
        requested_broker: str,
        requested_range: str,
        custom_start_date: str = "",
        custom_end_date: str = "",
        source_params_digest: str = "",
    ) -> "ResultTruth":
        return cls(
            evidence_required=True,
            stage=stage,
            trust_status="untrusted",
            params_digest=params_digest(params),
            source_params_digest=source_params_digest,
            requested_symbol=requested_symbol,
            requested_broker=requested_broker,
            requested_range=requested_range,
            custom_start_date=custom_start_date or "",
            custom_end_date=custom_end_date or "",
        )

    def record(
        self,
        check: str,
        status: str,
        *,
        required: bool = True,
        reason: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.evidence[check] = {
            "status": status,
            "required": required,
            "reason": reason,
            "details": details or {},
        }

    def finalize(self) -> None:
        if not self.evidence_required:
            self.trust_status = "legacy_unverified"
            return

        self.missing_evidence = []
        self.warnings = []
        self.rejection_reasons = []
        required_checks = {
            "symbol_loaded",
            "broker_loaded",
            "strategy_tester_range_selected",
            "params_applied",
            "dialog_params_matched",
            "tv_recalculated",
            "result_hash_captured",
            "metrics_tab_selected",
        }
        if self.requested_range == "custom":
            required_checks.update(
                {
                    "custom_dates_selected",
                    "chart_history_covered",
                    "trade_coverage_verified",
                }
            )
        if self.stage in {"validation", "final_replay"}:
            required_checks.add("frozen_params_applied")
        if self.stage == "validation" or self.source_params_digest:
            required_checks.add("source_params_digest_preserved")
        if self.stage == "final_replay":
            required_checks.add("final_replay_matched_or_replaced")

        for check in sorted(required_checks - set(self.evidence)):
            self.missing_evidence.append(check)

        for check, payload in sorted(self.evidence.items()):
            status = str(payload.get("status") or "missing")
            required = bool(payload.get("required", True)) or check in required_checks
            reason = str(payload.get("reason") or "")
            if status in {"missing", "not_applicable"} and required:
                self.missing_evidence.append(check)
            elif status == "warn":
                self.warnings.append(f"{check}: {reason or 'warning'}")
            elif status == "fail":
                self.rejection_reasons.append(f"{check}: {reason or 'failed'}")

        if self.rejection_reasons:
            self.trust_status = "rejected"
        elif self.missing_evidence:
            self.trust_status = "untrusted"
        elif self.warnings:
            self.trust_status = "watch_only"
        else:
            self.trust_status = "trusted"

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return {
            "schema_version": self.schema_version,
            "evidence_required": self.evidence_required,
            "stage": self.stage,
            "trust_status": self.trust_status,
            "params_digest": self.params_digest,
            "source_params_digest": self.source_params_digest,
            "requested_symbol": self.requested_symbol,
            "requested_broker": self.requested_broker,
            "requested_range": self.requested_range,
            "custom_start_date": self.custom_start_date,
            "custom_end_date": self.custom_end_date,
            "evidence": self.evidence,
            "missing_evidence": self.missing_evidence,
            "warnings": self.warnings,
            "rejection_reasons": self.rejection_reasons,
        }


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
    result_truth: ResultTruth = field(default_factory=ResultTruth)

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

    def is_prop_firm_compliant(self, dd_limit: float | None = None) -> bool:
        """Return True if this result passes the configured DD limit."""
        if dd_limit is None:
            from .config import PROP_FIRM_MAX_DD_PCT
            dd_limit = PROP_FIRM_MAX_DD_PCT
        return self.max_drawdown_pct <= float(dd_limit) and self.net_profit > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (for JSON checkpoint / CSV)."""
        truth = self.result_truth.to_dict()
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
            "result_truth": truth,
            "trust_status": truth["trust_status"],
        }
