from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RULE_TYPES = {
    "valid_demand_zone",
    "valid_supply_zone",
    "market_direction",
    "zone_formation",
    "liquidity_rule",
    "liquidity_sweep_rule",
    "break_of_structure",
    "entry_rule",
    "stop_loss_rule",
    "take_profit_rule",
    "session_rule",
    "trend_rule",
    "skip_condition",
    "bad_market_condition",
    "prop_firm_risk_rule",
    "psychology_or_non_mechanical",
}

_PREFIXES = {
    "valid_demand_zone": "dem",
    "valid_supply_zone": "sup",
    "market_direction": "dir",
    "zone_formation": "zone",
    "liquidity_rule": "liq",
    "liquidity_sweep_rule": "liq",
    "break_of_structure": "bos",
    "entry_rule": "ent",
    "stop_loss_rule": "sl",
    "take_profit_rule": "tp",
    "session_rule": "ses",
    "trend_rule": "trd",
    "skip_condition": "skip",
    "bad_market_condition": "bad",
    "prop_firm_risk_rule": "prop",
    "psychology_or_non_mechanical": "psy",
}

_TIMESTAMP_RE = re.compile(r"(?:\[|\b)(\d{1,2}:\d{2}(?::\d{2})?)(?:\]|\b)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(line: str) -> tuple[str, str]:
    timestamp = ""
    match = _TIMESTAMP_RE.search(line)
    if match:
        timestamp = match.group(1)
        line = line.replace(match.group(0), "", 1)
    return timestamp, " ".join(line.strip(" -\t").split())


def _classify(text: str) -> tuple[str, bool]:
    lower = text.lower()
    if any(word in lower for word in ("psychology", "mindset", "patience", "emotion")):
        return "psychology_or_non_mechanical", False
    if "news" in lower or "do not trade" in lower or "don't trade" in lower or "skip" in lower:
        return "skip_condition", True
    if "prop" in lower or "daily loss" in lower or "risk per trade" in lower:
        return "prop_firm_risk_rule", True
    if "stop" in lower or "sl " in lower or "beyond the zone wick" in lower:
        return "stop_loss_rule", True
    if "take profit" in lower or "tp" in lower or "1:3" in lower or "1:4" in lower:
        return "take_profit_rule", True
    if "break of structure" in lower or "bos" in lower or "structure break" in lower:
        return "break_of_structure", True
    if ("sweep" in lower or "swept" in lower) and "liquidity" in lower:
        return "liquidity_sweep_rule", True
    if "liquidity" in lower:
        return "liquidity_rule", True
    if "entry" in lower or "enter" in lower or "return to" in lower or "closes" in lower:
        return "entry_rule", True
    if "session" in lower or "london" in lower or "new york" in lower or "asia" in lower:
        return "session_rule", False
    if "trend" in lower:
        return "trend_rule", True
    if "direction" in lower or "bias" in lower:
        return "market_direction", True
    if "supply" in lower and "zone" in lower:
        return "valid_supply_zone", True
    if "demand" in lower and "zone" in lower:
        return "valid_demand_zone", True
    if "zone" in lower:
        return "zone_formation", True
    if "bad market" in lower or "choppy" in lower or "range" in lower:
        return "bad_market_condition", True
    return "psychology_or_non_mechanical", False


def _confidence(text: str, critical: bool) -> str:
    lower = text.lower()
    if any(word in lower for word in ("must", "only", "never", "always", "invalid")):
        return "high"
    return "medium" if critical else "low"


def _rule_id(rule_type: str, counters: dict[str, int]) -> str:
    prefix = _PREFIXES[rule_type]
    counters[prefix] += 1
    return f"{prefix}_{counters[prefix]:03d}"


def _markdown_report(payload: dict[str, Any]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for rule in payload["rules"]:
        counts[rule["rule_type"]] += 1
    lines = [
        "# Strategy Rulebook Report",
        "",
        f"- Status: {payload['status']}",
        f"- Mechanical rules: {payload['mechanical_rule_count']}",
        f"- Critical rules: {payload['critical_rule_count']}",
        "",
        "## Rule Counts",
    ]
    for rule_type in sorted(counts):
        lines.append(f"- {rule_type}: {counts[rule_type]}")
    return "\n".join(lines) + "\n"


def extract_rulebook(
    source_dir: Path,
    rulebook_output_path: Path,
    evidence_output_path: Path,
    markdown_output_path: Path,
) -> dict[str, Any]:
    counters: dict[str, int] = defaultdict(int)
    rules: list[dict[str, Any]] = []
    for source_file in sorted(source_dir.glob("*.txt")):
        for line in source_file.read_text(errors="ignore").splitlines():
            timestamp, text = _clean_text(line)
            if not text:
                continue
            rule_type, critical = _classify(text)
            rules.append(
                {
                    "rule_id": _rule_id(rule_type, counters),
                    "source_file": source_file.name,
                    "timestamp": timestamp,
                    "raw_text": text,
                    "normalized_rule": text.rstrip(".") + ".",
                    "rule_type": rule_type,
                    "asset_class": "all",
                    "confidence": _confidence(text, critical),
                    "status": "needs_review",
                    "pine_coverage": "manual_only" if rule_type == "psychology_or_non_mechanical" else "ambiguous",
                    "critical": critical,
                }
            )

    mechanical_count = sum(1 for rule in rules if rule["rule_type"] != "psychology_or_non_mechanical")
    payload = {
        "schema_version": 1,
        "generated_at": _now(),
        "status": "needs_review",
        "mechanical_rule_count": mechanical_count,
        "critical_rule_count": sum(1 for rule in rules if rule["critical"]),
        "rules": rules,
    }
    rulebook_output_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    rulebook_output_path.write_text(json.dumps(payload, indent=2))
    with evidence_output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rule_id",
                "source_file",
                "timestamp",
                "rule_type",
                "confidence",
                "critical",
                "pine_coverage",
                "normalized_rule",
            ],
        )
        writer.writeheader()
        for rule in rules:
            writer.writerow({field: rule[field] for field in writer.fieldnames})
    markdown_output_path.write_text(_markdown_report(payload))
    return payload


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract mechanical Liquidity S&D rules from transcript text files.")
    parser.add_argument("--source-dir", type=Path, default=Path("data/strategy_sources/videos"))
    parser.add_argument("--rulebook-output", type=Path, default=Path("data/strategy_sources/strategy_rulebook.json"))
    parser.add_argument("--evidence-output", type=Path, default=Path("data/strategy_sources/rule_evidence.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/strategy_rulebook_report.md"))
    args = parser.parse_args(argv)
    extract_rulebook(args.source_dir, args.rulebook_output, args.evidence_output, args.report_output)


if __name__ == "__main__":
    cli()
