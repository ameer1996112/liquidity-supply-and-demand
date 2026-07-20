import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = (
    ROOT
    / "scripts"
    / "rd_concepts_pipeline"
    / "reference"
    / "rd_5m_decision_matrix.json"
)
RULES_PATH = MATRIX_PATH.with_name("rd_5m_rules.jsonl")
PINE_PATH = ROOT / "scripts" / "pinescript" / "indicators" / "SND_RD_5M_V1_LAB.pine"
REFERENCE_PATH = ROOT / "scripts" / "rd_concepts_pipeline" / "reference_detector.py"


def load_matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def load_rule_ids() -> set[str]:
    return {
        json.loads(line)["rule_id"]
        for line in RULES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def all_decisions(matrix: dict) -> list[dict]:
    return [
        *matrix["decisions"],
        *matrix["eligibility_decisions"],
        *matrix["entry_route_decisions"],
        *matrix["setup_decisions"],
    ]


def test_decision_matrix_is_complete_and_resolved() -> None:
    matrix = load_matrix()
    decisions = matrix["decisions"]
    eligibility = matrix["eligibility_decisions"]
    entry_route = matrix["entry_route_decisions"]
    setup = matrix["setup_decisions"]
    matrix_decisions = all_decisions(matrix)
    decision_ids = [decision["decision_id"] for decision in matrix_decisions]

    assert matrix["version"] == 11
    assert matrix["timeframe"] == "5m"
    assert matrix["runtime_contract"] == "closed_bar_deterministic"
    assert len(decision_ids) == len(set(decision_ids))
    assert all(decision["rule_ids"] for decision in matrix_decisions)
    assert all(len(decision["implementations"]) == 2 for decision in decisions)
    assert all(
        decision["implementation_status"] == "IMPLEMENTED"
        and len(decision["implementations"]) == 2
        for decision in [*eligibility, *entry_route, *setup]
    )
    assert all(conflict["status"] == "RESOLVED" for conflict in matrix["conflicts"])


def test_decision_matrix_references_existing_rules() -> None:
    known_rule_ids = load_rule_ids()
    referenced_rule_ids = {
        rule_id
        for decision in all_decisions(load_matrix())
        for rule_id in decision["rule_ids"]
    }

    assert referenced_rule_ids <= known_rule_ids


def test_every_pine_reason_code_has_a_rule_mapping() -> None:
    pine_source = PINE_PATH.read_text(encoding="utf-8")
    pine_reason_codes = set(
        re.findall(
            r'const string (?:CONFIRM|REJECT|TAP|INVALIDATE|WAIT|LIQUIDITY|EXPIRE|ARM|TRIGGER)_[A-Z_]+ = "([A-Z_]+)"',
            pine_source,
        )
    )
    mapped_reason_codes = {
        decision["reason_code"]
        for decision in all_decisions(load_matrix())
        if decision["reason_code"] is not None
    }

    assert pine_reason_codes == mapped_reason_codes


def test_reference_detector_reason_codes_match_pine_contract() -> None:
    reference_source = REFERENCE_PATH.read_text(encoding="utf-8")
    mapped_reason_codes = {
        decision["reason_code"]
        for decision in all_decisions(load_matrix())
        if decision["reason_code"] is not None
    }
    emitted_reason_codes = set(
        re.findall(
            r'"((?:CONFIRM|REJECT|TAP|INVALIDATE|WAIT|LIQUIDITY|EXPIRE|ARM|TRIGGER)_[A-Z_]+)"',
            reference_source,
        )
    )

    assert emitted_reason_codes == mapped_reason_codes


def test_liquidity_eligibility_does_not_hide_raw_zones() -> None:
    matrix = load_matrix()
    contract = matrix["eligibility_contract"]
    eligibility = matrix["eligibility_decisions"]

    assert contract == {
        "stage": "post_raw_confirmation_pre_entry",
        "raw_zone_visibility_unchanged": True,
        "implementation_status": "IMPLEMENTED",
        "default_policy": "fail_closed",
    }
    assert all("Keep the raw zone visible" in item["outcome"] for item in eligibility[:3])
    assert {
        "RD5M-LIQUIDITY-MIN-OPPOSITE-CANDLES",
        "RD5M-LIQUIDITY-TAKE-OWN-EXTREME",
        "RD5M-LIQUIDITY-ONE-CANDLE-EXCEPTION",
    } <= {
        rule_id
        for item in eligibility
        for rule_id in item["rule_ids"]
    }


def test_clean_view_requires_fresh_zones_that_qualified_at_least_once() -> None:
    matrix = load_matrix()

    assert matrix["clean_view_contract"] == {
        "stage": "display_only_post_eligibility",
        "fresh_zone_required": True,
        "liquidity_qualified_once_required": True,
        "current_eligibility_state_required": False,
        "current_setup_state_required": False,
        "raw_audit_unchanged": True,
    }


def test_liquidity_display_requires_a_zone_relative_level() -> None:
    matrix = load_matrix()

    assert matrix["liquidity_display_contract"] == {
        "stage": "display_only",
        "visible_zone_link_required": True,
        "formed_after_zone_confirmation_required": True,
        "demand_low_strictly_above_zone_required": True,
        "supply_high_strictly_below_zone_required": True,
        "global_unlinked_levels_drawn": False,
        "raw_audit_bypasses_zone_relationship": False,
    }


def test_premium_presentation_is_display_only_and_default_on() -> None:
    matrix = load_matrix()

    assert matrix["presentation_contract"] == {
        "stage": "display_only",
        "premium_visuals_default": True,
        "diagnostic_labels_hidden_in_premium": True,
        "own_extreme_audit_lines_hidden_in_premium": True,
        "status_panel_default": False,
        "detector_and_setup_state_unchanged": True,
    }


def test_setup_handoff_is_non_executable_and_fail_closed() -> None:
    matrix = load_matrix()

    assert matrix["setup_contract"] == {
        "stage": "post_liquidity_eligibility_first_target_return",
        "raw_zone_visibility_unchanged": True,
        "executable": False,
        "implementation_status": "IMPLEMENTED",
        "default_policy": "fail_closed",
    }
    assert {
        "ARM_SETUP_AFTER_LIQUIDITY",
        "TRIGGER_FIRST_FRESH_TAP_AFTER_LIQUIDITY",
        "REJECT_TARGET_TAP_WITHOUT_ELIGIBILITY",
        "REJECT_TARGET_INVALIDATED_ON_RETURN",
        "REJECT_AMBIGUOUS_SAME_BAR_ROUTE",
    } <= {
        item["reason_code"]
        for item in matrix["setup_decisions"]
        if item["reason_code"] is not None
    }
