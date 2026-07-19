from copy import deepcopy
from pathlib import Path
import json

from scripts.rd_concepts_pipeline.benchmark_cases import validate_benchmark_case


FIXTURE = Path("tests/rd_concepts_pipeline/fixtures/rd_5m_case.json")


def approved_case() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_approved_case_is_valid() -> None:
    assert validate_benchmark_case(approved_case()) == []


def test_rejects_non_5m_and_non_monotonic_bars() -> None:
    case = approved_case()
    case["timeframe"] = "15m"
    case["bars"] = list(reversed(case["bars"]))
    errors = validate_benchmark_case(case)
    assert "case timeframe must be 5m" in errors
    assert "bar times must be strictly increasing" in errors


def test_rejects_inverted_zone_and_missing_expected_time() -> None:
    case = approved_case()
    case["expected_zones"][0]["top"] = case["expected_zones"][0]["bottom"]
    case["expected_zones"][0]["confirmation_time"] = "2026-07-19T09:00:00Z"
    errors = validate_benchmark_case(case)
    assert "expected zone 0 top must be greater than bottom" in errors
    assert "expected zone 0 confirmation_time is absent from bars" in errors


def test_approved_case_requires_rules() -> None:
    case = approved_case()
    case["rules"] = []
    assert "approved case requires rule IDs" in validate_benchmark_case(case)


def test_non_finite_price_is_reported_instead_of_raising() -> None:
    case = approved_case()
    case["bars"][0]["low"] = "NaN"
    assert "bar 0 has invalid OHLC" in validate_benchmark_case(case)


def test_provisional_case_can_omit_prices_with_evidence_note() -> None:
    case = {
        "case_id": "USDJPY-5M-PROVISIONAL-001",
        "timeframe": "5m",
        "label_status": "PROVISIONAL",
        "rules": ["RD5M-ZONE-FORMATION-WICK-DEMAND"],
        "evidence_note": "User screenshot dated 2026-07-19.",
        "expected_behavior": "Bullish formation wick extends the demand distal bound.",
    }
    assert validate_benchmark_case(case) == []

    invalid = deepcopy(case)
    invalid["evidence_note"] = ""
    assert "provisional case requires evidence_note" in validate_benchmark_case(invalid)
