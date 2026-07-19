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


def test_decision_matrix_is_complete_and_resolved() -> None:
    matrix = load_matrix()
    decisions = matrix["decisions"]
    decision_ids = [decision["decision_id"] for decision in decisions]

    assert matrix["timeframe"] == "5m"
    assert matrix["runtime_contract"] == "closed_bar_deterministic"
    assert len(decision_ids) == len(set(decision_ids))
    assert all(decision["rule_ids"] for decision in decisions)
    assert all(len(decision["implementations"]) == 2 for decision in decisions)
    assert all(conflict["status"] == "RESOLVED" for conflict in matrix["conflicts"])


def test_decision_matrix_references_existing_rules() -> None:
    known_rule_ids = load_rule_ids()
    referenced_rule_ids = {
        rule_id
        for decision in load_matrix()["decisions"]
        for rule_id in decision["rule_ids"]
    }

    assert referenced_rule_ids <= known_rule_ids


def test_every_pine_reason_code_has_a_rule_mapping() -> None:
    pine_source = PINE_PATH.read_text(encoding="utf-8")
    pine_reason_codes = set(
        re.findall(
            r'const string (?:CONFIRM|REJECT|TAP|INVALIDATE)_[A-Z_]+ = "([A-Z_]+)"',
            pine_source,
        )
    )
    mapped_reason_codes = {
        decision["reason_code"]
        for decision in load_matrix()["decisions"]
        if decision["reason_code"] is not None
    }

    assert pine_reason_codes == mapped_reason_codes


def test_reference_detector_reason_codes_match_pine_contract() -> None:
    reference_source = REFERENCE_PATH.read_text(encoding="utf-8")
    mapped_reason_codes = {
        decision["reason_code"]
        for decision in load_matrix()["decisions"]
        if decision["reason_code"] is not None
    }
    emitted_reason_codes = set(
        re.findall(
            r'"((?:CONFIRM|REJECT|TAP|INVALIDATE)_[A-Z_]+)"',
            reference_source,
        )
    )

    assert emitted_reason_codes == mapped_reason_codes
