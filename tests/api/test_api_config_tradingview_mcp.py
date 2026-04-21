from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api_config as api_config


def test_get_tradingview_mcp_config_returns_empty_defaults(monkeypatch) -> None:
    class _Resp:
        def __init__(self, data):
            self.data = data

    class _Query:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, *_args, **_kwargs):
            return self

        def execute(self):
            return _Resp([])

    class _Supabase:
        def table(self, _name: str):
            return _Query()

    monkeypatch.setattr(api_config, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.get("/api/v1/config/tradingview-mcp")

    assert response.status_code == 200
    assert response.json() == {"approved_versions": []}


def test_patch_tradingview_mcp_config_normalizes_and_deduplicates(monkeypatch) -> None:
    store: dict[str, str] = {}

    class _Resp:
        def __init__(self, data):
            self.data = data

    class _SelectQuery:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, _field: str, keys):
            self._keys = keys
            return self

        def execute(self):
            rows = [{"key": key, "value": value} for key, value in store.items() if key in self._keys]
            return _Resp(rows)

    class _UpsertQuery:
        def upsert(self, payload, **_kwargs):
            store[payload["key"]] = payload["value"]
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

    monkeypatch.setattr(api_config, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/config/tradingview-mcp",
        json={"approved_versions": [" 2.9.0 ", "2.9.0", "2.9.1", "   "]},
    )

    assert response.status_code == 200
    assert response.json() == {"approved_versions": ["2.9.0", "2.9.1"]}
    assert store["local_chart_tradingview_allowed_versions"] == '["2.9.0", "2.9.1"]'


def test_patch_tradingview_mcp_config_allows_clearing_versions(monkeypatch) -> None:
    store = {"local_chart_tradingview_allowed_versions": '["2.9.0"]'}

    class _Resp:
        def __init__(self, data):
            self.data = data

    class _SelectQuery:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, _field: str, keys):
            self._keys = keys
            return self

        def execute(self):
            rows = [{"key": key, "value": value} for key, value in store.items() if key in self._keys]
            return _Resp(rows)

    class _UpsertQuery:
        def upsert(self, payload, **_kwargs):
            store[payload["key"]] = payload["value"]
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

    monkeypatch.setattr(api_config, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/config/tradingview-mcp",
        json={"approved_versions": []},
    )

    assert response.status_code == 200
    assert response.json() == {"approved_versions": []}
    assert store["local_chart_tradingview_allowed_versions"] == "[]"
