from __future__ import annotations

import re
from collections.abc import Sequence

from scripts.rd_concepts_pipeline.models import EvidenceSpan, TranscriptCue


NORMATIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    label: re.compile(pattern, re.I)
    for label, pattern in {
        "must": r"\bmust\b",
        "always": r"\balways\b",
        "never": r"\bnever\b",
        "only": r"\bonly\b",
        "valid": r"\bvalid\b",
        "invalid": r"\binvalid\b",
        "wait": r"\bwait\b",
        "do_not": r"\bdo not\b|\bdon't\b",
        "rule": r"\brule\b",
    }.items()
}
CONCEPT_PATTERNS: dict[str, re.Pattern[str]] = {
    label: re.compile(pattern, re.I)
    for label, pattern in {
        "zone": r"\bzone(s)?\b",
        "origin": r"\borigin\b",
        "base": r"\bbase\b",
        "wick": r"\bwick(s)?\b",
        "candle": r"\bcandle(s)?\b",
        "departure": r"\bdeparture\b",
        "liquidity": r"\bliquidity\b",
        "sweep": r"\bsweep(s|ed)?\b",
        "entry": r"\bentry\b|\benter\b",
        "stop": r"\bstop( loss)?\b",
        "target": r"\btarget(s)?\b",
        "time": r"\btime\b|\bminute(s)?\b|\bhour\b",
        "risk": r"\brisk\b",
    }.items()
}


def _hits(text: str, patterns: dict[str, re.Pattern[str]]) -> set[str]:
    return {label for label, pattern in patterns.items() if pattern.search(text)}


def extract_evidence_spans(
    video_id: str,
    cues: Sequence[TranscriptCue],
    context_ms: int = 15_000,
) -> list[EvidenceSpan]:
    if context_ms < 0:
        raise ValueError("context_ms must be non-negative")

    matched: list[tuple[TranscriptCue, set[str], set[str]]] = []
    for cue in sorted(cues, key=lambda item: item.start_ms):
        normative_hits = _hits(cue.text, NORMATIVE_PATTERNS)
        concept_hits = _hits(cue.text, CONCEPT_PATTERNS)
        if normative_hits and concept_hits:
            matched.append((cue, normative_hits, concept_hits))

    groups: list[list[tuple[TranscriptCue, set[str], set[str]]]] = []
    for item in matched:
        if not groups or item[0].start_ms - groups[-1][-1][0].end_ms > context_ms:
            groups.append([item])
        else:
            groups[-1].append(item)

    spans: list[EvidenceSpan] = []
    for group in groups:
        start_ms = group[0][0].start_ms
        end_ms = max(item[0].end_ms for item in group)
        spans.append(
            EvidenceSpan(
                span_id=f"{video_id}:{start_ms}-{end_ms}",
                video_id=video_id,
                start_ms=start_ms,
                end_ms=end_ms,
                text=" ".join(item[0].text for item in group),
                concepts=tuple(sorted({hit for item in group for hit in item[2]})),
                normative_hits=tuple(sorted({hit for item in group for hit in item[1]})),
            )
        )
    return spans
