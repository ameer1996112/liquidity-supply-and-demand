from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from config.settings import get_settings
from src.services.optimizer_run_service import OptimizerRunService


def _disable_admin_auth() -> None:
    import os
    os.environ["ADMIN_API_KEY"] = ""
    get_settings.cache_clear()


from src.api import app  # noqa: E402


class StubOptimizerService:
    def __init__(self) -> None:
        self._run = {
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
            "broker": "vantage",
            "market": "forex",
            "summary": {"total_pairs": 2, "running_pairs": 1, "completed_pairs": 0, "failed_pairs": 0},
            "results": [
                {
                    "symbol": "EURUSD",
                    "status": "completed",
                    "decision": "pass",
                    "reason": "forward window survived current drawdown gate",
                    "metrics": {"score": 2.1},
                    "validation_metrics": {"score": 1.9},
                    "forward_metrics": {"score": 1.7},
                }
            ],
            "artifacts": {
                "trials": [{"symbol": "EURUSD", "trial_number": 1, "window": "validation"}],
                "stress_results": [{"symbol": "EURUSD", "scenario": "spread_125", "status": "pass"}],
                "events": [{"event_type": "pair_completed", "run_id": "run-1", "symbol": "EURUSD"}],
                "summary": {
                    "trial_count": 1,
                    "stress_result_count": 1,
                    "event_count": 1,
                    "symbols": {
                        "EURUSD": {
                            "trial_count": 1,
                            "stress_result_count": 1,
                            "latest_event_type": "pair_completed",
                        }
                    },
                },
            },
        }
        self.portfolio_results: dict[str, dict] = {}
        self.trials: dict[str, list[dict]] = {"run-1": [{"symbol": "EURUSD", "trial_number": 1}]}
        self.stress_results: dict[str, list[dict]] = {"run-1": [{"symbol": "EURUSD", "scenario": "shock"}]}

    def start_run(self, **_: object) -> dict:
        return self._run

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict]:
        if status and self._run["status"] != status:
            return []
        if strategy_id and self._run["strategy_id"] != strategy_id:
            return []
        if strategy_version and self._run["strategy_version"] != strategy_version:
            return []
        return [self._run][:limit]

    def get_run(self, run_id: str) -> dict:
        if run_id != "run-1":
            raise KeyError(run_id)
        portfolio_result = self.portfolio_results.get(run_id)
        if portfolio_result is not None:
            self._run["portfolio_result"] = portfolio_result
        return self._run

    def list_results(self, run_id: str) -> list[dict]:
        if run_id != "run-1":
            raise KeyError(run_id)
        return [{"symbol": "EURUSD", "status": "completed", "metrics": {"score": 2.1}}]

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict]:
        if run_id != "run-1":
            raise KeyError(run_id)
        trials = self.trials.get(run_id, [])
        if symbol is None:
            return trials
        return [trial for trial in trials if trial.get("symbol") == symbol]

    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict]:
        if run_id != "run-1":
            raise KeyError(run_id)
        results = self.stress_results.get(run_id, [])
        if symbol is None:
            return results
        return [result for result in results if result.get("symbol") == symbol]

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict]:
        if run_id != "run-1":
            raise KeyError(run_id)
        return [{"event_type": "pair_completed", "run_id": run_id, "symbol": "EURUSD"}][:limit]

    def cancel_run(self, run_id: str) -> dict:
        if run_id != "run-1":
            raise KeyError(run_id)
        self._run["status"] = "cancelled"
        return self._run


class MissingArtifactTableError(RuntimeError):
    def __init__(self, table_name: str) -> None:
        super().__init__(f"Could not find the table '{table_name}' in the schema cache")
        self.code = "PGRST205"


class MissingOptionalArtifactsStore:
    def __init__(self) -> None:
        self.run = {
            "id": "run-1",
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "status": "completed",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
            "broker": "vantage",
            "market": "forex",
            "summary": {"total_pairs": 1, "running_pairs": 0, "completed_pairs": 1, "failed_pairs": 0},
        }

    def get_run(self, run_id: str) -> dict | None:
        if run_id != "run-1":
            return None
        return self.run

    def list_results(self, run_id: str) -> list[dict]:
        if run_id != "run-1":
            return []
        return [{"run_id": run_id, "symbol": "EURUSD", "status": "completed", "metrics": {"score": 2.1}}]

    def get_portfolio_result(self, run_id: str) -> dict | None:
        raise MissingArtifactTableError("public.optimizer_portfolio_results")

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict]:
        raise MissingArtifactTableError("public.optimizer_run_trials")

    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict]:
        raise MissingArtifactTableError("public.optimizer_run_stress_tests")

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict]:
        raise MissingArtifactTableError("public.optimizer_run_events")


class NoPrecheckTrialsService:
    def get_run(self, run_id: str) -> dict:
        raise AssertionError(f"route should not prefetch run {run_id}")

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict]:
        return [{"run_id": run_id, "symbol": symbol or "EURUSD", "trial_number": 1}]


class NoPrecheckEventsService:
    def get_run(self, run_id: str) -> dict:
        raise AssertionError(f"route should not prefetch run {run_id}")

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict]:
        return [{"run_id": run_id, "event_type": "pair_completed"}][:limit]


