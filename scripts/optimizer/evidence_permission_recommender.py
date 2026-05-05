from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .backtest_live_gap_analyzer import GAP_REPORT_OUTPUT
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.backtest_live_gap_analyzer import GAP_REPORT_OUTPUT
    from scripts.optimizer.config import RESULTS_DIR


RECOMMENDATIONS_OUTPUT = RESULTS_DIR / "evidence_permission_recommendations.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_status(gap_status: str) -> str:
    if gap_status == "REJECT_RESEARCH":
        return "REJECTED"
    return "WATCH_ONLY"


def build_evidence_permission_recommendations(
    gap_report: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now()
    approved_candidates: dict[str, Any] = {}
    watch_only: dict[str, list[str]] = {}
    blocked: dict[str, list[str]] = {}

    for symbol, row in sorted((gap_report.get("candidates") or {}).items()):
        status = str(row.get("status") or "WATCH_ONLY")
        reasons = list(row.get("detected_gaps") or [])
        if not reasons:
            reasons = [status.lower()]
        candidate_status = _candidate_status(status)
        approved_candidates[symbol] = {
            "candidate_status": candidate_status,
            "gap_status": status,
            "live_trading_permission": "NO_TRADE",
            "shadow_forward_test_permission": "WATCH_ONLY"
            if status in {"WATCH_ONLY", "CANDIDATE_FOR_SHADOW_FORWARD_TEST", "IMPLEMENTATION_GAP"}
            else "NO_TRADE",
            "reasons": reasons,
        }
        if candidate_status == "REJECTED" or status in {"NO_TRADE_EXECUTION_HEALTH_FAILED", "IMPLEMENTATION_GAP"}:
            blocked[symbol] = reasons
        else:
            watch_only[symbol] = reasons

    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_gap_status": gap_report.get("global_status", "WATCH_ONLY"),
        "approved_candidates": approved_candidates,
        "daily_trade_permissions": {
            "schema_version": 1,
            "generated_at": generated_at,
            "account_profile": "gap_analyzer_fail_closed",
            "global_decision": "NO_TRADE",
            "permissions": {},
            "blocked": blocked,
            "watch_only": watch_only,
            "reasons": [
                "backtest_live_gap_not_resolved",
                "live_bot_confirmation_required",
                "daily_trade_permissions_remain_no_trade_until_gap_fixed",
            ],
        },
    }


def write_evidence_permission_recommendations(
    gap_report_path: Path = GAP_REPORT_OUTPUT,
    output_path: Path = RECOMMENDATIONS_OUTPUT,
) -> dict[str, Any]:
    gap_report = json.loads(gap_report_path.read_text()) if gap_report_path.exists() else {"candidates": {}}
    payload = build_evidence_permission_recommendations(gap_report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    return payload


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convert gap evidence into fail-closed permission recommendations.")
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT_OUTPUT)
    parser.add_argument("--output", type=Path, default=RECOMMENDATIONS_OUTPUT)
    args = parser.parse_args(argv)
    write_evidence_permission_recommendations(args.gap_report, args.output)


if __name__ == "__main__":
    cli()
