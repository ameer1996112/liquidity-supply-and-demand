from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Any

from scripts.rd_concepts_pipeline.common import atomic_write_json, ensure_dir
from scripts.rd_concepts_pipeline.models import TranscriptCue, VideoRecord


CommandRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class TranscriptCacheResult:
    video_id: str
    status: str
    path: Path | None = None


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


def transcript_command(record: VideoRecord, output_dir: Path) -> list[str]:
    output_template = output_dir / f"{record.video_id}.%(ext)s"
    return [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "en.*,en",
        "--sub-format",
        "json3",
        "--output",
        str(output_template),
        record.url,
    ]


def parse_json3_transcript(payload: Mapping[str, Any]) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    for event in payload.get("events") or []:
        text = "".join(
            str(segment.get("utf8", "")) for segment in event.get("segs") or []
        ).strip()
        if not text:
            continue
        cues.append(
            TranscriptCue(
                start_ms=int(event.get("tStartMs", 0)),
                duration_ms=max(0, int(event.get("dDurationMs", 0))),
                text=text,
            )
        )
    return cues


def cache_transcript(
    record: VideoRecord,
    data_dir: Path,
    runner: CommandRunner = run_command,
    refresh: bool = False,
) -> TranscriptCacheResult:
    transcript_dir = ensure_dir(data_dir / "youtube" / "transcripts")
    cache_path = transcript_dir / f"{record.video_id}.json3"
    if cache_path.exists() and not refresh:
        return TranscriptCacheResult(record.video_id, "SKIPPED", cache_path)

    with TemporaryDirectory(prefix=f".{record.video_id}.", dir=transcript_dir) as temporary:
        temporary_dir = Path(temporary)
        runner(transcript_command(record, temporary_dir))
        candidates = sorted(
            temporary_dir.glob(f"{record.video_id}*.json3"),
            key=lambda path: (".en." not in path.name, path.name),
        )
        if not candidates:
            return TranscriptCacheResult(record.video_id, "NO_TRANSCRIPT")

        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
        parse_json3_transcript(payload)
        atomic_write_json(cache_path, dict(payload))
    return TranscriptCacheResult(record.video_id, "CACHED", cache_path)
