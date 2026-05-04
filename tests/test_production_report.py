from scripts.optimizer.production_report import build_production_report


def test_production_report_counts_trust_statuses_and_issues() -> None:
    report = build_production_report(
        {
            "USDCAD": {
                "status": "completed",
                "result_truth": {
                    "evidence_required": True,
                    "trust_status": "trusted",
                    "missing_evidence": [],
                    "rejection_reasons": [],
                },
            },
            "EURUSD": {"status": "completed"},
        }
    )

    assert report["counts"]["trusted"] == 1
    assert report["counts"]["untrusted"] == 1
    assert report["results"]["EURUSD"]["issues"] == ["missing_result_truth"]
