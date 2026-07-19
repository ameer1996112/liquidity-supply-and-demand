from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.rd_concepts_pipeline.common import read_jsonl
from scripts.rd_concepts_pipeline.models import (
    RuleRecord,
    RuleStatus,
    SourceKind,
    SourceRef,
)


SOURCE_PRIORITY: Mapping[SourceKind | str, int] = {
    SourceKind.MANUAL: 1,
    "rd_forex": 2,
    "arger_fx": 3,
    "mangoe": 3,
    "rt_futures": 3,
    "charney_fx": 4,
    "trirex": 5,
    SourceKind.PROTECTED_INDICATOR: 6,
}


def load_rule_catalog(path: Path) -> list[RuleRecord]:
    return [RuleRecord.from_mapping(row) for row in read_jsonl(path)]


def source_priority(ref: SourceRef) -> int:
    if ref.kind in {SourceKind.MANUAL, SourceKind.PROTECTED_INDICATOR}:
        return SOURCE_PRIORITY[ref.kind]
    return SOURCE_PRIORITY.get(ref.source_id, 99)


def rule_priority(record: RuleRecord) -> int:
    return min((source_priority(ref) for ref in record.sources), default=99)


def resolve_rule(
    records: Sequence[RuleRecord], decision_key: str
) -> RuleRecord | None:
    superseded_ids = {
        rule_id for record in records for rule_id in record.supersedes
    }
    candidates = [
        record
        for record in records
        if record.decision_key == decision_key
        and record.executable
        and record.status in {RuleStatus.CONFIRMED, RuleStatus.CORROBORATED}
        and record.rule_id not in superseded_ids
    ]
    if not candidates:
        return None

    best_priority = min(rule_priority(record) for record in candidates)
    best = [record for record in candidates if rule_priority(record) == best_priority]
    statements = {record.statement.strip().casefold() for record in best}
    if len(statements) != 1:
        return None
    return min(best, key=lambda record: record.rule_id)


def validate_rule_catalog(records: Sequence[RuleRecord]) -> list[str]:
    errors: list[str] = []
    by_id: dict[str, RuleRecord] = {}
    for record in records:
        if record.rule_id in by_id:
            errors.append(f"duplicate rule_id: {record.rule_id}")
        else:
            by_id[record.rule_id] = record
        errors.extend(
            f"{record.rule_id}: {error}" for error in record.validation_errors()
        )

    known_ids = set(by_id)
    for record in records:
        for related_id in (*record.supersedes, *record.conflicts_with):
            if related_id not in known_ids:
                errors.append(f"{record.rule_id}: unknown related rule {related_id}")

    executable = [record for record in records if record.executable]
    for index, left in enumerate(executable):
        for right in executable[index + 1 :]:
            if left.decision_key != right.decision_key:
                continue
            statements_differ = (
                left.statement.strip().casefold()
                != right.statement.strip().casefold()
            )
            declared_conflict = (
                right.rule_id in left.conflicts_with
                or left.rule_id in right.conflicts_with
            )
            explicitly_resolved = (
                right.rule_id in left.supersedes or left.rule_id in right.supersedes
            )
            if (statements_differ or declared_conflict) and not explicitly_resolved:
                errors.append(
                    f"unresolved executable conflict: {left.rule_id} vs {right.rule_id}"
                )

    for decision_key in {record.decision_key for record in executable}:
        if resolve_rule(records, decision_key) is None:
            errors.append(f"no deterministic executable rule: {decision_key}")
    return sorted(set(errors))


def rule_coverage(
    records: Sequence[RuleRecord], cases: Sequence[Mapping[str, Any]]
) -> dict[str, list[str]]:
    approved = [case for case in cases if case.get("label_status") == "APPROVED"]
    superseded_ids = {
        rule_id for record in records for rule_id in record.supersedes
    }
    active_rule_ids = sorted(
        record.rule_id
        for record in records
        if record.executable
        and record.status in {RuleStatus.CONFIRMED, RuleStatus.CORROBORATED}
        and record.rule_id not in superseded_ids
    )
    return {
        "missing_positive": [
            rule_id
            for rule_id in active_rule_ids
            if not any(
                rule_id in case.get("rules", ()) and case.get("expected_zones")
                for case in approved
            )
        ],
        "missing_negative": [
            rule_id
            for rule_id in active_rule_ids
            if not any(
                rule_id in case.get("rules", ()) and case.get("expected_rejections")
                for case in approved
            )
        ],
    }
