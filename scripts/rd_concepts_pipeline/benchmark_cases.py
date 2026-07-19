from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from scripts.rd_concepts_pipeline.common import read_jsonl


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
    expected_zones = case.get("expected_zones") or []
    expected_rejections = case.get("expected_rejections") or []
    if not isinstance(bars, list) or not bars:
        errors.append("approved case requires bars")
        bars = []
    if not isinstance(rules, list) or not rules:
        errors.append("approved case requires rule IDs")
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

    for index, zone in enumerate(expected_zones):
        if not isinstance(zone, Mapping):
            errors.append(f"expected zone {index} must be an object")
            continue
        top = _decimal(zone.get("top"))
        bottom = _decimal(zone.get("bottom"))
        if top is None or bottom is None:
            errors.append(f"expected zone {index} has invalid bounds")
        elif top <= bottom:
            errors.append(f"expected zone {index} top must be greater than bottom")
        for field in ("origin_time", "confirmation_time"):
            if str(zone.get(field)) not in bar_time_text:
                errors.append(f"expected zone {index} {field} is absent from bars")

    for index, rejection in enumerate(expected_rejections):
        if not isinstance(rejection, Mapping):
            errors.append(f"expected rejection {index} must be an object")
            continue
        for field in ("origin_time", "confirmation_time", "rejection_time"):
            value = rejection.get(field)
            if value is not None and str(value) not in bar_time_text:
                errors.append(f"expected rejection {index} {field} is absent from bars")
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
