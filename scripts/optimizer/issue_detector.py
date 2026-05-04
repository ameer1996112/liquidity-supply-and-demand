from __future__ import annotations

from typing import Any


def detect_result_issues(row: dict[str, Any]) -> list[str]:
    """Return result-truth issues that make an optimizer row unsafe to trust."""
    truth = row.get("result_truth")
    if not isinstance(truth, dict):
        return ["missing_result_truth"]

    issues: list[str] = []
    if truth.get("evidence_required") and truth.get("trust_status") != "trusted":
        issues.append(f"result_truth={truth.get('trust_status') or 'untrusted'}")
    for check in truth.get("missing_evidence") or []:
        issues.append(f"missing_evidence:{check}")
    for reason in truth.get("rejection_reasons") or []:
        issues.append(f"result_truth_rejected:{reason}")
    return issues
