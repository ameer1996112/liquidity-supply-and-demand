from fastapi.testclient import TestClient

from src.local_chart_provider_app import app


def test_chart_context_endpoint_returns_provider_payload(monkeypatch) -> None:
    seen = {}

    def _fake_fetch(symbol, timeframe, zone_id=None):
        seen["args"] = (symbol, timeframe, zone_id)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider_timestamp": "2026-04-17T00:20:00Z",
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "setup_evidence": {
                "status": "degraded",
                "focus_zone": None,
                "focus_image": None,
                "reason": "",
            },
            "reason": "",
            "metadata": {"partial_failures": []},
        }

    monkeypatch.setattr(
        "src.local_chart_provider_app.fetch_live_chart_context",
        _fake_fetch,
    )

    client = TestClient(app)
    response = client.get("/chart-context", params={"symbol": "XAUUSD", "timeframe": "5m", "zone_id": 17733})

    assert response.status_code == 200
    assert response.json()["symbol"] == "XAUUSD"
    assert response.json()["provider_timestamp"] == "2026-04-17T00:20:00Z"
    assert seen["args"] == ("XAUUSD", "5m", 17733)


def test_chart_context_endpoint_promotes_focus_image_to_absolute_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.fetch_live_chart_context",
        lambda symbol, timeframe, zone_id=None: {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider_timestamp": "2026-04-17T00:20:00Z",
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "setup_evidence": {
                "status": "ok",
                "focus_zone": {"label": "ILP", "high": 0.7210, "low": 0.7195},
                "focus_image": {"path": "mcp/tradingview-mcp/screenshots/setup-audusd.png"},
                "reason": "",
            },
            "reason": "",
            "metadata": {"partial_failures": []},
        },
    )

    client = TestClient(app)
    response = client.get("/chart-context", params={"symbol": "XAUUSD", "timeframe": "5m"})

    assert response.status_code == 200
    assert response.json()["setup_evidence"]["focus_image"]["url"].startswith(
        "http://testserver/provider-artifacts/"
    )


def test_chart_context_endpoint_requires_query_params() -> None:
    client = TestClient(app)
    response = client.get("/chart-context")
    assert response.status_code == 422


def test_compatibility_health_endpoint_returns_cached_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.get_chart_provider_compatibility_status",
        lambda: {
            "status": "supported",
            "chart_context_enabled": True,
            "tradingview_version": "2.9.0",
            "checked_at": "2026-04-21T12:00:00Z",
            "reason": "",
            "probe": {"command": "status", "ok": True},
        },
    )

    client = TestClient(app)
    response = client.get("/health/compatibility")

    assert response.status_code == 200
    assert response.json()["status"] == "supported"
    assert response.json()["chart_context_enabled"] is True
    assert response.json()["tradingview_version"] == "2.9.0"


def test_compatibility_health_endpoint_supports_browser_cors(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.get_chart_provider_compatibility_status",
        lambda: {
            "status": "probe_failed",
            "chart_context_enabled": False,
            "tradingview_version": "2.9.1",
            "checked_at": "2026-04-21T12:00:00Z",
            "reason": "status command failed",
            "probe": {"command": "status", "ok": False},
        },
    )

    client = TestClient(app)
    response = client.options(
        "/health/compatibility",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_compatibility_health_endpoint_supports_railway_frontend_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.get_chart_provider_compatibility_status",
        lambda: {
            "status": "probe_failed",
            "chart_context_enabled": False,
            "tradingview_version": "3.1.0",
            "checked_at": "2026-04-22T18:00:00Z",
            "reason": "status command failed",
            "probe": {"command": "status", "ok": False},
        },
    )

    client = TestClient(app)
    response = client.options(
        "/health/compatibility",
        headers={
            "Origin": "https://frontend-production-a7cf.up.railway.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://frontend-production-a7cf.up.railway.app"
    )
    assert "GET" in response.headers["access-control-allow-methods"]
