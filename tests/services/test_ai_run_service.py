from src.services.ai_run_service import build_ai_run_row


def test_build_ai_run_row_persists_layered_fields() -> None:
    row = build_ai_run_row(
        correlation_id="corr-1",
        run_payload={
            "analysis_mode": "posttrade_review",
            "chart_context": {"status": "ok"},
            "pine_context": {"script_name": "Liquidity Sweeps"},
            "module_status": {"chart_context": {"status": "ok", "reason": ""}},
            "layered_output": {"top_level": {"verdict": "good setup"}},
        },
    )

    assert row["analysis_mode"] == "posttrade_review"
    assert row["chart_context"]["status"] == "ok"
    assert row["layered_output"]["top_level"]["verdict"] == "good setup"
