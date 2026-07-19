from pathlib import Path
import json

import pytest

from scripts.rd_concepts_pipeline.models import ChannelSource, EvidenceClass
from scripts.rd_concepts_pipeline.youtube_inventory import (
    inventory_command,
    parse_playlist_json,
    sync_inventory,
)


FIXTURE = Path("tests/rd_concepts_pipeline/fixtures/youtube_playlist.json")
SOURCE = ChannelSource(
    "rd_forex", "RD Forex", "https://www.youtube.com/@RD_Forex", 2, "canonical"
)


def test_parse_playlist_normalizes_records() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = parse_playlist_json(payload, SOURCE)

    assert len(records) == 2
    assert records[0].evidence_class is EvidenceClass.RULE_SOURCE
    assert records[0].published_at == "2026-01-02"
    assert records[1].url == "https://www.youtube.com/watch?v=mindset1"


def test_inventory_command_is_metadata_only() -> None:
    command = inventory_command(SOURCE)
    assert command == [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        SOURCE.videos_url,
    ]


def test_sync_inventory_sorts_and_writes_records(tmp_path: Path) -> None:
    payload = FIXTURE.read_text(encoding="utf-8")
    sources = [
        ChannelSource("z", "Z", "https://www.youtube.com/@z", 3, "test"),
        ChannelSource("a", "A", "https://www.youtube.com/@a", 2, "test"),
    ]
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> str:
        calls.append(argv)
        return payload

    records = sync_inventory(sources, tmp_path, runner)

    assert len(calls) == 2
    assert [(record.source_id, record.video_id) for record in records] == [
        ("a", "course1"),
        ("a", "mindset1"),
        ("z", "course1"),
        ("z", "mindset1"),
    ]
    assert (tmp_path / "youtube" / "inventory.jsonl").exists()


def test_sync_inventory_fails_closed_on_empty_channel(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty inventory response"):
        sync_inventory([SOURCE], tmp_path, lambda _argv: "")
