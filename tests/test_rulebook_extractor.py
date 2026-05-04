import json

from scripts.optimizer.rulebook_extractor import extract_rulebook


def test_rulebook_extractor_classifies_mechanical_rules_with_evidence(tmp_path) -> None:
    source_dir = tmp_path / "videos"
    source_dir.mkdir()
    (source_dir / "course.txt").write_text(
        "\n".join(
            [
                "[13:29] Liquidity must be swept before price touches the zone.",
                "[14:10] Enter long only when price returns to demand and closes bullish.",
                "[15:02] Stop loss goes beyond the zone wick.",
                "[16:00] Do not trade when news risk is active.",
            ]
        )
    )

    rulebook_path = tmp_path / "strategy_rulebook.json"
    evidence_path = tmp_path / "rule_evidence.csv"
    report_path = tmp_path / "strategy_rulebook_report.md"

    payload = extract_rulebook(source_dir, rulebook_path, evidence_path, report_path)

    assert payload["schema_version"] == 1
    assert len(payload["rules"]) == 4
    assert {rule["rule_type"] for rule in payload["rules"]} >= {
        "liquidity_sweep_rule",
        "entry_rule",
        "stop_loss_rule",
        "skip_condition",
    }
    first = payload["rules"][0]
    assert first["timestamp"] == "13:29"
    assert first["pine_coverage"] == "ambiguous"
    assert first["critical"] is True
    assert json.loads(rulebook_path.read_text())["rules"][0]["source_file"] == "course.txt"
    assert "rule_id,source_file,timestamp" in evidence_path.read_text()
    assert "Strategy Rulebook Report" in report_path.read_text()
