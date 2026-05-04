import json

from scripts.optimizer.rulebook_coverage_checker import check_rulebook_coverage


def test_missing_critical_pine_rule_blocks_production(tmp_path) -> None:
    rulebook_path = tmp_path / "strategy_rulebook.json"
    rulebook_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rules": [
                    {
                        "rule_id": "liq_001",
                        "rule_type": "liquidity_sweep_rule",
                        "critical": True,
                        "pine_coverage": "missing",
                        "status": "needs_review",
                    },
                    {
                        "rule_id": "psy_001",
                        "rule_type": "psychology_or_non_mechanical",
                        "critical": False,
                        "pine_coverage": "manual_only",
                        "status": "needs_review",
                    },
                ],
            }
        )
    )

    report = check_rulebook_coverage(rulebook_path, tmp_path / "coverage.md")

    assert report["status"] == "blocked"
    assert report["missing_critical_rule_ids"] == ["liq_001"]
    assert "liq_001" in (tmp_path / "coverage.md").read_text()
