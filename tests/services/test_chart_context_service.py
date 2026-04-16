from src.services.chart_context_service import ChartContextProviderResult, normalize_chart_context


def test_normalize_chart_context_returns_degraded_payload_when_provider_fails() -> None:
    payload = normalize_chart_context(
        provider_result=ChartContextProviderResult(
            ok=False,
            symbol="XAUUSD",
            timeframe="5m",
            structured=None,
            screenshot_url=None,
            reason="TradingView MCP unavailable",
        )
    )

    assert payload["status"] == "degraded"
    assert payload["reason"] == "TradingView MCP unavailable"
    assert payload["structured"] == {}


def test_normalize_chart_context_preserves_structured_signal_artifacts() -> None:
    payload = normalize_chart_context(
        provider_result=ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={
                "pine_labels": ["sweep", "entry"],
                "zones": [{"kind": "liquidity", "top": 3300.0, "bottom": 3297.5}],
            },
            screenshot_url="http://example.test/xau.png",
            reason="",
        )
    )

    assert payload["status"] == "ok"
    assert payload["symbol"] == "XAUUSD"
    assert payload["structured"]["pine_labels"] == ["sweep", "entry"]
