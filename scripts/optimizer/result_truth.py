from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


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
