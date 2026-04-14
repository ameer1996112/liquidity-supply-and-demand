from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from config.settings import get_settings


def _disable_admin_auth() -> None:
    import os

    os.environ["ADMIN_API_KEY"] = ""
    get_settings.cache_clear()


from src.api import app  # noqa: E402


class StubAlertSetupService:
    def __init__(self) -> None:
        self._config = {
            "id": "cfg-1",
            "pair": "EURUSD",
            "timeframe": "5m",
            "status": "approved",
            "params": {"lookback": 20},
            "risk_weight": 0.75,
        }
        self._batch = {
            "id": "batch-1",
            "status": "queued",
            "source_mode": "approved",
            "timeframe": "5m",
            "pairs": ["EURUSD"],
            "approved_config_ids": ["cfg-1"],
            "config_snapshot": [self._config],
            "summary": {"total_pairs": 1, "pending_pairs": 1, "running_pairs": 0, "completed_pairs": 0, "failed_pairs": 0, "cancelled_pairs": 0},
        }

    def list_approved_configs(self, *, limit: int = 100, status: str | None = "approved", pair: str | None = None, timeframe: str | None = None) -> list[dict]:
        return [self._config][:limit]

    def upsert_approved_config(self, **payload: object) -> dict:
        self._config = {"id": "cfg-1", **payload}
        return self._config

    def list_batches(self, *, limit: int = 20, status: str | None = None) -> list[dict]:
        if status and self._batch["status"] != status:
            return []
        return [self._batch][:limit]

    def start_batch(self, **payload: object) -> dict:
        self._batch = {
            **self._batch,
            "pairs": payload["pairs"],
            "timeframe": payload["timeframe"],
            "source_mode": payload["source_mode"],
        }
        return self._batch

    def get_batch(self, batch_id: str) -> dict:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        return self._batch

    def list_results(self, batch_id: str) -> list[dict]:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        return [{"batch_id": batch_id, "pair": "EURUSD", "timeframe": "5m", "status": "pending", "params": {"lookback": 20}}]

    def list_events(self, batch_id: str, *, limit: int = 200) -> list[dict]:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        return [{"batch_id": batch_id, "event_type": "batch_started", "pair": None}][:limit]

    def cancel_batch(self, batch_id: str) -> dict:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        self._batch["status"] = "cancelled"
        return self._batch

    def update_batch_from_agent(self, batch_id: str, *, status: str | None = None, summary: dict | None = None) -> dict:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        if status:
            self._batch["status"] = status
        if summary:
            self._batch["summary"] = {**self._batch["summary"], **summary}
        return self._batch

    def update_result_from_agent(self, batch_id: str, pair: str, updates: dict) -> dict:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        return {"batch_id": batch_id, "pair": pair, **updates}

    def push_event(self, batch_id: str, event: dict) -> dict:
        if batch_id != "batch-1":
            raise KeyError(batch_id)
        return {"batch_id": batch_id, **event}


@patch("src.api_alert_setup.get_alert_setup_service", return_value=StubAlertSetupService())
def test_create_approved_config_and_list_configs(_) -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.post(
        "/api/alert-setup/approved-configs",
        json={
            "pair": "EURUSD",
            "timeframe": "5m",
            "params": {"lookback": 20},
            "risk_weight": 0.75,
            "status": "approved",
        },
    )
    assert response.status_code == 200
    listed = client.get("/api/alert-setup/approved-configs")
    assert listed.status_code == 200
    assert listed.json()["configs"][0]["pair"] == "EURUSD"


@patch("src.api_alert_setup.get_alert_setup_service", return_value=StubAlertSetupService())
def test_create_batch_and_fetch_results(_) -> None:
    _disable_admin_auth()
    client = TestClient(app)
    response = client.post(
        "/api/alert-setup/batches",
        json={
            "source_mode": "approved",
            "timeframe": "5m",
            "pairs": ["EURUSD"],
            "created_by": "operator",
            "notes": "batch-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    results = client.get("/api/alert-setup/batches/batch-1/results")
    assert results.status_code == 200
    assert results.json()["results"][0]["pair"] == "EURUSD"
