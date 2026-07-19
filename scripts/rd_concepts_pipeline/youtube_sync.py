from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
from pathlib import Path
from typing import Any

from scripts.rd_concepts_pipeline.common import (
    atomic_write_json,
    atomic_write_jsonl,
    now_iso,
    read_jsonl,
    redact,
)
from scripts.rd_concepts_pipeline.config import PipelineSettings, get_settings
from scripts.rd_concepts_pipeline.evidence_extractor import extract_evidence_spans
from scripts.rd_concepts_pipeline.models import EvidenceClass, VideoRecord
from scripts.rd_concepts_pipeline.sources import CHANNEL_SOURCES
from scripts.rd_concepts_pipeline.youtube_inventory import sync_inventory
from scripts.rd_concepts_pipeline.youtube_transcripts import (
    TranscriptCacheResult,
    cache_transcript,
    parse_json3_transcript,
)


InventorySync = Callable[..., list[VideoRecord]]
TranscriptCache = Callable[..., TranscriptCacheResult]


def _selected_classes(include_operations: bool) -> tuple[EvidenceClass, ...]:
    selected = [EvidenceClass.RULE_SOURCE, EvidenceClass.EDGE_EVIDENCE]
    if include_operations:
        selected.append(EvidenceClass.OPERATIONS_EVIDENCE)
    return tuple(selected)


def _load_inventory(data_dir: Path) -> list[VideoRecord]:
    path = data_dir / "youtube" / "inventory.jsonl"
    records = [VideoRecord.from_mapping(row) for row in read_jsonl(path)]
    if not records:
        raise ValueError("YouTube inventory is missing or empty; run inventory first")
    return records


def _filter_records(
    records: Sequence[VideoRecord],
    source_ids: set[str],
    classes: tuple[EvidenceClass, ...],
) -> list[VideoRecord]:
    return [
        record
        for record in records
        if record.source_id in source_ids and record.evidence_class in classes
    ]


def _empty_counts() -> dict[str, int]:
    return {"total": 0, "successes": 0, "failures": 0, "skipped": 0}


def _sync_transcripts(
    records: Sequence[VideoRecord],
    data_dir: Path,
    refresh: bool,
    transcript_cache: TranscriptCache,
) -> tuple[dict[str, int], list[dict[str, str]]]:
    counts = _empty_counts()
    failures: list[dict[str, str]] = []
    for record in records:
        counts["total"] += 1
        try:
            result = transcript_cache(record, data_dir, refresh=refresh)
        except Exception as exc:
            counts["failures"] += 1
            failures.append(
                {"video_id": record.video_id, "error": redact(str(exc))}
            )
            continue
        if result.status in {"SKIPPED", "NO_TRANSCRIPT"}:
            counts["skipped"] += 1
        else:
            counts["successes"] += 1
    return counts, failures


def _sync_evidence(
    records: Sequence[VideoRecord], data_dir: Path
) -> tuple[dict[str, int], list[dict[str, str]]]:
    counts = _empty_counts()
    failures: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    transcript_dir = data_dir / "youtube" / "transcripts"
    for record in records:
        counts["total"] += 1
        path = transcript_dir / f"{record.video_id}.json3"
        if not path.exists():
            counts["skipped"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cues = parse_json3_transcript(payload)
            spans = extract_evidence_spans(record.video_id, cues)
            rows.extend(
                {"source_id": record.source_id, **span.to_mapping()} for span in spans
            )
            counts["successes"] += 1
        except Exception as exc:
            counts["failures"] += 1
            failures.append(
                {"video_id": record.video_id, "error": redact(str(exc))}
            )
    atomic_write_jsonl(data_dir / "youtube" / "evidence_candidates.jsonl", rows)
    return counts, failures


def run_sync(
    command: str,
    settings: PipelineSettings,
    *,
    source_ids: Sequence[str] | None = None,
    refresh: bool = False,
    include_operations: bool = False,
    inventory_sync: InventorySync = sync_inventory,
    transcript_cache: TranscriptCache = cache_transcript,
) -> dict[str, Any]:
    if command not in {"inventory", "transcripts", "evidence", "all"}:
        raise ValueError(f"unsupported command: {command}")
    available_sources = {source.source_id: source for source in CHANNEL_SOURCES}
    selected_ids = list(dict.fromkeys(source_ids or available_sources))
    unknown = sorted(set(selected_ids) - set(available_sources))
    if unknown:
        raise ValueError(f"unknown source IDs: {', '.join(unknown)}")
    sources = [available_sources[source_id] for source_id in selected_ids]
    classes = _selected_classes(include_operations)
    manifest: dict[str, Any] = {
        "started_at": now_iso(),
        "completed_at": None,
        "command": command,
        "selected_source_ids": selected_ids,
        "selected_classes": [item.value for item in classes],
        "stages": {},
        "failures": [],
    }
    manifest_path = settings.data_dir / "youtube" / "manifest.json"

    try:
        records: list[VideoRecord]
        if command in {"inventory", "all"}:
            records = inventory_sync(sources, settings.data_dir)
            manifest["stages"]["inventory"] = {
                "total": len(sources),
                "successes": len(sources),
                "failures": 0,
                "skipped": 0,
                "videos": len(records),
            }
        else:
            records = _load_inventory(settings.data_dir)

        selected_records = _filter_records(records, set(selected_ids), classes)
        if command in {"transcripts", "all"}:
            counts, failures = _sync_transcripts(
                selected_records,
                settings.data_dir,
                refresh,
                transcript_cache,
            )
            manifest["stages"]["transcripts"] = counts
            manifest["failures"].extend(failures)
        if command in {"evidence", "all"}:
            counts, failures = _sync_evidence(selected_records, settings.data_dir)
            manifest["stages"]["evidence"] = counts
            manifest["failures"].extend(failures)
    except Exception as exc:
        if command in {"inventory", "all"} and "inventory" not in manifest["stages"]:
            manifest["stages"]["inventory"] = {
                "total": len(sources),
                "successes": 0,
                "failures": len(sources),
                "skipped": 0,
                "videos": 0,
            }
        manifest["failures"].append({"stage": command, "error": redact(str(exc))})
        manifest["completed_at"] = now_iso()
        atomic_write_json(manifest_path, manifest)
        raise

    manifest["completed_at"] = now_iso()
    atomic_write_json(manifest_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize RD YouTube evidence")
    parser.add_argument("command", choices=("inventory", "transcripts", "evidence", "all"))
    parser.add_argument("--source", action="append", dest="source_ids")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--include-operations", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = run_sync(
        args.command,
        get_settings(),
        source_ids=args.source_ids,
        refresh=args.refresh,
        include_operations=args.include_operations,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
