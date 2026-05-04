from __future__ import annotations

import csv
import json

from scripts.optimizer.manual_examples_schema import (
    MANUAL_EXAMPLE_FIELDS,
    load_manual_examples,
)
from scripts.optimizer.strategy_fidelity_checker import run_fidelity_check


def _write_csv(path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_EXAMPLE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_manual_examples_schema_loads_required_fields(tmp_path) -> None:
    manual_path = tmp_path / "manual_examples.csv"
    _write_csv(
        manual_path,
        [
            {
                "symbol": "XAUUSD",
                "timeframe": "5m",
                "date": "2026-04-12",
                "time": "10:30",
                "direction": "long",
                "expected_action": "take_trade",
                "expected_zone_type": "demand",
                "expected_reason": "demand zone + inducement sweep",
                "notes": "clean London setup",
            }
        ],
    )

    examples = load_manual_examples(manual_path)

    assert len(examples) == 1
    assert examples[0].symbol == "XAUUSD"
    assert examples[0].timestamp_iso == "2026-04-12T10:30:00"
    assert examples[0].expected_action == "take_trade"


def test_strategy_fidelity_checker_classifies_mismatches_and_writes_reports(tmp_path) -> None:
    manual_path = tmp_path / "manual_examples.csv"
    actual_path = tmp_path / "pine_debug.json"
    json_report = tmp_path / "strategy_fidelity_report.json"
    md_report = tmp_path / "strategy_fidelity_report.md"
    _write_csv(
        manual_path,
        [
            {
                "symbol": "XAUUSD",
                "timeframe": "5m",
                "date": "2026-04-12",
                "time": "10:30",
                "direction": "long",
                "expected_action": "take_trade",
                "expected_zone_type": "demand",
                "expected_reason": "demand zone + inducement sweep",
                "notes": "",
            },
            {
                "symbol": "NAS100",
                "timeframe": "5m",
                "date": "2026-04-15",
                "time": "16:00",
                "direction": "short",
                "expected_action": "take_trade",
                "expected_zone_type": "supply",
                "expected_reason": "supply zone + sweep",
                "notes": "",
            },
            {
                "symbol": "EURUSD",
                "timeframe": "5m",
                "date": "2026-04-16",
                "time": "09:15",
                "direction": "long",
                "expected_action": "skip_trade",
                "expected_zone_type": "demand",
                "expected_reason": "news too close",
                "notes": "",
            },
            {
                "symbol": "USDJPY",
                "timeframe": "5m",
                "date": "2026-04-17",
                "time": "11:45",
                "direction": "long",
                "expected_action": "take_trade",
                "expected_zone_type": "demand",
                "expected_reason": "demand sweep",
                "notes": "",
            },
        ],
    )
    actual_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "XAUUSD",
                    "timeframe": "5m",
                    "timestamp": "2026-04-12T10:30:00",
                    "action": "take_trade",
                    "direction": "long",
                    "zone_type": "demand",
                    "risk_status": "ok",
                },
                {
                    "symbol": "NAS100",
                    "timeframe": "5m",
                    "timestamp": "2026-04-15T16:00:00",
                    "action": "skip_trade",
                    "blocked_reason": "missing_liquidity",
                },
                {
                    "symbol": "EURUSD",
                    "timeframe": "5m",
                    "timestamp": "2026-04-16T09:15:00",
                    "action": "take_trade",
                    "direction": "long",
                    "zone_type": "demand",
                },
                {
                    "symbol": "USDJPY",
                    "timeframe": "5m",
                    "timestamp": "2026-04-17T11:45:00",
                    "action": "take_trade",
                    "direction": "short",
                    "zone_type": "demand",
                },
            ]
        )
    )

    report = run_fidelity_check(
        manual_examples_path=manual_path,
        pine_export_path=actual_path,
        json_output_path=json_report,
        markdown_output_path=md_report,
        min_agreement=0.80,
    )

    assert report["status"] == "failed"
    assert report["agreement_rate"] == 0.25
    assert report["classification_counts"]["matched_trade"] == 1
    assert report["classification_counts"]["missed_trade"] == 1
    assert report["classification_counts"]["false_positive_trade"] == 1
    assert report["classification_counts"]["wrong_direction"] == 1
    assert json.loads(json_report.read_text())["status"] == "failed"
    assert "Strategy Fidelity Report" in md_report.read_text()
