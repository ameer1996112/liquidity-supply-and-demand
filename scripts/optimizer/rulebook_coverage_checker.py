from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_COVERAGE = {"implemented", "missing", "manual_only", "ambiguous"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Rulebook Coverage Report",
        "",
        f"- Status: {report['status']}",
        f"- Critical rules: {report['critical_rule_count']}",
        f"- Missing critical Pine rules: {len(report['missing_critical_rule_ids'])}",
        f"- Ambiguous rules: {len(report['ambiguous_rule_ids'])}",
    ]
    if report["missing_critical_rule_ids"]:
        lines.extend(["", "## Missing Critical Rules"])
        lines.extend(f"- {rule_id}" for rule_id in report["missing_critical_rule_ids"])
    if report["ambiguous_rule_ids"]:
        lines.extend(["", "## Needs Human Review"])
        lines.extend(f"- {rule_id}" for rule_id in report["ambiguous_rule_ids"])
    return "\n".join(lines) + "\n"


def check_rulebook_coverage(rulebook_path: Path, markdown_output_path: Path | None = None) -> dict[str, Any]:
    payload = json.loads(rulebook_path.read_text())
    rules = [rule for rule in payload.get("rules", []) if isinstance(rule, dict)]
    missing_critical = [
        str(rule.get("rule_id"))
        for rule in rules
        if bool(rule.get("critical")) and rule.get("pine_coverage") == "missing"
    ]
    ambiguous = [
        str(rule.get("rule_id"))
        for rule in rules
        if rule.get("pine_coverage") == "ambiguous" or rule.get("status") == "needs_review"
    ]
    invalid = [
        str(rule.get("rule_id"))
        for rule in rules
        if rule.get("pine_coverage") not in ALLOWED_COVERAGE
    ]
    status = "blocked" if missing_critical or invalid else ("needs_review" if ambiguous else "passed")
    report = {
        "schema_version": 1,
        "generated_at": _now(),
        "status": status,
        "critical_rule_count": sum(1 for rule in rules if bool(rule.get("critical"))),
        "missing_critical_rule_ids": missing_critical,
        "ambiguous_rule_ids": ambiguous,
        "invalid_coverage_rule_ids": invalid,
    }
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(_markdown(report))
    return report


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check Pine/manual/missing coverage for extracted strategy rules.")
    parser.add_argument("--rulebook", type=Path, default=Path("data/strategy_sources/strategy_rulebook.json"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/strategy_rulebook_coverage_report.md"))
    args = parser.parse_args(argv)
    print(json.dumps(check_rulebook_coverage(args.rulebook, args.report_output), indent=2))


if __name__ == "__main__":
    cli()
