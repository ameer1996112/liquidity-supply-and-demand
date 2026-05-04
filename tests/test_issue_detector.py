from scripts.optimizer.issue_detector import detect_result_issues


def test_issue_detector_flags_missing_source_digest_in_validate_mode() -> None:
    issues = detect_result_issues(
        {
            "status": "completed",
            "result_truth": {
                "evidence_required": True,
                "stage": "validation",
                "trust_status": "untrusted",
                "missing_evidence": ["source_params_digest_preserved"],
                "rejection_reasons": [],
            },
        }
    )

    assert "missing_evidence:source_params_digest_preserved" in issues


def test_issue_detector_flags_failed_range_verification() -> None:
    issues = detect_result_issues(
        {
            "status": "completed",
            "result_truth": {
                "evidence_required": True,
                "trust_status": "rejected",
                "missing_evidence": [],
                "rejection_reasons": [
                    "strategy_tester_range_selected: Strategy Tester range did not match requested range"
                ],
            },
        }
    )

    assert any("strategy_tester_range_selected" in issue for issue in issues)
