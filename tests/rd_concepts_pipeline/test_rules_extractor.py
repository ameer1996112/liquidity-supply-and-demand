from pathlib import Path

from scripts.rd_concepts_pipeline.rules_extractor import extract_rule_record, extract_rules_from_files


def test_extract_rule_record_matches_must_and_liquidity() -> None:
    row = {
        "id": "10",
        "channel": "webinars-and-extras",
        "timestamp": "2026-05-08T09:00:00+00:00",
        "author": {"username": "mentor"},
        "content": "Rule: price must sweep liquidity before entry into order block.",
        "images": ["chart.png"],
        "message_url": "https://discord.com/channels/@me/10/10",
    }

    record = extract_rule_record(row)

    assert record is not None
    assert "must" in record["keyword_hits"]
    assert {"liquidity", "sweep", "order_block"} <= set(record["concept_tags"])


def test_extract_rules_from_files_counts_concepts() -> None:
    rules, concepts = extract_rules_from_files([Path("tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl")])

    assert isinstance(rules, list)
    assert "liquidity" in concepts
