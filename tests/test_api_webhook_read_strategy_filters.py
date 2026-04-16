from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_webhook_read import router


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n: int):
        self._rows = self._rows[:n]
        return self

    def eq(self, key: str, value):
        self._rows = [row for row in self._rows if row.get(key) == value]
        return self

    def in_(self, key: str, values):
        self._rows = [row for row in self._rows if row.get(key) in values]
        return self

    def gte(self, key: str, value):
        self._rows = [row for row in self._rows if (row.get(key) or "") >= value]
        return self

    def execute(self):
        return _FakeResponse(self._rows)


class _FakeSupabase:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self._rows_by_table = rows_by_table

    def table(self, table_name: str):
        return _FakeQuery(self._rows_by_table.get(table_name, []))


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_recent_signals_can_be_filtered_by_strategy(monkeypatch):
    monkeypatch.setattr(
        "src.api_webhook_read._get_supabase",
        lambda: _FakeSupabase(
            {
                "trading_signals": [
                    {"id": 1, "symbol": "EURUSD", "strategy_id": "liq_sd_v1", "strategy_version": "1"},
                    {"id": 2, "symbol": "NAS100", "strategy_id": "breakout_v1", "strategy_version": "1"},
                ]
            }
        ),
    )

    response = _client().get("/api/v1/webhook/signals/recent?strategy_id=liq_sd_v1")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["signals"][0]["strategy_id"] == "liq_sd_v1"


def test_stats_summary_can_be_filtered_by_strategy_version(monkeypatch):
    monkeypatch.setattr(
        "src.api_webhook_read._get_supabase",
        lambda: _FakeSupabase(
            {
                "trading_signals": [
                    {
                        "id": 1,
                        "status": "closed",
                        "outcome": "win",
                        "pnl_usd": 120.0,
                        "rr_ratio": 2.0,
                        "run_mode": "LIVE",
                        "strategy_id": "liq_sd_v1",
                        "strategy_version": "2",
                        "created_at": "2099-01-01T00:00:00+00:00",
                    },
                    {
                        "id": 2,
                        "status": "closed",
                        "outcome": "loss",
                        "pnl_usd": -50.0,
                        "rr_ratio": 1.0,
                        "run_mode": "LIVE",
                        "strategy_id": "liq_sd_v1",
                        "strategy_version": "1",
                        "created_at": "2099-01-01T00:00:00+00:00",
                    },
                ]
            }
        ),
    )
    monkeypatch.setattr("src.services.redis_cache.cache_get", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("src.services.redis_cache.cache_set", lambda *_args, **_kwargs: None)

    response = _client().get("/api/v1/webhook/stats/summary?run_mode=LIVE&strategy_id=liq_sd_v1&strategy_version=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total_trades"] == 1
    assert body["win_count"] == 1
    assert body["loss_count"] == 0
