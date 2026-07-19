from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
from pathlib import Path
from typing import Any

from scripts.rd_concepts_pipeline.common import read_jsonl
from scripts.rd_concepts_pipeline.reference_detector import (
    Bar,
    Direction,
    Formation,
    Geometry,
    ZoneState,
    detect_zones,
)


class BenchmarkStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NO_APPROVED_CASES = "NO_APPROVED_CASES"


@dataclass(frozen=True)
class BenchmarkIssue:
    case_id: str
    kind: str
    entity_key: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "kind": self.kind,
            "entity_key": self.entity_key,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    label_status: str
    evaluated: bool
    expected_zones: int
    actual_zones: int
    exact_zones: int
    expected_rejections: int
    actual_rejections: int
    exact_rejections: int
    rejections_checked: bool
    issues: tuple[BenchmarkIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return self.evaluated and not self.issues

    def to_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "label_status": self.label_status,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "expected_zones": self.expected_zones,
            "actual_zones": self.actual_zones,
            "exact_zones": self.exact_zones,
            "expected_rejections": self.expected_rejections,
            "actual_rejections": self.actual_rejections,
            "exact_rejections": self.exact_rejections,
            "rejections_checked": self.rejections_checked,
            "issues": [issue.to_mapping() for issue in self.issues],
        }


@dataclass(frozen=True)
class BenchmarkReport:
    cases: tuple[BenchmarkCaseResult, ...]

    @property
    def approved_cases(self) -> int:
        return sum(case.evaluated for case in self.cases)

    @property
    def provisional_cases(self) -> int:
        return sum(not case.evaluated for case in self.cases)

    @property
    def issues(self) -> tuple[BenchmarkIssue, ...]:
        return tuple(issue for case in self.cases for issue in case.issues)

    @property
    def status(self) -> BenchmarkStatus:
        if self.approved_cases == 0:
            return BenchmarkStatus.NO_APPROVED_CASES
        return BenchmarkStatus.FAILED if self.issues else BenchmarkStatus.PASSED

    def to_mapping(self) -> dict[str, Any]:
        approved = tuple(case for case in self.cases if case.evaluated)
        issue_counts = Counter(issue.kind for issue in self.issues)
        return {
            "status": self.status.value,
            "status_scope": "approved_cases_only",
            "approved_cases": self.approved_cases,
            "provisional_cases": self.provisional_cases,
            "passed_cases": sum(case.passed for case in approved),
            "expected_zones": sum(case.expected_zones for case in approved),
            "actual_zones": sum(case.actual_zones for case in approved),
            "exact_zones": sum(case.exact_zones for case in approved),
            "expected_rejections": sum(
                case.expected_rejections for case in approved if case.rejections_checked
            ),
            "actual_rejections": sum(
                case.actual_rejections for case in approved if case.rejections_checked
            ),
            "exact_rejections": sum(
                case.exact_rejections for case in approved if case.rejections_checked
            ),
            "issue_count": len(self.issues),
            "issues_by_kind": dict(sorted(issue_counts.items())),
            "cases": [case.to_mapping() for case in self.cases],
        }


