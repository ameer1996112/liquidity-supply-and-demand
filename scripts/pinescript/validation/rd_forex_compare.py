"""Compare protected-reference RD Forex fixtures with LAB debug exports."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REQUIRED_FIXTURE_FIELDS = {
    "symbol",
    "feed",
    "timeframe",
    "zone_id",
    "model",
    "zone_type",
    "origin_time",
    "detection_time",
    "confirmation_time",
    "top",
    "bottom",
    "evidence",
}
BOUNDARY_FIELDS = ("top", "bottom")
TIMESTAMP_FIELDS = ("origin_time", "detection_time", "confirmation_time")
LIFECYCLE_FIELDS = ("liquidity_swept", "target_swept", "touched")


def _load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Fixture JSON must be an array of objects")
    return [dict(row) for row in data]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL line {line_number} is not an object")
            rows.append(row)
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_events(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise ValueError(f"Unsupported input extension: {path.suffix}")


def validate_fixture(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen_keys: dict[tuple[str, str, str, str, str, str], int] = {}
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_FIXTURE_FIELDS - row.keys())
        evidence = row.get("evidence")
        if missing:
            errors.append({"row": index, "error": "missing_fields", "fields": missing})
        if not evidence:
            errors.append({"row": index, "error": "missing_evidence"})
        key = _key(row)
        if key in seen_keys:
            errors.append({"row": index, "error": "duplicate_fixture_key", "first_row": seen_keys[key], "key": key})
        else:
            seen_keys[key] = index
    return errors


def _key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("symbol") or ""),
        str(row.get("feed") or ""),
        str(row.get("timeframe") or ""),
        str(row.get("model") or ""),
        str(row.get("zone_type") or ""),
        str(row.get("origin_time") or ""),
    )


def _float_value(value: Any) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def _compare_matched(expected: dict[str, Any], actual: dict[str, Any], tick_size: float) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for field in BOUNDARY_FIELDS:
        exp = _float_value(expected.get(field))
        act = _float_value(actual.get(field))
        if exp is None or act is None or abs(exp - act) > tick_size:
            mismatches.append({"type": "boundary", "field": field, "expected": exp, "actual": act})
    for field in TIMESTAMP_FIELDS:
        if str(expected.get(field) or "") != str(actual.get(field) or ""):
            mismatches.append(
                {"type": "timestamp", "field": field, "expected": expected.get(field), "actual": actual.get(field)}
            )
    for field in LIFECYCLE_FIELDS:
        if field in expected and str(expected.get(field)).lower() != str(actual.get(field)).lower():
            mismatches.append(
                {"type": "lifecycle", "field": field, "expected": expected.get(field), "actual": actual.get(field)}
            )
    if actual.get("detection_time") and actual.get("origin_time") and int(actual["detection_time"]) < int(actual["origin_time"]):
        mismatches.append({"type": "repaint", "field": "detection_time", "actual": actual.get("detection_time")})
    return mismatches


def compare_events(
    fixture_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    *,
    tick_size: float,
) -> dict[str, Any]:
    fixture_errors = validate_fixture(fixture_rows)
    expected_by_key: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    actual_by_key: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in fixture_rows:
        expected_by_key[_key(row)].append(row)
    for row in actual_rows:
        if row.get("event") == "ZONE_CONFIRMED_NON_EXECUTABLE":
            actual_by_key[_key(row)].append(row)

    missing = []
    extra = []
    mismatches = []
    all_keys = sorted(set(expected_by_key) | set(actual_by_key))
    for key in all_keys:
        expected_group = expected_by_key.get(key, [])
        actual_group = actual_by_key.get(key, [])
        matched_count = min(len(expected_group), len(actual_group))
        missing.extend(expected_group[matched_count:])
        extra.extend(actual_group[matched_count:])
        for index in range(matched_count):
            for mismatch in _compare_matched(expected_group[index], actual_group[index], tick_size):
                mismatch["key"] = key
                mismatch["match_index"] = index
                mismatches.append(mismatch)

    duplicate_actuals = []
    for key in sorted(actual_by_key):
        expected_count = len(expected_by_key.get(key, []))
        actual_count = len(actual_by_key[key])
        if expected_count > 0 and actual_count > expected_count:
            duplicate_actuals.append({"key": key, "expected_count": expected_count, "actual_count": actual_count})

    return {
        "fixture_errors": fixture_errors,
        "summary": {
            "expected": len(fixture_rows),
            "actual_confirmed": sum(len(group) for group in actual_by_key.values()),
            "missing": len(missing),
            "extra": len(extra),
            "mismatches": len(mismatches),
            "duplicate_actuals": len(duplicate_actuals),
        },
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "duplicate_actuals": duplicate_actuals,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--tick-size", default=0.0001, type=float)
    args = parser.parse_args()

    report = compare_events(load_events(args.fixture), load_events(args.actual), tick_size=args.tick_size)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if report["fixture_errors"] or report["missing"] or report["extra"] or report["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
