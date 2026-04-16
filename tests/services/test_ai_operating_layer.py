from src.services.ai_operating_layer import build_posttrade_review_run, build_shadow_pretrade_run


def test_shadow_pretrade_run_marks_analysis_mode_and_module_health() -> None:
    result = build_shadow_pretrade_run(
        signal_payload={"symbol": "XAUUSD", "side": "buy"},
        chart_context={"status": "ok", "structured": {"pine_labels": ["entry"]}},
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert result["analysis_mode"] == "shadow_pretrade"
    assert result["module_status"]["chart_context"]["status"] == "ok"
    assert result["layered_output"]["top_level"]["verdict"] == "unclear"


def test_posttrade_review_run_includes_chart_and_pine_context() -> None:
    result = build_posttrade_review_run(
        signal_payload={"symbol": "XAUUSD", "side": "sell"},
        trade_outcome={"result": "loss"},
        chart_context={"status": "degraded", "reason": "provider unavailable", "structured": {}},
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert result["analysis_mode"] == "posttrade_review"
    assert result["module_status"]["chart_context"]["reason"] == "provider unavailable"
    assert result["pine_context"]["script_name"] == "Liquidity Sweeps"
