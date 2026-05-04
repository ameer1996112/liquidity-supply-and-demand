from scripts.optimizer.audit_result import audit_result


def test_audit_result_reports_missing_result_truth() -> None:
    audit = audit_result({"status": "completed", "params": {"risk_per_trade_pct": 0.5}})

    assert audit["trust_status"] == "untrusted"
    assert "missing_result_truth" in audit["issues"]


def test_audit_result_passes_trusted_result_truth() -> None:
    audit = audit_result(
        {
            "status": "completed",
            "result_truth": {
                "evidence_required": True,
                "trust_status": "trusted",
                "missing_evidence": [],
                "rejection_reasons": [],
            },
        }
    )

    assert audit["trust_status"] == "trusted"
    assert audit["issues"] == []
