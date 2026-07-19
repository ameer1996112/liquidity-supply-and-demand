from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class EvidenceClass(str, Enum):
    RULE_SOURCE = "RULE_SOURCE"
    EDGE_EVIDENCE = "EDGE_EVIDENCE"
    OPERATIONS_EVIDENCE = "OPERATIONS_EVIDENCE"
    NON_RULE = "NON_RULE"


class RuleStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CORROBORATED = "CORROBORATED"
    CONFLICTING = "CONFLICTING"
    UNVERIFIED = "UNVERIFIED"
    SUPERSEDED = "SUPERSEDED"


class SourceKind(str, Enum):
    VIDEO = "VIDEO"
    MANUAL = "MANUAL"
    PROTECTED_INDICATOR = "PROTECTED_INDICATOR"


@dataclass(frozen=True)
class ChannelSource:
    source_id: str
    name: str
    channel_url: str
    priority: int
    role: str

    @property
    def videos_url(self) -> str:
        return f"{self.channel_url.rstrip('/')}/videos"


@dataclass(frozen=True)
class VideoRecord:
    source_id: str
    video_id: str
    title: str
    url: str
    evidence_class: EvidenceClass
    published_at: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "evidence_class": self.evidence_class.value,
            "published_at": self.published_at,
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> VideoRecord:
        return cls(
            source_id=str(mapping["source_id"]),
            video_id=str(mapping["video_id"]),
            title=str(mapping["title"]),
            url=str(mapping["url"]),
            evidence_class=EvidenceClass(str(mapping["evidence_class"])),
            published_at=(
                str(mapping["published_at"])
                if mapping.get("published_at") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class TranscriptCue:
    start_ms: int
    duration_ms: int
    text: str

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        if not self.text.strip():
            raise ValueError("text must not be blank")

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass(frozen=True)
class SourceRef:
    kind: SourceKind
    source_id: str
    evidence_id: str
    url: str
    start_ms: int | None = None
    end_ms: int | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.start_ms is not None and self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms is not None and self.end_ms < 0:
            raise ValueError("end_ms must be non-negative")
        if (
            self.start_ms is not None
            and self.end_ms is not None
            and self.end_ms <= self.start_ms
        ):
            raise ValueError("end_ms must be greater than start_ms")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "source_id": self.source_id,
            "evidence_id": self.evidence_id,
            "url": self.url,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "note": self.note,
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> SourceRef:
        return cls(
            kind=SourceKind(str(mapping["kind"])),
            source_id=str(mapping["source_id"]),
            evidence_id=str(mapping["evidence_id"]),
            url=str(mapping["url"]),
            start_ms=(int(mapping["start_ms"]) if mapping.get("start_ms") is not None else None),
            end_ms=(int(mapping["end_ms"]) if mapping.get("end_ms") is not None else None),
            note=str(mapping.get("note", "")),
        )


@dataclass(frozen=True)
class EvidenceSpan:
    span_id: str
    video_id: str
    start_ms: int
    end_ms: int
    text: str
    concepts: tuple[str, ...]
    normative_hits: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if not self.text.strip():
            raise ValueError("evidence span text must not be blank")
        if not self.concepts:
            raise ValueError("evidence span must contain a concept hit")
        if not self.normative_hits:
            raise ValueError("evidence span must contain a normative hit")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "video_id": self.video_id,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "concepts": list(self.concepts),
            "normative_hits": list(self.normative_hits),
        }


@dataclass(frozen=True)
class RuleRecord:
    rule_id: str
    decision_key: str
    concept: str
    statement: str
    timeframe: str
    market_scope: tuple[str, ...]
    status: RuleStatus
    executable: bool
    sources: tuple[SourceRef, ...]
    supersedes: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()

    def validation_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.executable and self.status not in {
            RuleStatus.CONFIRMED,
            RuleStatus.CORROBORATED,
        }:
            errors.append("executable rule is not confirmed")
        if self.executable and not self.sources:
            errors.append("executable rule has no evidence source")
        if self.timeframe != "5m":
            errors.append("rule timeframe must be 5m")
        if not self.market_scope:
            errors.append("rule market_scope is empty")
        return tuple(errors)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "decision_key": self.decision_key,
            "concept": self.concept,
            "statement": self.statement,
            "timeframe": self.timeframe,
            "market_scope": list(self.market_scope),
            "status": self.status.value,
            "executable": self.executable,
            "sources": [source.to_mapping() for source in self.sources],
            "supersedes": list(self.supersedes),
            "conflicts_with": list(self.conflicts_with),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> RuleRecord:
        return cls(
            rule_id=str(mapping["rule_id"]),
            decision_key=str(mapping["decision_key"]),
            concept=str(mapping["concept"]),
            statement=str(mapping["statement"]),
            timeframe=str(mapping["timeframe"]),
            market_scope=tuple(str(value) for value in mapping.get("market_scope", ())),
            status=RuleStatus(str(mapping["status"])),
            executable=bool(mapping["executable"]),
            sources=tuple(
                SourceRef.from_mapping(source) for source in mapping.get("sources", ())
            ),
            supersedes=tuple(str(value) for value in mapping.get("supersedes", ())),
            conflicts_with=tuple(
                str(value) for value in mapping.get("conflicts_with", ())
            ),
        )
