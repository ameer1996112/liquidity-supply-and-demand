from __future__ import annotations

import json
from pathlib import Path

import src.services.alert_setup_service as alert_setup_service
from src.services.alert_setup_service import AlertSetupService


class InMemoryAlertSetupStore:
    def __init__(self) -> None:
        self.configs: dict[tuple[str, str], dict] = {}
        self.batches: dict[str, dict] = {}
        self.results: dict[tuple[str, str, str], dict] = {}
        self.events: list[dict] = []

    def upsert_config(self, payload: dict) -> dict:
        key = (payload["pair"], payload["timeframe"])
        existing = self.configs.get(key, {})
        merged = {**existing, **payload}
        merged.setdefault("id", f"{payload['pair']}-{payload['timeframe']}")
        self.configs[key] = merged
        return merged

    def get_config(self, pair: str, timeframe: str) -> dict | None:
        return self.configs.get((pair, timeframe))

    def list_configs(self, *, limit: int = 100, status: str | None = None, pair: str | None = None, timeframe: str | None = None) -> list[dict]:
        rows = list(self.configs.values())
        if status:
            rows = [row for row in rows if row["status"] == status]
        if pair:
            rows = [row for row in rows if row["pair"] == pair]
        if timeframe:
            rows = [row for row in rows if row["timeframe"] == timeframe]
        return rows[:limit]

    def create_batch(self, payload: dict) -> dict:
        self.batches[payload["id"]] = payload.copy()
        return self.batches[payload["id"]]

    def get_batch(self, batch_id: str) -> dict | None:
        return self.batches.get(batch_id)

    def update_batch(self, batch_id: str, updates: dict) -> dict:
        self.batches[batch_id].update(updates)
        return self.batches[batch_id]

    def list_batches(self, *, limit: int = 20, status: str | None = None) -> list[dict]:
        rows = list(self.batches.values())
        if status:
            rows = [row for row in rows if row["status"] == status]
        return rows[:limit]

    def create_results(self, batch_id: str, rows: list[dict]) -> None:
        for row in rows:
            self.results[(batch_id, row["pair"], row["timeframe"])] = row.copy()

    def update_result(self, batch_id: str, pair: str, timeframe: str, updates: dict) -> dict:
        row = self.results[(batch_id, pair, timeframe)]
        row.update(updates)
        return row

    def list_results(self, batch_id: str) -> list[dict]:
        return [row for (current_batch_id, _, _), row in self.results.items() if current_batch_id == batch_id]

    def append_event(self, payload: dict) -> dict:
        self.events.append(payload)
        return payload

    def list_events(self, batch_id: str, *, limit: int = 200) -> list[dict]:
        return [event for event in self.events if event["batch_id"] == batch_id][:limit]


def _make_service() -> tuple[AlertSetupService, InMemoryAlertSetupStore]:
    store = InMemoryAlertSetupStore()
    service = AlertSetupService(store)
    return service, store


def test_upsert_approved_config_updates_existing_row() -> None:
    service, store = _make_service()

    first = service.upsert_approved_config(
        pair="eurusd",
        timeframe="5m",
        params={"lookback": 20},
        risk_weight=0.75,
        source_score=12.5,
        status="approved",
    )
    second = service.upsert_approved_config(
        pair="EURUSD",
        timeframe="5m",
        params={"lookback": 30},
        risk_weight=0.5,
        source_score=18.0,
        status="approved",
    )

    assert first["pair"] == "EURUSD"
    assert second["params"]["lookback"] == 30
    assert service.list_approved_configs() == [second]
    assert store.configs[("EURUSD", "5m")]["risk_weight"] == 0.5


def test_start_batch_persists_results_and_summary() -> None:
    service, store = _make_service()
    service.upsert_approved_config(
        pair="EURUSD",
        timeframe="5m",
        params={"lookback": 20},
        risk_weight=0.75,
        source_score=14.0,
        status="approved",
    )
    service.upsert_approved_config(
        pair="GBPUSD",
        timeframe="5m",
        params={"lookback": 30},
        risk_weight=0.5,
        source_score=18.0,
        status="approved",
    )

    batch = service.start_batch(
        source_mode="approved",
        pairs=["EURUSD", "GBPUSD"],
        timeframe="5m",
        created_by="operator",
        notes="batch-1",
    )

    assert batch["status"] == "queued"
    assert batch["summary"]["total_pairs"] == 2
    assert batch["summary"]["pending_pairs"] == 2
    assert batch["summary"]["best_pair"] == "GBPUSD"
    assert store.results[(batch["id"], "EURUSD", "5m")]["status"] == "pending"
    assert store.events[0]["event_type"] == "batch_started"


def test_cancel_batch_marks_pending_results_cancelled() -> None:
    service, _store = _make_service()
    service.upsert_approved_config(
        pair="EURUSD",
        timeframe="5m",
        params={"lookback": 20},
        risk_weight=0.75,
        source_score=14.0,
        status="approved",
    )
    batch = service.start_batch(
        source_mode="approved",
        pairs=["EURUSD"],
        timeframe="5m",
        created_by="operator",
    )

    cancelled = service.cancel_batch(batch["id"])

    assert cancelled["status"] == "cancelled"
    assert service.list_results(batch["id"])[0]["status"] == "cancelled"


def test_start_batch_custom_imports_selected_pairs_from_parallel_results(tmp_path: Path, monkeypatch) -> None:
    service, store = _make_service()
    service.upsert_approved_config(
        pair="USDJPY",
        timeframe="5m",
        params={"max_zones": 99},
        risk_weight=0.75,
        source_score=10.0,
        status="approved",
    )

    results_file = tmp_path / "parallel_results.json"
    results_file.write_text(
        json.dumps(
            {
                "USDJPY": {
                    "params": {"max_zones": 13, "rr_mode": "fixed_2.5"},
                    "score": 24.62,
                    "net_profit": 18507.84,
                    "win_rate": 40.54,
                    "profit_factor": 1.391,
                    "max_drawdown_pct": 4.06,
                    "total_trades": 370,
                    "worker_id": 1,
                    "timestamp": "2026-04-14T12:54:33.523947",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(alert_setup_service, "_PARALLEL_RESULTS_FILE", results_file)

    batch = service.start_batch(
        source_mode="custom",
        pairs=["USDJPY"],
        timeframe="5m",
        created_by="operator",
    )

    assert batch["status"] == "queued"
    assert batch["config_snapshot"][0]["params"]["max_zones"] == 13
    assert batch["config_snapshot"][0]["source_metrics"]["profit_factor"] == 1.391
    assert store.configs[("USDJPY", "5m")]["params"]["max_zones"] == 13
    assert store.results[(batch["id"], "USDJPY", "5m")]["params"]["max_zones"] == 13
