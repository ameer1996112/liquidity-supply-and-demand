from src.services.ai_operating_layer import build_posttrade_review_run, build_shadow_pretrade_run


def test_shadow_pretrade_run_fetches_chart_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {
            "status": "ok",
            "structured": {"provider_timestamp": "2026-04-16T12:00:00Z"},
        },
    )

    payload = build_shadow_pretrade_run(
        signal_payload={"symbol": "XAUUSD", "timeframe": "5m"},
        chart_context=None,
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert payload["chart_context"]["status"] == "ok"
    assert payload["module_status"]["chart_context"]["status"] == "ok"


def test_posttrade_review_run_records_degraded_provider_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {
            "status": "degraded",
            "reason": "provider timeout",
            "structured": {},
        },
    )

    payload = build_posttrade_review_run(
        signal_payload={"symbol": "XAUUSD", "timeframe": "5m"},
        trade_outcome={"result": "loss"},
        chart_context=None,
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert payload["chart_context"]["status"] == "degraded"
    assert payload["module_status"]["chart_context"]["reason"] == "provider timeout"
