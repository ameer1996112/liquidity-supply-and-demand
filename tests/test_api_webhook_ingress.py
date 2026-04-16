"""Focused production-boundary tests for webhook ingress behavior in src.api."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import app


class _FailingTransport:
    """Test double that simulates a queue outage during webhook enqueue."""

    def enqueue(self, payload: str, queue_key: str = "signals:default") -> None:
        raise RuntimeError("queue down")


class _FakeSupabaseTable:
    def insert(self, row):
        self.row = row
        return self

    def execute(self):
        return SimpleNamespace(data={})


class _FakeSupabase:
    def table(self, _name: str) -> _FakeSupabaseTable:
        return _FakeSupabaseTable()


@patch("src.api.validate_webhook_secret", return_value=None)
@patch("src.api.get_transport", return_value=_FailingTransport())
@patch("src.api.build_received_signal_row", return_value={"id": "signal-row"})
@patch("src.api.resolve_and_stamp_strategy_context", side_effect=lambda payload: payload)
@patch("src.api._get_system_trading_mode", return_value="PAPER")
@patch("src.adapters.supabase.get_supabase", return_value=_FakeSupabase())
@patch("src.core.account_router.AccountRouter.resolve_account_id", return_value="acct-1")
def test_webhook_returns_503_when_queue_enqueue_fails(
    _mock_account_id,
    _mock_supabase,
    _mock_mode,
    _mock_strategy_context,
    _mock_signal_row,
    _mock_transport,
    _mock_secret,
) -> None:
    client = TestClient(app)

    response = client.post(
        "/webhook",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2400.0,
            "sl": 2390.0,
            "tp": 2420.0,
            "size": 0.1,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Signal queue unavailable. Webhook not accepted."


@patch("src.api.get_settings", return_value=SimpleNamespace(ai_mode="shadow"))
@patch("src.services.ai_mode_override.get_ai_mode_override", side_effect=RuntimeError("db unavailable"))
def test_get_effective_ai_mode_falls_back_to_settings_when_override_lookup_fails(
    _mock_settings,
    _mock_override,
) -> None:
    from src.api import _get_effective_ai_mode

    assert _get_effective_ai_mode() == "shadow"