@pytest.fixture
def optimizer_store() -> StubOptimizerService:
    return StubOptimizerService()


@pytest.fixture
def client(optimizer_store: StubOptimizerService) -> TestClient:
    _disable_admin_auth()
    with patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=optimizer_store):
        yield TestClient(app)


@patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=StubOptimizerService())
def test_create_optimizer_run_returns_200(_) -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.post(
        "/api/optimizer/runs",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD", "GBPUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
            "broker": "vantage",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["broker"] == "vantage"


def test_create_optimizer_run_rejects_empty_pairs() -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.post(
        "/api/optimizer/runs",
        json={"mode": "bayesian", "workers": 2, "pairs": [], "n_trials": 25, "dd_limit": 6.0, "dry_run": True, "broker": "vantage"},
    )
    assert response.status_code == 422


@patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=StubOptimizerService())
def test_create_optimizer_run_accepts_all_pairs_token(_) -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.post(
        "/api/optimizer/runs",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["ALL"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
            "broker": "vantage",
        },
    )
    assert response.status_code == 200


def test_create_optimizer_run_rejects_unsupported_broker() -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.post(
        "/api/optimizer/runs",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["ALL"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
            "broker": "bad-broker",
        },
    )
    assert response.status_code == 422


@patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=StubOptimizerService())
def test_get_optimizer_run_results_returns_payload(_) -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.get("/api/optimizer/runs/run-1/results")
    assert response.status_code == 200
    assert response.json()["results"][0]["symbol"] == "EURUSD"


def test_get_optimizer_run_returns_portfolio_summary(
    client: TestClient,
    optimizer_store: StubOptimizerService,
) -> None:
    optimizer_store.portfolio_results["run-1"] = {"combined_max_drawdown_pct": 5.9}
    response = client.get("/api/optimizer/runs/run-1")
    assert response.status_code == 200
    assert response.json()["run"]["portfolio_result"]["combined_max_drawdown_pct"] == 5.9


def test_get_optimizer_run_returns_embedded_results_and_artifacts(
    client: TestClient,
) -> None:
    response = client.get("/api/optimizer/runs/run-1")

    assert response.status_code == 200
    payload = response.json()["run"]
    assert payload["results"][0]["decision"] == "pass"
    assert payload["results"][0]["reason"] == "forward window survived current drawdown gate"
    assert payload["artifacts"]["trials"][0]["window"] == "validation"
    assert payload["artifacts"]["stress_results"][0]["scenario"] == "spread_125"
    assert payload["artifacts"]["events"][0]["event_type"] == "pair_completed"
    assert payload["artifacts"]["summary"]["symbols"]["EURUSD"]["trial_count"] == 1


def test_get_optimizer_run_stress_results(client: TestClient) -> None:
    response = client.get("/api/optimizer/runs/run-1/stress-results")
    assert response.status_code == 200
    assert "results" in response.json()


def test_get_optimizer_run_trials_degrades_gracefully_when_artifact_tables_are_missing() -> None:
    _disable_admin_auth()
    service = OptimizerRunService(
        MissingOptionalArtifactsStore(),
        project_root=Path("/tmp"),
        results_dir=Path("/tmp/results"),
    )
    with patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=service):
        client = TestClient(app)
        response = client.get("/api/optimizer/runs/run-1/trials")

    assert response.status_code == 200
    assert response.json() == {"trials": []}


def test_get_optimizer_run_stress_results_degrades_gracefully_when_artifact_tables_are_missing() -> None:
    _disable_admin_auth()
    service = OptimizerRunService(
        MissingOptionalArtifactsStore(),
        project_root=Path("/tmp"),
        results_dir=Path("/tmp/results"),
    )
    with patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=service):
        client = TestClient(app)
        response = client.get("/api/optimizer/runs/run-1/stress-results")

    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_get_optimizer_run_events_degrades_gracefully_when_artifact_tables_are_missing() -> None:
    _disable_admin_auth()
    service = OptimizerRunService(
        MissingOptionalArtifactsStore(),
        project_root=Path("/tmp"),
        results_dir=Path("/tmp/results"),
    )
    with patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=service):
        client = TestClient(app)
        response = client.get("/api/optimizer/runs/run-1/events")

    assert response.status_code == 200
    assert response.json() == {"events": []}


def test_get_optimizer_run_trials_does_not_prefetch_full_run() -> None:
    _disable_admin_auth()
    with patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=NoPrecheckTrialsService()):
        client = TestClient(app)
        response = client.get("/api/optimizer/runs/run-1/trials?symbol=EURAUD")

    assert response.status_code == 200
    assert response.json() == {"trials": [{"run_id": "run-1", "symbol": "EURAUD", "trial_number": 1}]}


def test_get_optimizer_run_events_does_not_prefetch_full_run() -> None:
    _disable_admin_auth()
    with patch("src.api_optimizer_runs.get_optimizer_run_service", return_value=NoPrecheckEventsService()):
        client = TestClient(app)
        response = client.get("/api/optimizer/runs/run-1/events")

    assert response.status_code == 200
    assert response.json() == {"events": [{"run_id": "run-1", "event_type": "pair_completed"}]}
