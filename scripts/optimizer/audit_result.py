from __future__ import annotations

from typing import Any

from .issue_detector import detect_result_issues


def audit_result(row: dict[str, Any]) -> dict[str, Any]:
    """Summarize whether one persisted optimizer result is production-trustworthy."""
    issues = detect_result_issues(row)
    truth = row.get("result_truth") if isinstance(row.get("result_truth"), dict) else {}
    return {
        "trust_status": truth.get("trust_status") if not issues else "untrusted",
        "issues": issues,
    }
