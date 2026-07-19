from scripts.rd_concepts_pipeline.evidence_extractor import extract_evidence_spans
from scripts.rd_concepts_pipeline.models import TranscriptCue


def test_extract_evidence_spans_merges_nearby_rule_cues() -> None:
    cues = [
        TranscriptCue(223000, 2000, "Never close in the zone."),
        TranscriptCue(225000, 2500, "Liquidity must take out its own high."),
        TranscriptCue(260000, 1000, "Welcome back to the chart."),
    ]
    spans = extract_evidence_spans("course1", cues, context_ms=15000)

    assert [span.span_id for span in spans] == ["course1:223000-227500"]
    assert {"zone", "liquidity"} <= set(spans[0].concepts)
    assert {"never", "must"} <= set(spans[0].normative_hits)


def test_extract_evidence_spans_keeps_distant_rules_separate() -> None:
    cues = [
        TranscriptCue(0, 1000, "Always use the origin candle."),
        TranscriptCue(20000, 1000, "Never enter this zone."),
    ]
    spans = extract_evidence_spans("course1", cues, context_ms=5000)
    assert [span.span_id for span in spans] == [
        "course1:0-1000",
        "course1:20000-21000",
    ]