def load_benchmark_cases(path: Path) -> list[dict[str, Any]]:
    return list(read_jsonl(path))


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _parse_time(value: Any) -> datetime | None:
    if _blank(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _decimal(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _validate_approved(case: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    bars = case.get("bars")
    rules = case.get("rules")
    expected_zones = case.get("expected_zones", [])
    expected_rejections = case.get("expected_rejections", [])
    if not isinstance(bars, list) or not bars:
        errors.append("approved case requires bars")
        bars = []
    if not isinstance(rules, list) or not rules:
        errors.append("approved case requires rule IDs")
    if _blank(case.get("symbol")):
        errors.append("approved case requires symbol")
    if _blank(case.get("feed")):
        errors.append("approved case requires feed")
    if not isinstance(expected_zones, list):
        errors.append("expected_zones must be a list")
        expected_zones = []
    if not isinstance(expected_rejections, list):
        errors.append("expected_rejections must be a list")
        expected_rejections = []
    if not expected_zones and not expected_rejections:
        errors.append("approved case requires an expected zone or rejection")

    bar_times: list[datetime] = []
    bar_time_text: set[str] = set()
    for index, bar in enumerate(bars):
        if not isinstance(bar, Mapping):
            errors.append(f"bar {index} must be an object")
            continue
        parsed_time = _parse_time(bar.get("time"))
        if parsed_time is None:
            errors.append(f"bar {index} has invalid time")
        else:
            bar_times.append(parsed_time)
            bar_time_text.add(str(bar.get("time")))
        prices = {name: _decimal(bar.get(name)) for name in ("open", "high", "low", "close")}
        if any(value is None for value in prices.values()):
            errors.append(f"bar {index} has invalid OHLC")
        elif not (
            prices["low"] <= prices["open"] <= prices["high"]
            and prices["low"] <= prices["close"] <= prices["high"]
        ):
            errors.append(f"bar {index} has inconsistent OHLC")

    if any(current <= previous for previous, current in zip(bar_times, bar_times[1:])):
        errors.append("bar times must be strictly increasing")
    elif any(
        current - previous != timedelta(minutes=5)
        for previous, current in zip(bar_times, bar_times[1:])
    ):
        errors.append("approved bars must be contiguous 5-minute intervals")

    zone_keys: set[tuple[str, str, str]] = set()
    for index, zone in enumerate(expected_zones):
        if not isinstance(zone, Mapping):
            errors.append(f"expected zone {index} must be an object")
            continue
        for field, allowed in (
            ("direction", {item.value for item in Direction}),
            ("formation", {item.value for item in Formation}),
            ("geometry", {item.value for item in Geometry}),
        ):
            if zone.get(field) not in allowed:
                errors.append(f"expected zone {index} has invalid {field}")
        top = _decimal(zone.get("top"))
        bottom = _decimal(zone.get("bottom"))
        if top is None or bottom is None:
            errors.append(f"expected zone {index} has invalid bounds")
        elif top <= bottom:
            errors.append(f"expected zone {index} top must be greater than bottom")
        for field in ("origin_time", "confirmation_time"):
            if str(zone.get(field)) not in bar_time_text:
                errors.append(f"expected zone {index} {field} is absent from bars")
        state = zone.get("state")
        if state is not None and state not in {item.value for item in ZoneState}:
            errors.append(f"expected zone {index} has invalid state")
        state_time = zone.get("state_time")
        if state_time is not None and str(state_time) not in bar_time_text:
            errors.append(f"expected zone {index} state_time is absent from bars")
        key = (
            str(zone.get("direction")),
            str(zone.get("origin_time")),
            str(zone.get("confirmation_time")),
        )
        if key in zone_keys:
            errors.append(f"expected zone {index} duplicates zone identity")
        zone_keys.add(key)

    rejection_keys: set[tuple[str, str, str]] = set()
    for index, rejection in enumerate(expected_rejections):
        if not isinstance(rejection, Mapping):
            errors.append(f"expected rejection {index} must be an object")
            continue
        if rejection.get("direction") not in {item.value for item in Direction}:
            errors.append(f"expected rejection {index} has invalid direction")
        if _blank(rejection.get("reason")):
            errors.append(f"expected rejection {index} requires reason")
        for field in ("origin_time", "rejection_time"):
            if str(rejection.get(field)) not in bar_time_text:
                errors.append(f"expected rejection {index} {field} is absent from bars")
        key = (
            str(rejection.get("direction")),
            str(rejection.get("origin_time")),
            str(rejection.get("rejection_time")),
        )
        if key in rejection_keys:
            errors.append(f"expected rejection {index} duplicates rejection identity")
        rejection_keys.add(key)
    if not isinstance(case.get("assert_no_other_rejections", False), bool):
        errors.append("assert_no_other_rejections must be boolean")
    return errors


def validate_benchmark_case(case: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if _blank(case.get("case_id")):
        errors.append("case_id is required")
    if case.get("timeframe") != "5m":
        errors.append("case timeframe must be 5m")

    label_status = case.get("label_status")
    if label_status == "APPROVED":
        errors.extend(_validate_approved(case))
    elif label_status == "PROVISIONAL":
        if not isinstance(case.get("rules"), list) or not case.get("rules"):
            errors.append("provisional case requires rule IDs")
        if _blank(case.get("evidence_note")):
            errors.append("provisional case requires evidence_note")
        if _blank(case.get("expected_behavior")):
            errors.append("provisional case requires expected_behavior")
    else:
        errors.append("label_status must be APPROVED or PROVISIONAL")
    return errors


def _zone_identity(zone: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(zone.get("direction")),
        str(zone.get("origin_time")),
        str(zone.get("confirmation_time")),
    )


def _rejection_identity(rejection: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(rejection.get("direction")),
        str(rejection.get("origin_time")),
        str(rejection.get("rejection_time")),
    )


def _identity_text(identity: tuple[str, ...]) -> str:
    return "|".join(identity)


def _value_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _compare_zone(
    case_id: str,
    entity_key: str,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    price_tolerance: Decimal,
) -> list[BenchmarkIssue]:
    issues: list[BenchmarkIssue] = []
    for field in ("formation", "geometry", "state", "state_time", "reason"):
        if field not in expected:
            continue
        if expected.get(field) != actual.get(field):
            issues.append(
                BenchmarkIssue(
                    case_id=case_id,
                    kind="ZONE_FIELD_MISMATCH",
                    entity_key=entity_key,
                    field=field,
                    expected=_value_text(expected.get(field)),
                    actual=_value_text(actual.get(field)),
                )
            )
    for field in ("top", "bottom"):
        expected_price = _decimal(expected.get(field))
        actual_price = _decimal(actual.get(field))
        if expected_price is None or actual_price is None:
            continue
        if abs(expected_price - actual_price) > price_tolerance:
            issues.append(
                BenchmarkIssue(
                    case_id=case_id,
                    kind="ZONE_FIELD_MISMATCH",
                    entity_key=entity_key,
                    field=field,
                    expected=_value_text(expected_price),
                    actual=_value_text(actual_price),
                )
            )
    return issues


def _compare_rejection(
    case_id: str,
    entity_key: str,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> list[BenchmarkIssue]:
    if expected.get("reason") == actual.get("reason"):
        return []
    return [
        BenchmarkIssue(
            case_id=case_id,
            kind="REJECTION_FIELD_MISMATCH",
            entity_key=entity_key,
            field="reason",
            expected=_value_text(expected.get("reason")),
            actual=_value_text(actual.get("reason")),
        )
    ]


def evaluate_benchmark_case(
    case: Mapping[str, Any],
    *,
    price_tolerance: Decimal = Decimal("0"),
) -> BenchmarkCaseResult:
    if price_tolerance < 0:
        raise ValueError("price_tolerance must be non-negative")
    errors = validate_benchmark_case(case)
    case_id = str(case.get("case_id") or "<unknown>")
    if errors:
        raise ValueError(f"{case_id}: {'; '.join(errors)}")

    label_status = str(case["label_status"])
    expected_zones = case.get("expected_zones", [])
    expected_rejections = case.get("expected_rejections", [])
    if label_status == "PROVISIONAL":
        return BenchmarkCaseResult(
            case_id=case_id,
            label_status=label_status,
            evaluated=False,
            expected_zones=len(expected_zones) if isinstance(expected_zones, list) else 0,
            actual_zones=0,
            exact_zones=0,
            expected_rejections=(
                len(expected_rejections) if isinstance(expected_rejections, list) else 0
            ),
            actual_rejections=0,
            exact_rejections=0,
            rejections_checked=False,
        )

    result = detect_zones([Bar.from_mapping(bar) for bar in case["bars"]])
    actual_zones = [zone.to_mapping() for zone in result.zones]
    actual_zone_pool: defaultdict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for zone in actual_zones:
        actual_zone_pool[_zone_identity(zone)].append(zone)

    issues: list[BenchmarkIssue] = []
    exact_zones = 0
    for expected in expected_zones:
        identity = _zone_identity(expected)
        entity_key = _identity_text(identity)
        matches = actual_zone_pool.get(identity)
        if not matches:
            issues.append(
                BenchmarkIssue(case_id, "MISSING_ZONE", entity_key)
            )
            continue
        actual = matches.pop(0)
        field_issues = _compare_zone(
            case_id, entity_key, expected, actual, price_tolerance
        )
        issues.extend(field_issues)
        if not field_issues:
            exact_zones += 1
    for identity, unmatched in actual_zone_pool.items():
        for _ in unmatched:
            issues.append(
                BenchmarkIssue(
                    case_id,
                    "UNEXPECTED_ZONE",
                    _identity_text(identity),
                )
            )

    rejections_checked = bool(expected_rejections) or bool(
        case.get("assert_no_other_rejections", False)
    )
    exact_rejections = 0
    if rejections_checked:
        actual_rejection_pool: defaultdict[
            tuple[str, str, str], list[Mapping[str, Any]]
        ] = defaultdict(list)
        for rejection in result.rejections:
            mapping = rejection.to_mapping()
            actual_rejection_pool[_rejection_identity(mapping)].append(mapping)
        for expected in expected_rejections:
            identity = _rejection_identity(expected)
            entity_key = _identity_text(identity)
            matches = actual_rejection_pool.get(identity)
            if not matches:
                issues.append(
                    BenchmarkIssue(case_id, "MISSING_REJECTION", entity_key)
                )
                continue
            actual = matches.pop(0)
            field_issues = _compare_rejection(
                case_id, entity_key, expected, actual
            )
            issues.extend(field_issues)
            if not field_issues:
                exact_rejections += 1
        for identity, unmatched in actual_rejection_pool.items():
            for _ in unmatched:
                issues.append(
                    BenchmarkIssue(
                        case_id,
                        "UNEXPECTED_REJECTION",
                        _identity_text(identity),
                    )
                )

    return BenchmarkCaseResult(
        case_id=case_id,
        label_status=label_status,
        evaluated=True,
        expected_zones=len(expected_zones),
        actual_zones=len(actual_zones),
        exact_zones=exact_zones,
        expected_rejections=len(expected_rejections),
        actual_rejections=len(result.rejections),
        exact_rejections=exact_rejections,
        rejections_checked=rejections_checked,
        issues=tuple(issues),
    )


def evaluate_benchmark_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    price_tolerance: Decimal = Decimal("0"),
) -> BenchmarkReport:
    return BenchmarkReport(
        tuple(
            evaluate_benchmark_case(case, price_tolerance=price_tolerance)
            for case in cases
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare the deterministic RD 5m detector with labeled cases."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("scripts/rd_concepts_pipeline/reference/rd_5m_cases.jsonl"),
    )
    parser.add_argument("--price-tolerance", default="0")
    args = parser.parse_args(argv)
    tolerance = _decimal(args.price_tolerance)
    if tolerance is None or tolerance < 0:
        parser.error("--price-tolerance must be a non-negative finite number")

    try:
        report = evaluate_benchmark_cases(
            load_benchmark_cases(args.path), price_tolerance=tolerance
        )
    except ValueError as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report.to_mapping(), indent=2, sort_keys=True))
    if report.status is BenchmarkStatus.PASSED:
        return 0
    return 1 if report.status is BenchmarkStatus.FAILED else 2


if __name__ == "__main__":
    raise SystemExit(main())
