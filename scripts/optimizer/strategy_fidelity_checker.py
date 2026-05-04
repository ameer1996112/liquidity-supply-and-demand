from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .manual_examples_schema import ManualTradeExample, load_manual_examples
except ImportError:  # Allows `python scripts/optimizer/strategy_fidelity_checker.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.optimizer.manual_examples_schema import (
        ManualTradeExample,
        load_manual_examples,
    )

MATCHED_TRADE = "matched_trade"
MISSED_TRADE = "missed_trade"
FALSE_POSITIVE_TRADE = "false_positive_trade"
WRONG_DIRECTION = "wrong_direction"
WRONG_SESSION = "wrong_session"
WRONG_ZONE = "wrong_zone"
WRONG_RISK = "wrong_risk"

TRADE_ACTIONS = {"take_trade", "trade", "entry", "alert"}
SKIP_ACTIONS = {"skip_trade", "skip", "blocked", "no_trade"}


def _parse_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _load_pine_export(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        if isinstance(payload, dict):
            payload = payload.get("events") or payload.get("trades") or payload.get("results")
        if not isinstance(payload, list):
            raise ValueError("Pine export JSON must be a list or contain events/trades/results")
        return [item for item in payload if isinstance(item, dict)]

    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _event_action(event: dict[str, Any]) -> str:
    return _norm(event.get("action") or event.get("event") or event.get("expected_action"))


def _is_trade(event: dict[str, Any]) -> bool:
    action = _event_action(event)
    if action in TRADE_ACTIONS:
        return True
    if action in SKIP_ACTIONS:
        return False
    return bool(event.get("direction")) and not event.get("blocked_reason")


def _matching_events(
    example: ManualTradeExample,
    events: list[dict[str, Any]],
    tolerance_minutes: int,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for event in events:
        if _norm(event.get("symbol")) != _norm(example.symbol):
            continue
        if _norm(event.get("timeframe")) and _norm(event.get("timeframe")) != _norm(example.timeframe):
            continue
        timestamp = _parse_timestamp(event.get("timestamp") or event.get("time"))
        if timestamp is None:
            continue
        delta_seconds = abs((timestamp - example.timestamp).total_seconds())
        if delta_seconds <= tolerance_minutes * 60:
            matches.append(event)
    return matches


def _classify_example(
    example: ManualTradeExample,
    events: list[dict[str, Any]],
    tolerance_minutes: int,
) -> dict[str, Any]:
    matches = _matching_events(example, events, tolerance_minutes)
    trade = next((event for event in matches if _is_trade(event)), None)
    blocked = next((event for event in matches if not _is_trade(event)), None)

    if example.expects_skip:
        classification = FALSE_POSITIVE_TRADE if trade else MATCHED_TRADE
    elif trade is None:
        classification = MISSED_TRADE
    elif _norm(trade.get("direction")) != _norm(example.direction):
        classification = WRONG_DIRECTION
    elif example.expected_zone_type and _norm(trade.get("zone_type")) != _norm(example.expected_zone_type):
        classification = WRONG_ZONE
    elif _norm(trade.get("session_status")) in {"wrong", "blocked"}:
        classification = WRONG_SESSION
    elif _norm(trade.get("risk_status")) not in {"", "ok", "passed"}:
        classification = WRONG_RISK
    else:
        classification = MATCHED_TRADE

    selected = trade or blocked or {}
    return {
        "symbol": example.symbol,
        "timeframe": example.timeframe,
        "timestamp": example.timestamp_iso,
        "expected_action": example.expected_action,
        "expected_direction": example.direction,
        "expected_zone_type": example.expected_zone_type,
        "classification": classification,
        "pine_action": _event_action(selected),
        "pine_direction": selected.get("direction"),
        "pine_zone_type": selected.get("zone_type"),
        "blocked_reason": selected.get("blocked_reason"),
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Strategy Fidelity Report",
        "",
        f"- Status: {report['status']}",
        f"- Agreement rate: {report['agreement_rate']:.2%}",
        f"- Minimum required: {report['minimum_agreement']:.2%}",
        f"- Examples: {report['example_count']}",
        "",
        "## Classifications",
    ]
    for classification, count in sorted(report["classification_counts"].items()):
        lines.append(f"- {classification}: {count}")
    lines.extend(["", "## Mismatches"])
    for item in report["examples"]:
        if item["classification"] == MATCHED_TRADE:
            continue
        lines.append(
            f"- {item['symbol']} {item['timeframe']} {item['timestamp']}: "
            f"{item['classification']}"
        )
    return "\n".join(lines) + "\n"


def run_fidelity_check(
    *,
    manual_examples_path: Path,
    pine_export_path: Path,
    json_output_path: Path,
    markdown_output_path: Path,
    min_agreement: float = 0.80,
    tolerance_minutes: int = 5,
) -> dict[str, Any]:
    examples = load_manual_examples(manual_examples_path)
    events = _load_pine_export(pine_export_path)
    classified = [
        _classify_example(example, events, tolerance_minutes)
        for example in examples
    ]
    counts = Counter(item["classification"] for item in classified)
    matched = counts[MATCHED_TRADE]
    agreement_rate = matched / len(classified) if classified else 0.0
    report = {
        "schema_version": 1,
        "status": "passed" if agreement_rate >= min_agreement else "failed",
        "agreement_rate": round(agreement_rate, 4),
        "minimum_agreement": min_agreement,
        "example_count": len(classified),
        "classification_counts": dict(counts),
        "examples": classified,
    }
    json_output_path.write_text(json.dumps(report, indent=2))
    markdown_output_path.write_text(_markdown_report(report))
    return report


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare manual SND examples against Pine debug exports.")
    parser.add_argument("manual_examples_csv", type=Path)
    parser.add_argument("pine_export", type=Path)
    parser.add_argument("--json-output", type=Path, default=Path("strategy_fidelity_report.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("strategy_fidelity_report.md"))
    parser.add_argument("--min-agreement", type=float, default=0.80)
    parser.add_argument("--tolerance-minutes", type=int, default=5)
    args = parser.parse_args(argv)

    run_fidelity_check(
        manual_examples_path=args.manual_examples_csv,
        pine_export_path=args.pine_export,
        json_output_path=args.json_output,
        markdown_output_path=args.markdown_output,
        min_agreement=args.min_agreement,
        tolerance_minutes=args.tolerance_minutes,
    )


if __name__ == "__main__":
    cli()
