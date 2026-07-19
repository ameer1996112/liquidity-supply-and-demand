from scripts.rd_concepts_pipeline.models import (
    RuleRecord,
    RuleStatus,
    SourceKind,
    SourceRef,
)
from scripts.rd_concepts_pipeline.rule_catalog import (
    resolve_rule,
    rule_coverage,
    validate_rule_catalog,
)


def make_rule(
    rule_id: str,
    *,
    statement: str = "Use the origin candle.",
    source_id: str = "rd_forex",
    kind: SourceKind = SourceKind.VIDEO,
    status: RuleStatus = RuleStatus.CONFIRMED,
    executable: bool = True,
    supersedes: tuple[str, ...] = (),
) -> RuleRecord:
    return RuleRecord(
        rule_id=rule_id,
        decision_key="zone.origin.demand",
        concept="zone_origin",
        statement=statement,
        timeframe="5m",
        market_scope=("all",),
        status=status,
        executable=executable,
        sources=(SourceRef(kind, source_id, f"{rule_id}:0-1", "manual", 0, 1),),
        supersedes=supersedes,
    )


def test_duplicate_rule_ids_fail() -> None:
    errors = validate_rule_catalog([make_rule("R1"), make_rule("R1")])
    assert "duplicate rule_id: R1" in errors


def test_contradictory_executable_rules_require_supersession() -> None:
    records = [make_rule("R1"), make_rule("R2", statement="Use the departure candle.")]
    assert any(
        "unresolved executable conflict" in error
        for error in validate_rule_catalog(records)
    )

    resolved = [
        make_rule("R1"),
        make_rule("R2", statement="Use the departure candle.", supersedes=("R1",)),
    ]
    assert validate_rule_catalog(resolved) == []
    assert resolve_rule(resolved, "zone.origin.demand").rule_id == "R2"


def test_manual_source_outranks_rd_forex() -> None:
    records = [
        make_rule("RD"),
        make_rule("MANUAL", source_id="manual", kind=SourceKind.MANUAL),
    ]
    assert resolve_rule(records, "zone.origin.demand").rule_id == "MANUAL"


def test_invalid_status_cannot_be_executable() -> None:
    rule = make_rule("R1", status=RuleStatus.CONFLICTING)
    assert "R1: executable rule is not confirmed" in validate_rule_catalog([rule])


def test_coverage_ignores_provisional_cases() -> None:
    records = [make_rule("R1")]
    cases = [
        {
            "label_status": "PROVISIONAL",
            "rules": ["R1"],
            "expected_zones": [{"direction": "DEMAND"}],
            "expected_rejections": [{"reason": "INVALID"}],
        }
    ]
    assert rule_coverage(records, cases) == {
        "missing_positive": ["R1"],
        "missing_negative": ["R1"],
    }


def test_coverage_ignores_rule_superseded_by_active_record() -> None:
    records = [make_rule("R1"), make_rule("R2", supersedes=("R1",))]
    coverage = rule_coverage(records, [])
    assert coverage == {"missing_positive": ["R2"], "missing_negative": ["R2"]}
