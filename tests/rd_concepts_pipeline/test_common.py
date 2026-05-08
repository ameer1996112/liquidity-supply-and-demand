from pathlib import Path

from scripts.rd_concepts_pipeline.common import (
    detect_session,
    extract_setup_tags,
    redact,
    safe_filename,
    write_jsonl,
    read_jsonl,
)


def test_redact_masks_token_like_values() -> None:
    text = "Authorization: aaaaaaaaaaaaaaaaaaaa.bbbbbb.cccccccccccccccccccccc and token=secret"
    assert "aaaaaaaaaaaaaaaaaaaa.bbbbbb.cccccccccccccccccccccc" not in redact(text)
    assert "secret" not in redact(text)


def test_safe_filename_removes_path_characters() -> None:
    assert safe_filename("EUR/USD setup: long.png") == "EUR_USD_setup_long.png"


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "messages.jsonl"
    rows = [{"id": "1", "content": "EURUSD long"}, {"id": "2", "content": "rule"}]
    write_jsonl(path, rows)

    assert list(read_jsonl(path)) == rows


def test_detect_session_london_from_utc_timestamp() -> None:
    assert detect_session("2026-05-08T08:30:00+00:00") == "london"


def test_extract_setup_tags_finds_core_rd_concepts() -> None:
    tags = extract_setup_tags("EURUSD sweep into OB with displacement and FVG")
    assert {"liquidity", "sweep", "order_block", "displacement", "fvg"} <= set(tags)


def test_extract_setup_tags_does_not_match_inside_words() -> None:
    tags = extract_setup_tags("Watching demand, obvious chart, and cinematic move")
    assert "ema" not in tags
    assert "order_block" not in tags
