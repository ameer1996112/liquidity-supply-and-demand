from fastapi.testclient import TestClient

from src.local_chart_provider_app import app


def test_chart_context_endpoint_returns_provider_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.fetch_live_chart_context",
        lambda symbol, timeframe: {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider_timestamp": "2026-04-17T00:20:00Z",
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "reason": "",
            "metadata": {"partial_failures": []},
        },
    )

    client = TestClient(app)
    response = client.get("/chart-context", params={"symbol": "XAUUSD", "timeframe": "5m"})

    assert response.status_code == 200
    assert response.json()["symbol"] == "XAUUSD"
    assert response.json()["provider_timestamp"] == "2026-04-17T00:20:00Z"


def test_chart_context_endpoint_requires_query_params() -> None:
    client = TestClient(app)
    response = client.get("/chart-context")
    assert response.status_code == 422
