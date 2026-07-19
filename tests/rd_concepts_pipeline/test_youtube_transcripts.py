from pathlib import Path
import json

from scripts.rd_concepts_pipeline.models import EvidenceClass, VideoRecord
from scripts.rd_concepts_pipeline.youtube_transcripts import (
    cache_transcript,
    parse_json3_transcript,
    transcript_command,
)


FIXTURE = Path("tests/rd_concepts_pipeline/fixtures/youtube_transcript.json3")
VIDEO = VideoRecord(
    source_id="rd_forex",
    video_id="course1",
    title="Full course",
    url="https://www.youtube.com/watch?v=course1",
    evidence_class=EvidenceClass.RULE_SOURCE,
)


def test_parse_json3_preserves_timestamps_and_ignores_blank_cues() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cues = parse_json3_transcript(payload)

    assert [(cue.start_ms, cue.duration_ms, cue.text) for cue in cues] == [
        (223000, 2000, "Never close in the zone."),
        (225000, 2500, "Liquidity must take out its own high."),
    ]


def test_transcript_command_is_subtitle_only(tmp_path: Path) -> None:
    command = transcript_command(VIDEO, tmp_path)
    assert "--skip-download" in command
    assert "--write-subs" in command
    assert "--write-auto-subs" in command
    assert command[command.index("--sub-format") + 1] == "json3"
    assert command[-1] == VIDEO.url


def test_cache_transcript_normalizes_generated_filename(tmp_path: Path) -> None:
    def runner(argv: list[str]) -> str:
        output_template = Path(argv[argv.index("--output") + 1])
        output = output_template.parent / "course1.en.json3"
        output.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        return ""

    result = cache_transcript(VIDEO, tmp_path, runner)

    assert result.status == "CACHED"
    assert result.path == tmp_path / "youtube" / "transcripts" / "course1.json3"
    assert result.path.exists()


def test_cache_transcript_does_not_reuse_stale_partial_output(tmp_path: Path) -> None:
    transcript_dir = tmp_path / "youtube" / "transcripts"
    transcript_dir.mkdir(parents=True)
    stale = transcript_dir / "course1.en.json3"
    stale.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    result = cache_transcript(VIDEO, tmp_path, lambda _argv: "")

    assert result.status == "NO_TRANSCRIPT"
    assert stale.exists()


def test_cache_transcript_skips_existing_file(tmp_path: Path) -> None:
    cache_path = tmp_path / "youtube" / "transcripts" / "course1.json3"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    result = cache_transcript(
        VIDEO,
        tmp_path,
        lambda _argv: (_ for _ in ()).throw(AssertionError("runner called")),
    )

    assert result.status == "SKIPPED"


def test_cache_transcript_records_missing_subtitles(tmp_path: Path) -> None:
    result = cache_transcript(VIDEO, tmp_path, lambda _argv: "")
    assert result.status == "NO_TRANSCRIPT"
    assert result.path is None
