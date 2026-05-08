from pathlib import Path

from scripts.rd_concepts_pipeline.parser import (
    IMAGE_INDEX_COLUMNS,
    SIGNAL_COLUMNS,
    parse_message,
    parse_raw_files,
    write_outputs,
)


def test_parse_pattern_a_long_signal() -> None:
    row = {
        "id": "1",
        "channel": "5m-signals",
        "timestamp": "2026-05-08T08:30:00+00:00",
        "content": "EURUSD LONG entry 1.0750 SL: 1.0725 TP: 1.0825 liquidity sweep into FVG 5m",
        "images": ["chart.png"],
    }

    parsed = parse_message(row)

    assert parsed["pair"] == "EURUSD"
    assert parsed["direction"] == "long"
    assert parsed["entry"] == 1.075
    assert parsed["stop_loss"] == 1.0725
    assert parsed["take_profit"] == 1.0825
    assert parsed["rr_ratio"] == 3.0
    assert parsed["has_chart"] is True
    assert {"liquidity", "sweep", "fvg"} <= set(parsed["setup_tags"])


def test_parse_pattern_b_short_signal() -> None:
    row = {
        "id": "2",
        "channel": "30m-signals",
        "timestamp": "2026-05-08T13:00:00+00:00",
        "content": "GBPUSD SELL @ 1.2600, Stop 1.2640, Target 1.2480 after BOS and order block",
        "images": [],
    }

    parsed = parse_message(row)

    assert parsed["pair"] == "GBPUSD"
    assert parsed["direction"] == "short"
    assert parsed["rr_ratio"] == 3.0
    assert {"bos", "order_block"} <= set(parsed["setup_tags"])


def test_parse_loose_setup_keeps_ambiguous_record() -> None:
    row = {
        "id": "3",
        "channel": "main-pairs",
        "timestamp": "2026-05-08T20:00:00+00:00",
        "content": "Watching XAUUSD bullish if it sweeps lows and reclaims 5m structure",
        "images": ["chart.png"],
    }

    parsed = parse_message(row)

    assert parsed["pair"] == "XAUUSD"
    assert parsed["direction"] == "long"
    assert "missing_levels" in parsed["quality_flags"]


def test_parse_raw_files_returns_signals_and_image_index() -> None:
    fixture = Path("tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl")
    signals, images = parse_raw_files([fixture])

    assert len(signals) == 3
    assert len(images) == 2


def test_parse_raw_files_returns_image_index_shape() -> None:
    fixture = Path("tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl")
    _, images = parse_raw_files([fixture])

    assert images == [
        {
            "message_id": "1",
            "timestamp": "2026-05-08T08:30:00+00:00",
            "channel": "5m-signals",
            "image_path": "data/rd_concepts/raw/5m-signals/images/1.png",
            "pair": "EURUSD",
            "direction": "long",
            "setup_tags": ["fvg", "liquidity", "sweep"],
        },
        {
            "message_id": "3",
            "timestamp": "2026-05-08T20:00:00+00:00",
            "channel": "main-pairs",
            "image_path": "data/rd_concepts/raw/main-pairs/images/3.png",
            "pair": "XAUUSD",
            "direction": "long",
            "setup_tags": ["liquidity", "structure", "sweep"],
        },
    ]


def test_write_outputs_creates_empty_csvs_with_headers(tmp_path: Path) -> None:
    write_outputs([], [], tmp_path)

    signals_header = (
        (tmp_path / "signals.csv").read_text(encoding="utf-8").splitlines()[0]
    )
    image_header = (
        tmp_path / "image_index.csv"
    ).read_text(encoding="utf-8").splitlines()[0]

    assert signals_header == ",".join(SIGNAL_COLUMNS)
    assert image_header == ",".join(IMAGE_INDEX_COLUMNS)
