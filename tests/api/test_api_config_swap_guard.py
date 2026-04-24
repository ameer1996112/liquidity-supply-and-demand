from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api_config as api_config


class _Resp:
    def __init__(self, data):
        self.data = data


def _make_supabase(store: dict[str, str]):
    class _SelectQuery:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, _field: str, keys):
            self._keys = keys
            return self

        def execute(self):
            rows = [
                {"key": key, "value": value}
                for key, value in store.items()
                if key in self._keys
            ]
            return _Resp(rows)

    class _UpsertQuery:
        def upsert(self, payload, **_kwargs):
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                store[row["key"]] = row["value"]
            return self

        def execute(self):
            return _Resp([])

    class _Supabase:
        def table(self, _name: str):
            class _Table:
                def select(self, *_args, **_kwargs):
                    return _SelectQuery().select(*_args, **_kwargs)

                def upsert(self, payload, **_kwargs):
                    return _UpsertQuery().upsert(payload, **_kwargs)

            return _Table()

    return _Supabase()


def test_get_swap_guard_config_returns_system_config(monkeypatch) -> None:
    store = {
        "swap_guard_enabled": "false",
        "swap_time": "23:55",
        "swap_timezone": "UTC",
        "swap_close_before_min": "10",
        "swap_min_block_after_min": "30",
        "swap_max_block_after_min": "90",
        "swap_recovery_consecutive_checks": "2",
        "swap_recovery_window_seconds": "180",
        "swap_fx_max_spread": "0.00025",
        "swap_jpy_max_spread": "0.025",
        "swap_gold_max_spread": "0.75",
        "swap_default_max_spread": "0.00040",
        "swap_symbol_spread_overrides_json": '{"XAUUSD":0.8}',
    }
    monkeypatch.setattr(api_config, "_get_supabase", lambda: _make_supabase(store))

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.get("/api/v1/config/swap-guard")

    assert response.status_code == 200
    body = response.json()
    assert body["enable_swap_guard"] is False
    assert body["swap_time"] == "23:55"
    assert body["swap_timezone"] == "UTC"
    assert body["swap_max_block_after_min"] == 90
    assert body["swap_symbol_spread_overrides_json"] == '{"XAUUSD":0.8}'


def test_patch_swap_guard_config_persists_runtime_values(monkeypatch) -> None:
    store: dict[str, str] = {}
    invalidated = {"called": False}
    monkeypatch.setattr(api_config, "_get_supabase", lambda: _make_supabase(store))
    monkeypatch.setattr(
        api_config,
        "_invalidate_swap_guard_cache",
        lambda: invalidated.__setitem__("called", True),
    )

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/config/swap-guard",
        json={
            "enable_swap_guard": True,
            "swap_max_block_after_min": 90,
            "swap_gold_max_spread": 0.75,
        },
    )

    assert response.status_code == 200
    assert store["swap_guard_enabled"] == "true"
    assert store["swap_max_block_after_min"] == "90"
    assert store["swap_gold_max_spread"] == "0.75"
    assert invalidated["called"] is True


def test_worker_swap_guard_settings_prefer_system_config(monkeypatch) -> None:
    import src.worker as worker

    store = {
        "swap_guard_enabled": "true",
        "swap_time": "23:55",
        "swap_timezone": "UTC",
        "swap_close_before_min": "10",
        "swap_min_block_after_min": "30",
        "swap_max_block_after_min": "90",
        "swap_recovery_consecutive_checks": "2",
        "swap_recovery_window_seconds": "180",
        "swap_fx_max_spread": "0.00025",
        "swap_jpy_max_spread": "0.025",
        "swap_gold_max_spread": "0.75",
        "swap_default_max_spread": "0.00040",
        "swap_symbol_spread_overrides_json": '{"XAUUSD":0.8}',
    }
    monkeypatch.setattr(worker, "_get_fresh_supabase", lambda: _make_supabase(store))
    worker._swap_guard_config_cache = {"values": None, "loaded_at": 0.0}

    settings = SimpleNamespace(
        enable_swap_guard=False,
        swap_time="00:00",
        swap_timezone="Asia/Jerusalem",
        swap_close_before_min=15,
        swap_min_block_after_min=45,
        swap_max_block_after_min=240,
        swap_recovery_consecutive_checks=3,
        swap_recovery_window_seconds=300,
        swap_fx_max_spread=0.00030,
        swap_jpy_max_spread=0.030,
        swap_gold_max_spread=0.50,
        swap_default_max_spread=0.00050,
        swap_symbol_spread_overrides_json="",
    )

    cfg = worker._get_swap_guard_settings(settings)

    assert cfg["enable_swap_guard"] is True
    assert cfg["swap_time"] == "23:55"
    assert cfg["swap_timezone"] == "UTC"
    assert cfg["swap_max_block_after_min"] == 90
    assert cfg["swap_gold_max_spread"] == 0.75
    assert cfg["swap_symbol_spread_overrides_json"] == '{"XAUUSD":0.8}'
