from src.adapters.tradingview_chart_provider import fetch_chart_context


def test_fetch_chart_context_returns_provider_payload(monkeypatch) -> None:
    seen = {}

    class _Response:
        status_code = 200

        def json(self):
            return {
                "symbol": "XAUUSD",
                "timeframe": "5m",
                "provider_timestamp": "2026-04-16T12:00:00Z",
                "pine_labels": ["entry"],
                "zones": [],
                "indicator_values": {"rsi": 54.2},
            }

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "src.adapters.tradingview_chart_provider.requests.get",
        lambda *args, **kwargs: (seen.setdefault("kwargs", kwargs), _Response())[1],
    )

    payload = fetch_chart_context(
        base_url="http://provider.test",
        symbol="XAUUSD",
        timeframe="5m",
        timeout_seconds=1.0,
        retry_count=0,
        zone_id=17733,
    )

    assert payload["symbol"] == "XAUUSD"
    assert payload["indicator_values"]["rsi"] == 54.2
    assert seen["kwargs"]["params"] == {
        "symbol": "XAUUSD",
        "timeframe": "5m",
        "zone_id": 17733,
    }


def test_fetch_chart_context_returns_failure_reason_after_retries(monkeypatch) -> None:
    calls = {"count": 0}

    def _boom(*_args, **_kwargs):
        calls["count"] += 1
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(
        "src.adapters.tradingview_chart_provider.requests.get",
        _boom,
    )

    payload = fetch_chart_context(
        base_url="http://provider.test",
        symbol="XAUUSD",
        timeframe="5m",
        timeout_seconds=0.2,
        retry_count=2,
    )

    assert payload["ok"] is False
    assert "provider timeout" in payload["reason"]
    assert calls["count"] == 3
