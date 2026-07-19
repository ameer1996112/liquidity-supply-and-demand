from pathlib import Path

import pytest

from scripts.rd_concepts_pipeline.common import atomic_write_jsonl
from scripts.rd_concepts_pipeline.config import PipelineSettings
from scripts.rd_concepts_pipeline.models import EvidenceClass, VideoRecord
from scripts.rd_concepts_pipeline.youtube_sync import run_sync
from scripts.rd_concepts_pipeline.youtube_transcripts import TranscriptCacheResult


def settings(tmp_path: Path) -> PipelineSettings:
    return PipelineSettings("", "", data_dir=tmp_path)


def records() -> list[VideoRecord]:
    return [
        VideoRecord("rd_forex", "rule", "Full course", "rule-url", EvidenceClass.RULE_SOURCE),
        VideoRecord("rd_forex", "edge", "Trade missed", "edge-url", EvidenceClass.EDGE_EVIDENCE),
        VideoRecord("trirex", "ops", "Automated bot", "ops-url", EvidenceClass.OPERATIONS_EVIDENCE),
        VideoRecord("mangoe", "mindset", "Mindset", "other-url", EvidenceClass.NON_RULE),
    ]


def write_inventory(tmp_path: Path) -> None:
    atomic_write_jsonl(
        tmp_path / "youtube" / "inventory.jsonl",
        (record.to_mapping() for record in records()),
    )


def test_inventory_calls_all_six_sources(tmp_path: Path) -> None:
    captured: list[str] = []

    def inventory_sync(sources, _data_dir):
        captured.extend(source.source_id for source in sources)
        return records()

    manifest = run_sync("inventory", settings(tmp_path), inventory_sync=inventory_sync)

    assert captured == [
        "rd_forex",
        "arger_fx",
        "mangoe",
        "rt_futures",
        "charney_fx",
        "trirex",
    ]
    assert manifest["stages"]["inventory"]["total"] == 6


def test_transcripts_default_to_rules_and_edges_and_continue_on_failure(tmp_path: Path) -> None:
    write_inventory(tmp_path)
    called: list[str] = []

    def transcript_cache(record, _data_dir, refresh=False):
        called.append(record.video_id)
        if record.video_id == "edge":
            raise RuntimeError("token=secret failure")
        return TranscriptCacheResult(record.video_id, "CACHED", Path("cache"))

    manifest = run_sync(
        "transcripts", settings(tmp_path), transcript_cache=transcript_cache
    )

    assert called == ["rule", "edge"]
    counts = manifest["stages"]["transcripts"]
    assert counts["total"] == counts["successes"] + counts["failures"] + counts["skipped"]
    assert counts == {"total": 2, "successes": 1, "failures": 1, "skipped": 0}
    assert "secret" not in manifest["failures"][0]["error"]


def test_transcripts_can_include_operations_and_report_skips(tmp_path: Path) -> None:
    write_inventory(tmp_path)
    called: list[str] = []

    def transcript_cache(record, _data_dir, refresh=False):
        called.append(record.video_id)
        return TranscriptCacheResult(record.video_id, "SKIPPED", Path("cache"))

    manifest = run_sync(
        "transcripts",
        settings(tmp_path),
        include_operations=True,
        transcript_cache=transcript_cache,
    )
    assert called == ["rule", "edge", "ops"]
    assert manifest["stages"]["transcripts"]["skipped"] == 3


def test_inventory_failure_is_fail_closed_and_manifested(tmp_path: Path) -> None:
    def inventory_sync(_sources, _data_dir):
        raise RuntimeError("channel unavailable")

    with pytest.raises(RuntimeError, match="channel unavailable"):
        run_sync("inventory", settings(tmp_path), inventory_sync=inventory_sync)

    manifest = (tmp_path / "youtube" / "manifest.json").read_text(encoding="utf-8")
    assert "channel unavailable" in manifest
    assert '"total": 6' in manifest
    assert '"failures": 6' in manifest


def test_duplicate_source_flags_are_deduplicated(tmp_path: Path) -> None:
    captured: list[str] = []

    def inventory_sync(sources, _data_dir):
        captured.extend(source.source_id for source in sources)
        return records()

    run_sync(
        "inventory",
        settings(tmp_path),
        source_ids=["rd_forex", "rd_forex"],
        inventory_sync=inventory_sync,
    )
    assert captured == ["rd_forex"]
