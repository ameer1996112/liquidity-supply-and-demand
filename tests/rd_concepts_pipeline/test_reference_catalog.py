from pathlib import Path
import json

from scripts.rd_concepts_pipeline.benchmark_cases import (
    BenchmarkStatus,
    evaluate_benchmark_cases,
    load_benchmark_cases,
    validate_benchmark_case,
)
from scripts.rd_concepts_pipeline.rule_catalog import (
    load_rule_catalog,
    rule_coverage,
    validate_rule_catalog,
)


REFERENCE = Path("scripts/rd_concepts_pipeline/reference")


def test_source_snapshot_has_immutable_six_channel_baseline() -> None:
    snapshot = json.loads(
        (REFERENCE / "source_snapshot.json").read_text(encoding="utf-8")
    )
    counts = {
        source["source_id"]: source["video_count"] for source in snapshot["sources"]
    }
    assert counts == {
        "rd_forex": 55,
        "arger_fx": 33,
        "mangoe": 123,
        "rt_futures": 21,
        "charney_fx": 79,
        "trirex": 81,
    }
    assert snapshot["total_videos"] == 392
    assert snapshot["immutable"] is True


def test_initial_rule_catalog_is_valid_and_contains_zone_contracts() -> None:
    records = load_rule_catalog(REFERENCE / "rd_5m_rules.jsonl")
    rule_ids = [record.rule_id for record in records]
    assert len(rule_ids) == len(set(rule_ids))
    assert {
        "RD5M-ZONE-ORIGIN-DEMAND",
        "RD5M-ZONE-ORIGIN-SUPPLY",
        "RD5M-ZONE-STANDARD-BOUNDS",
        "RD5M-ZONE-ACCURACY-DEMAND",
        "RD5M-ZONE-ACCURACY-SUPPLY",
        "RD5M-ZONE-UNTAPPED",
        "RD5M-ZONE-DEPARTURE-WICK-EXCEPTION",
        "RD5M-ZONE-FORMATION-WICK-DEMAND",
    } <= set(rule_ids)
    assert validate_rule_catalog(records) == []


def test_first_manual_case_has_exact_ohlc_and_positive_release_coverage() -> None:
    records = load_rule_catalog(REFERENCE / "rd_5m_rules.jsonl")
    cases = load_benchmark_cases(REFERENCE / "rd_5m_cases.jsonl")

    assert len(cases) == 1
    assert cases[0]["case_id"] == "USDJPY-5M-FORMATION-WICK-001"
    assert cases[0]["label_status"] == "APPROVED"
    assert len(cases[0]["bars"]) == 3
    assert cases[0]["expected_zones"][0]["bottom"] == "162.263"
    assert len(cases[0]["source_export_sha256"]) == 64
    assert "RD5M-ZONE-FORMATION-WICK-DEMAND" in cases[0]["rules"]
    assert validate_benchmark_case(cases[0]) == []
    assert evaluate_benchmark_cases(cases).status is BenchmarkStatus.PASSED
    coverage = rule_coverage(records, cases)
    assert "RD5M-ZONE-FORMATION-WICK-DEMAND" not in coverage["missing_positive"]
    assert "RD5M-ZONE-FORMATION-WICK-DEMAND" in coverage["missing_negative"]


def test_readme_documents_youtube_safety_and_commands() -> None:
    text = Path("scripts/rd_concepts_pipeline/README.md").read_text(encoding="utf-8")
    assert "youtube_sync.py inventory" in text
    assert "youtube_sync.py transcripts" in text
    assert "Full transcripts remain under ignored `data/rd_concepts`" in text
    assert "does not execute trades" in text
