from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api_ai_runs as api_ai_runs


def test_get_ai_run_by_signal_returns_expanded_fields(monkeypatch) -> None:
    class _Resp:
        def __init__(self, data):
            self.data = data

    class _Query:
        def __init__(self, data):
            self._data = data

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return _Resp(self._data)

    class _Supabase:
        def table(self, name: str):
            if name == "ai_runs":
                return _Query(
                    [
                        {
                            "id": 1,
                            "correlation_id": "corr-1",
                            "signal_id": 12,
                            "run_type": "debate",
                            "analysis_mode": "posttrade_review",
                            "recommendation": "allow",
                            "confidence": 77,
                            "reason_codes": [],
                            "memo": "memo",
                            "votes": {},
                            "transcript": [],
                            "chart_context": {"status": "ok"},
                            "pine_context": {"script_name": "Liquidity Sweeps"},
                            "module_status": {"chart_context": {"status": "ok", "reason": ""}},
                            "layered_output": {"top_level": {"verdict": "good setup"}},
                            "council_report": {},
                            "created_at": "2026-04-16T00:00:00Z",
                        }
                    ]
                )
            return _Query([])

    monkeypatch.setattr(api_ai_runs, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_ai_runs.router)
    client = TestClient(app)

    response = client.get("/api/ai-runs", params={"signal_id": 12})
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_mode"] == "posttrade_review"
    assert body["module_status"]["chart_context"]["status"] in {"ok", "degraded"}
    assert "layered_output" in body
