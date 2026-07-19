from __future__ import annotations

import re

from scripts.rd_concepts_pipeline.models import ChannelSource, EvidenceClass


CHANNEL_SOURCES: tuple[ChannelSource, ...] = (
    ChannelSource(
        "rd_forex",
        "RD Forex",
        "https://www.youtube.com/@RD_Forex",
        2,
        "canonical 5m rules",
    ),
    ChannelSource(
        "arger_fx",
        "Arger FX",
        "https://www.youtube.com/@argerfx",
        3,
        "rule corroboration",
    ),
    ChannelSource(
        "mangoe",
        "Mangoe",
        "https://www.youtube.com/@_mangoe",
        3,
        "rule corroboration",
    ),
    ChannelSource(
        "rt_futures",
        "RT Futures",
        "https://www.youtube.com/@RTFutures",
        3,
        "rule corroboration",
    ),
    ChannelSource(
        "charney_fx",
        "CharneyFX",
        "https://www.youtube.com/@CharneyFX",
        4,
        "filter and skipped-trade evidence",
    ),
    ChannelSource(
        "trirex",
        "Trirex",
        "https://www.youtube.com/@quentintrirex",
        5,
        "automation and performance evidence",
    ),
)

OPERATIONS_PATTERN = re.compile(
    r"\b(bot|ea|automated|automation|portfolio|drawdown)\b", re.I
)
RULE_PATTERN = re.compile(
    r"full (course|guide)|blueprint|checklist|how to (draw|enter|identify)|"
    r"entry confirmation|only trading strategy|5.?minute.*strategy",
    re.I,
)
EDGE_PATTERN = re.compile(
    r"backtest|breakdown|skipp?ed|loss|live trad|perfect setup|week(ly)? recap|"
    r"trade taken|trades? missed",
    re.I,
)
RELEVANCE_PATTERN = re.compile(
    r"supply\s*(?:&|and)?\s*demand|\bs&d\b|\bliquidity\b|\bzone(s)?\b|"
    r"\bentry (model|confirmation)\b|\bstrategy\b|\bsetup(s)?\b",
    re.I,
)


def classify_video_title(title: str) -> EvidenceClass:
    if OPERATIONS_PATTERN.search(title):
        return EvidenceClass.OPERATIONS_EVIDENCE
    if RULE_PATTERN.search(title):
        return EvidenceClass.RULE_SOURCE
    if EDGE_PATTERN.search(title):
        return EvidenceClass.EDGE_EVIDENCE
    if RELEVANCE_PATTERN.search(title):
        return EvidenceClass.EDGE_EVIDENCE
    return EvidenceClass.NON_RULE
