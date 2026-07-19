from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import Any

from scripts.rd_concepts_pipeline.common import atomic_write_jsonl
from scripts.rd_concepts_pipeline.models import ChannelSource, VideoRecord
from scripts.rd_concepts_pipeline.sources import classify_video_title


CommandRunner = Callable[[list[str]], str]


def run_command(argv: list[str]) -> str:
    try:
        completed = subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"{argv[0]} exited {exc.returncode}: {detail or 'no diagnostic output'}"
        ) from exc
    return completed.stdout


def inventory_command(source: ChannelSource) -> list[str]:
    return ["yt-dlp", "--flat-playlist", "--dump-single-json", source.videos_url]


def _published_at(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value)
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _video_url(entry: Mapping[str, Any], video_id: str) -> str:
    value = str(entry.get("webpage_url") or entry.get("url") or "")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://www.youtube.com/watch?v={video_id}"


def parse_playlist_json(
    payload: Mapping[str, Any], source: ChannelSource
) -> list[VideoRecord]:
    records: list[VideoRecord] = []
    for entry in payload.get("entries") or ():
        if not isinstance(entry, Mapping):
            continue
        video_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        if not video_id or not title:
            continue
        records.append(
            VideoRecord(
                source_id=source.source_id,
                video_id=video_id,
                title=title,
                url=_video_url(entry, video_id),
                evidence_class=classify_video_title(title),
                published_at=_published_at(entry.get("upload_date")),
            )
        )
    return records


def sync_inventory(
    sources: Sequence[ChannelSource],
    data_dir: Path,
    runner: CommandRunner = run_command,
) -> list[VideoRecord]:
    records: list[VideoRecord] = []
    for source in sources:
        output = runner(inventory_command(source))
        if not output.strip():
            raise ValueError(f"empty inventory response for {source.source_id}")
        payload = json.loads(output)
        channel_records = parse_playlist_json(payload, source)
        if not channel_records:
            raise ValueError(f"inventory contains no videos for {source.source_id}")
        records.extend(channel_records)

    records.sort(key=lambda record: (record.source_id, record.video_id))
    output_path = data_dir / "youtube" / "inventory.jsonl"
    atomic_write_jsonl(output_path, (record.to_mapping() for record in records))
    return records
