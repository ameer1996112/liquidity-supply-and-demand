from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api_config as api_config


def test_get_ai_operating_layer_config_returns_defaults(monkeypatch) -> None:
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

    response = client.get("/api/v1/config/ai-operating-layer")
    assert response.status_code == 200
    body = response.json()
    assert body["panic_mode"] is False
    assert body["modules"]["chart_context"] == "inherit"


def test_patch_ai_operating_layer_config_updates_panic_mode_and_modules(monkeypatch) -> None:
    store = {}

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
            if isinstance(payload, list):
                for row in payload:
                    store[row["key"]] = row["value"]
            else:
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
        "/api/v1/config/ai-operating-layer",
        json={
            "panic_mode": True,
            "modules": {
                "chart_context": "enabled",
                "debate_review": "disabled",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["panic_mode"] is True
    assert body["modules"]["chart_context"] == "enabled"
    assert body["modules"]["debate_review"] == "disabled"


def test_patch_ai_operating_layer_config_updates_provider_fields(monkeypatch) -> None:
    store = {}

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
            if isinstance(payload, list):
                for row in payload:
                    store[row["key"]] = row["value"]
            else:
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
        "/api/v1/config/ai-operating-layer",
        json={
            "provider": {
                "enabled": True,
                "base_url": "http://provider.test",
                "timeout_seconds": 1.0,
                "retry_count": 2,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"]["enabled"] is True
    assert body["provider"]["base_url"] == "http://provider.test"
