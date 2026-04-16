from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_optimizer_runs import router


class StubOptimizerService:
    def __init__(self) -> None:
        self._runs = [
            {
                "id": "run-1",
                "strategy_id": "liq_sd_v1",
                "strategy_version": "1",
                "status": "running",
                "mode": "bayesian",
                "workers": 2,
                "pairs": ["EURUSD", "GBPUSD"],
                "n_trials": 25,
                "dd_limit": 6.0,
                "dry_run": True,
                "summary": {"total_pairs": 2, "running_pairs": 1, "completed_pairs": 0, "failed_pairs": 0},
            }
        ]

    def start_run(self, **payload: object) -> dict:
        return payload

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict]:
        runs = list(self._runs)
        if status:
            runs = [run for run in runs if run["status"] == status]
        if strategy_id:
            runs = [run for run in runs if run["strategy_id"] == strategy_id]
        if strategy_version:
            runs = [run for run in runs if run["strategy_version"] == strategy_version]
        return runs[:limit]


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr("src.api_optimizer_runs.get_optimizer_run_service", lambda: StubOptimizerService())
    return TestClient(app)


def test_create_optimizer_run_requires_strategy_identity(monkeypatch) -> None:
    response = _client(monkeypatch).post(
        "/api/optimizer/runs",
        json={
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
        },
    )

    assert response.status_code == 422


def test_create_optimizer_run_accepts_strategy_identity(monkeypatch) -> None:
    response = _client(monkeypatch).post(
        "/api/optimizer/runs",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["strategy_id"] == "liq_sd_v1"
    assert response.json()["strategy_version"] == "1"


def test_list_optimizer_runs_filters_by_strategy(monkeypatch) -> None:
    response = _client(monkeypatch).get("/api/optimizer/runs?strategy_id=liq_sd_v1&strategy_version=1")

    assert response.status_code == 200
    body = response.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["strategy_id"] == "liq_sd_v1"
