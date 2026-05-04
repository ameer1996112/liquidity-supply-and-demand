from __future__ import annotations

from typing import Any

from .audit_result import audit_result


def build_production_report(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build a compact trust report for persisted optimizer results."""
    counts: dict[str, int] = {}
    audited: dict[str, dict[str, Any]] = {}
    for symbol, row in sorted(results.items()):
        audit = audit_result(row)
        status = str(audit.get("trust_status") or "untrusted")
        counts[status] = counts.get(status, 0) + 1
        audited[symbol] = audit
    return {
        "schema_version": 1,
        "counts": counts,
        "results": audited,
    }
