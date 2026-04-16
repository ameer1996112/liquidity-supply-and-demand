from src.services.chart_context_service import (
    ChartContextProviderResult,
    normalize_chart_context,
)


def test_normalize_chart_context_requires_structured_contract_fields() -> None:
    payload = normalize_chart_context(
        ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={"zones": []},
            screenshot_url=None,
            reason="",
        )
    )

    assert payload["status"] == "degraded"
    assert payload["reason"] == "provider returned incomplete structured state"


def test_normalize_chart_context_accepts_full_structured_contract() -> None:
    payload = normalize_chart_context(
        ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={
                "provider_timestamp": "2026-04-16T12:00:00Z",
                "pine_labels": [],
                "zones": [],
                "indicator_values": {"rsi": 54.2},
            },
            screenshot_url=None,
            reason="",
        )
    )

    assert payload["status"] == "ok"
    assert payload["structured"]["provider_timestamp"] == "2026-04-16T12:00:00Z"
