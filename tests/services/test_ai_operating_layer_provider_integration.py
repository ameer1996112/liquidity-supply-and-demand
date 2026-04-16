from src.services.ai_operating_layer import build_posttrade_review_run, build_shadow_pretrade_run


def test_shadow_pretrade_run_fetches_chart_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {
            "status": "ok",
            "structured": {
                "provider_timestamp": "2026-04-16T12:00:00Z",
                "setup_evidence": {
                    "status": "ok",
                    "focus_zone": {"label": "ILP", "high": 0.7210, "low": 0.7195},
                    "focus_image": {"url": "https://provider/setup.png"},
                    "reason": "",
                },
            },
        },
    )

    payload = build_shadow_pretrade_run(
        signal_payload={"symbol": "XAUUSD", "timeframe": "5m"},
        chart_context=None,
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert payload["chart_context"]["status"] == "ok"
    assert payload["module_status"]["chart_context"]["status"] == "ok"
    assert payload["chart_context"]["structured"]["setup_evidence"]["status"] == "ok"


def test_posttrade_review_run_records_degraded_provider_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {
            "status": "degraded",
            "reason": "provider timeout",
            "structured": {
                "setup_evidence": {
                    "status": "degraded",
                    "focus_zone": None,
                    "focus_image": None,
                    "reason": "provider timeout",
                }
            },
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
    assert payload["chart_context"]["structured"]["setup_evidence"]["reason"] == "provider timeout"
