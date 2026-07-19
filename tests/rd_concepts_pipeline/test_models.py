from scripts.rd_concepts_pipeline.models import (
    ChannelSource,
    EvidenceClass,
    EvidenceSpan,
    RuleRecord,
    RuleStatus,
    SourceKind,
    SourceRef,
    TranscriptCue,
    VideoRecord,
)


def test_channel_source_builds_videos_url() -> None:
    source = ChannelSource(
        "rd_forex", "RD Forex", "https://www.youtube.com/@RD_Forex", 2, "canonical"
    )
    assert source.videos_url == "https://www.youtube.com/@RD_Forex/videos"


def test_video_record_round_trips_to_mapping() -> None:
    record = VideoRecord(
        source_id="rd_forex",
        video_id="abc123",
        title="Five minute full course",
        url="https://www.youtube.com/watch?v=abc123",
        evidence_class=EvidenceClass.RULE_SOURCE,
        published_at="2026-01-02",
    )
    assert VideoRecord.from_mapping(record.to_mapping()) == record


def test_rule_record_requires_evidence_for_executable_rule() -> None:
    record = RuleRecord(
        rule_id="RD5M-ZONE-001",
        decision_key="zone.origin.demand",
        concept="zone_origin",
        statement="Demand begins from the final bearish origin candle.",
        timeframe="5m",
        market_scope=("all",),
        status=RuleStatus.CONFIRMED,
        executable=True,
        sources=(),
    )
    assert record.validation_errors() == ("executable rule has no evidence source",)


def test_rule_record_round_trips_nested_sources() -> None:
    record = RuleRecord(
        rule_id="RD5M-ZONE-001",
        decision_key="zone.origin.demand",
        concept="zone_origin",
        statement="Demand begins from the final bearish origin candle.",
        timeframe="5m",
        market_scope=("all",),
        status=RuleStatus.CONFIRMED,
        executable=True,
        sources=(
            SourceRef(
                kind=SourceKind.VIDEO,
                source_id="rd_forex",
                evidence_id="abc123:1000-2000",
                url="https://www.youtube.com/watch?v=abc123",
                start_ms=1000,
                end_ms=2000,
            ),
        ),
    )
    assert RuleRecord.from_mapping(record.to_mapping()) == record


def test_evidence_span_requires_normative_and_concept_hits() -> None:
    try:
        EvidenceSpan("abc:0-1000", "abc", 0, 1000, "Never tap it.", (), ("never",))
    except ValueError as exc:
        assert str(exc) == "evidence span must contain a concept hit"
    else:
        raise AssertionError("span without a concept must fail")


def test_transcript_cue_rejects_negative_start() -> None:
    try:
        TranscriptCue(start_ms=-1, duration_ms=1000, text="rule")
    except ValueError as exc:
        assert str(exc) == "start_ms must be non-negative"
    else:
        raise AssertionError("negative start must fail")
