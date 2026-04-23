from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.adapters.execution import router as execution_router
from src.api_portfolio_control import router as portfolio_control_router


class _FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._eq_filters: list[tuple[str, Any]] = []
        self._in_filters: list[tuple[str, tuple[Any, ...]]] = []
        self._null_filters: list[tuple[str, bool]] = []

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def eq(self, key: str, value: Any) -> "_FakeQuery":
        self._eq_filters.append((key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> "_FakeQuery":
        self._in_filters.append((key, tuple(values)))
        return self

    def is_(self, key: str, value: Any) -> "_FakeQuery":
        self._null_filters.append((key, value == "null"))
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def execute(self) -> _FakeResponse:
        matched = []
        for row in self._rows:
            if any(row.get(key) != value for key, value in self._eq_filters):
                continue
            if any(row.get(key) not in values for key, values in self._in_filters):
                continue
            null_filter_failed = False
            for key, should_be_null in self._null_filters:
                if should_be_null and row.get(key) is not None:
                    null_filter_failed = True
                    break
                if not should_be_null and row.get(key) is None:
                    null_filter_failed = True
                    break
            if null_filter_failed:
                continue
            matched.append(row)
        return _FakeResponse(matched)


class _FakeSupabase:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self._tables = tables

    def table(self, table_name: str) -> _FakeQuery:
        return _FakeQuery(self._tables.get(table_name, []))


class _FailingMetaApiAdapter:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("MetaApiAdapter should not be instantiated for cTrader accounts")


class _CapturedCTraderAdapter:
    created_kwargs: list[dict[str, Any]] = []
    broker_positions: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        type(self).created_kwargs.append(kwargs)

    def get_open_positions(self) -> list[dict[str, Any]]:
        return list(type(self).broker_positions)


def _make_client(monkeypatch, *, trading_signals: list[dict[str, Any]], profiles: list[dict[str, Any]]) -> TestClient:
    app = FastAPI()
    app.include_router(portfolio_control_router)

    monkeypatch.setattr(
        "src.api_portfolio_control._get_supabase",
        lambda: _FakeSupabase({"trading_signals": trading_signals, "account_strategies": []}),
    )
    monkeypatch.setattr("src.core.broker_profiles.get_active_profiles", lambda: profiles)
    return TestClient(app)


def test_positions_endpoint_uses_ctrader_adapter_without_metaapi(monkeypatch) -> None:
    _CapturedCTraderAdapter.created_kwargs.clear()
    _CapturedCTraderAdapter.broker_positions = [
        {
            "id": "9001",
            "symbol": "EURUSD",
            "type": "BUY",
            "volume": 0.25,
            "openPrice": 1.0845,
            "currentPrice": 1.0862,
            "sl": 1.08,
            "tp": 1.09,
            "profit": 12.34,
            "swap": -0.45,
            "commission": -1.25,
            "comment": "ctrader-position",
            "time": "2026-04-23T08:00:00+00:00",
        }
    ]
    monkeypatch.setattr(execution_router, "CTraderAdapter", _CapturedCTraderAdapter)
    monkeypatch.setattr(execution_router, "MetaApiAdapter", _FailingMetaApiAdapter)

    client = _make_client(
        monkeypatch,
        trading_signals=[
            {
                "account_name": "ctrader-live",
                "status": "active",
                "broker_order_id": "9001",
                "created_at": "2026-04-23T08:01:00+00:00",
            }
        ],
        profiles=[
            {
                "name": "ctrader-live",
                "venue": "ctrader",
                "token": "refresh-token",
                "meta_api_account_id": "ctrader-account-id",
                "run_mode": "LIVE",
            }
        ],
    )

    response = client.get("/api/portfolio-control/accounts/ctrader-live/positions")

    assert response.status_code == 200
    payload = response.json()
    assert _CapturedCTraderAdapter.created_kwargs == [
        {
            "refresh_token": "refresh-token",
            "ctid_trader_account_id": "ctrader-account-id",
            "account_name": "ctrader-live",
            "is_live": True,
        }
    ]
    assert payload["broker"] == [
        {
            "id": "9001",
            "symbol": "EURUSD",
            "side": "buy",
            "volume": 0.25,
            "open_price": 1.0845,
            "current_price": 1.0862,
            "sl": 1.08,
            "tp": 1.09,
            "profit": 12.34,
            "swap": -0.45,
            "commission": -1.25,
            "open_time": "2026-04-23T08:00:00+00:00",
            "comment": "ctrader-position",
            "reconciliation_status": "matched",
        }
    ]
    assert payload["reconciliation_summary"] == {"matched": 1, "orphaned": 0, "pending": 0}


def test_positions_endpoint_uses_resolve_profile_adapter_output(monkeypatch) -> None:
    resolved_profiles: list[dict[str, Any]] = []

    class _ResolvedAdapter:
        def get_open_positions(self) -> list[dict[str, Any]]:
            return [
                {
                    "id": "555",
                    "symbol": "GBPUSD",
                    "type": "SELL",
                    "volume": 0.1,
                    "openPrice": 1.25,
                    "currentPrice": 1.247,
                    "profit": 8.5,
                    "swap": 0.0,
                    "commission": -0.5,
                    "comment": "from-resolver",
                    "time": "2026-04-23T09:00:00+00:00",
                }
            ]

    def _resolve_profile_adapter(profile: dict[str, Any] | None):
        assert profile is not None
        resolved_profiles.append(profile)
        return _ResolvedAdapter()

    monkeypatch.setattr(execution_router, "resolve_profile_adapter", _resolve_profile_adapter)
    monkeypatch.setattr(execution_router, "MetaApiAdapter", _FailingMetaApiAdapter)

    client = _make_client(
        monkeypatch,
        trading_signals=[],
        profiles=[
            {
                "name": "ctrader-eval",
                "venue": "ctrader",
                "token": "refresh-token",
                "account_id": "eval-account-id",
                "run_mode": "DEMO",
            }
        ],
    )

    response = client.get("/api/portfolio-control/accounts/ctrader-eval/positions")

    assert response.status_code == 200
    assert resolved_profiles == [
        {
            "name": "ctrader-eval",
            "venue": "ctrader",
            "token": "refresh-token",
            "account_id": "eval-account-id",
            "run_mode": "DEMO",
        }
    ]
    payload = response.json()
    assert payload["broker"][0]["id"] == "555"
    assert payload["broker"][0]["symbol"] == "GBPUSD"
    assert payload["broker"][0]["side"] == "sell"
    assert payload["broker"][0]["profit"] == 8.5
    assert payload["broker"][0]["reconciliation_status"] == "orphaned"
    assert payload["reconciliation_summary"] == {"matched": 0, "orphaned": 1, "pending": 0}
