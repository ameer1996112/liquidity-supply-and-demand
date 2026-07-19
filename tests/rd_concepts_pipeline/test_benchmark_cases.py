from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json

import pytest

from scripts.rd_concepts_pipeline.benchmark_cases import (
    BenchmarkStatus,
    evaluate_benchmark_case,
    evaluate_benchmark_cases,
    main,
    validate_benchmark_case,
)


FIXTURE = Path("tests/rd_concepts_pipeline/fixtures/rd_5m_case.json")


def approved_case() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def rejection_case() -> dict:
    return {
        "case_id": "SYNTHETIC-5M-INTERRUPTION-001",
        "symbol": "TEST",
        "feed": "SYNTHETIC",
        "timeframe": "5m",
        "label_status": "APPROVED",
        "rules": ["RD5M-ZONE-OPPOSITE-INTERRUPTION"],
        "bars": [
            {
                "time": "2026-07-19T08:00:00Z",
                "open": 10.2,
                "high": 10.3,
                "low": 9.8,
                "close": 9.9,
            },
            {
                "time": "2026-07-19T08:05:00Z",
                "open": 9.9,
                "high": 10.0,
                "low": 9.5,
                "close": 9.6,
            },
            {
                "time": "2026-07-19T08:10:00Z",
                "open": 9.6,
                "high": 9.9,
                "low": 9.4,
                "close": 9.8,
            },
            {
                "time": "2026-07-19T08:15:00Z",
                "open": 9.8,
                "high": 9.9,
                "low": 9.3,
                "close": 9.5,
            },
        ],
        "expected_zones": [],
        "expected_rejections": [
            {
                "direction": "DEMAND",
                "origin_time": "2026-07-19T08:05:00Z",
                "rejection_time": "2026-07-19T08:15:00Z",
                "reason": "REJECT_FORMATION_INTERRUPTED",
            }
        ],
    }


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


def test_approved_case_requires_feed_symbol_and_contiguous_bars() -> None:
    case = approved_case()
    case["feed"] = ""
    case["symbol"] = ""
    case["bars"][1]["time"] = "2026-07-19T08:01:00Z"

    errors = validate_benchmark_case(case)

    assert "approved case requires feed" in errors
    assert "approved case requires symbol" in errors
    assert "approved bars must be contiguous 5-minute intervals" in errors


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


def test_exact_detector_output_passes_approved_case() -> None:
    result = evaluate_benchmark_case(approved_case())

    assert result.passed
    assert result.exact_zones == 1
    assert result.actual_zones == 1
    assert not result.rejections_checked


def test_reports_missing_zone_when_confirmation_never_happens() -> None:
    case = approved_case()
    case["bars"][-1]["close"] = 162.290

    result = evaluate_benchmark_case(case)

    assert not result.passed
    assert [issue.kind for issue in result.issues] == ["MISSING_ZONE"]


def test_reports_unexpected_zone_independent_of_zone_order() -> None:
    case = approved_case()
    case["bars"].append(
        {
            "time": "2026-07-19T08:10:00Z",
            "open": 162.305,
            "high": 162.312,
            "low": 162.250,
            "close": 162.255,
        }
    )

    result = evaluate_benchmark_case(case)

    assert result.exact_zones == 1
    assert result.actual_zones == 2
    assert [issue.kind for issue in result.issues] == ["UNEXPECTED_ZONE"]


def test_reports_classification_and_bound_mismatches() -> None:
    case = approved_case()
    expected = case["expected_zones"][0]
    expected["geometry"] = "ACCURACY"
    expected["top"] = 162.297

    result = evaluate_benchmark_case(case)

    assert {(issue.kind, issue.field) for issue in result.issues} == {
        ("ZONE_FIELD_MISMATCH", "geometry"),
        ("ZONE_FIELD_MISMATCH", "top"),
    }


def test_price_tolerance_is_explicit() -> None:
    case = approved_case()
    case["expected_zones"][0]["top"] = 162.2965

    strict = evaluate_benchmark_case(case)
    tolerant = evaluate_benchmark_case(case, price_tolerance=Decimal("0.001"))

    assert not strict.passed
    assert tolerant.passed


def test_optional_lifecycle_fields_are_compared() -> None:
    case = approved_case()
    case["bars"].append(
        {
            "time": "2026-07-19T08:10:00Z",
            "open": 162.305,
            "high": 162.306,
            "low": 162.280,
            "close": 162.285,
        }
    )
    case["expected_zones"][0].update(
        {
            "state": "TAPPED",
            "state_time": "2026-07-19T08:10:00Z",
            "reason": "TAP_POST_CONFIRM_OVERLAP",
        }
    )

    assert evaluate_benchmark_case(case).passed


def test_rejection_labels_are_matched_when_requested() -> None:
    result = evaluate_benchmark_case(rejection_case())

    assert result.passed
    assert result.rejections_checked
    assert result.exact_rejections == 1


def test_report_cannot_pass_without_approved_cases() -> None:
    provisional = {
        "case_id": "USDJPY-5M-PROVISIONAL-001",
        "timeframe": "5m",
        "label_status": "PROVISIONAL",
        "rules": ["RD5M-ZONE-FORMATION-WICK-DEMAND"],
        "evidence_note": "User screenshot dated 2026-07-19.",
        "expected_behavior": "Bullish formation wick extends the demand distal bound.",
    }

    report = evaluate_benchmark_cases([provisional])

    assert report.status is BenchmarkStatus.NO_APPROVED_CASES
    assert report.to_mapping()["status_scope"] == "approved_cases_only"


def test_report_fails_when_any_approved_case_has_an_issue() -> None:
    passing = approved_case()
    failing = approved_case()
    failing["case_id"] = "USDJPY-5M-FORMATION-WICK-002"
    failing["expected_zones"][0]["bottom"] = 162.265

    report = evaluate_benchmark_cases([passing, failing])

    assert report.status is BenchmarkStatus.FAILED
    assert report.to_mapping()["passed_cases"] == 1
    assert report.to_mapping()["issues_by_kind"] == {"ZONE_FIELD_MISMATCH": 1}


def test_cli_returns_no_approved_status_for_provisional_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provisional = {
        "case_id": "USDJPY-5M-PROVISIONAL-CLI-001",
        "timeframe": "5m",
        "label_status": "PROVISIONAL",
        "rules": ["RD5M-ZONE-FORMATION-WICK-DEMAND"],
        "evidence_note": "Screenshot awaiting exact OHLC export.",
        "expected_behavior": "Formation wick extends the distal bound.",
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(provisional) + "\n", encoding="utf-8")

    exit_code = main([str(path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output["status"] == "NO_APPROVED_CASES"
