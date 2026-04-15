from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.optimizer_run_service import OptimizerRunService
from src.services import optimizer_run_service as optimizer_service_module


@dataclass
class DummyProcess:
    pid: int
    terminated: bool = False

    def terminate(self) -> None:
        self.terminated = True


class InMemoryOptimizerStore:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.results: dict[tuple[str, str], dict] = {}
        self.events: list[dict] = []
        self.rule_suggestions: list[dict] = []

    @classmethod
    def with_running_run(cls) -> "InMemoryOptimizerStore":
        store = cls()
        store.create_run(
            {
                "id": "run-1",
                "status": "running",
                "mode": "bayesian",
                "workers": 2,
                "pairs": ["EURUSD"],
                "n_trials": 25,
                "dd_limit": 6.0,
                "dry_run": True,
                "summary": {"total_pairs": 1, "running_pairs": 1, "completed_pairs": 0, "failed_pairs": 0},
            }
        )
        store.create_results("run-1", ["EURUSD"])
        store.update_result("run-1", "EURUSD", {"status": "running"})
        return store

    @classmethod
    def with_run_and_pending_symbol(cls, run_id: str, symbol: str) -> "InMemoryOptimizerStore":
        store = cls()
        store.create_run(
            {
                "id": run_id,
                "status": "running",
                "mode": "bayesian",
                "workers": 2,
                "pairs": [symbol],
                "n_trials": 25,
                "dd_limit": 6.0,
                "dry_run": True,
                "summary": {"total_pairs": 1, "running_pairs": 0, "completed_pairs": 0, "failed_pairs": 0},
            }
        )
        store.create_results(run_id, [symbol])
        return store

    def create_run(self, payload: dict) -> dict:
        self.runs[payload["id"]] = payload.copy()
        return self.runs[payload["id"]]

    def update_run(self, run_id: str, updates: dict) -> dict:
        self.runs[run_id].update(updates)
        return self.runs[run_id]

    def get_run(self, run_id: str) -> dict | None:
        return self.runs.get(run_id)

    def list_runs(self, *, limit: int = 20, status: str | None = None) -> list[dict]:
        runs = list(self.runs.values())
        if status:
            runs = [run for run in runs if run["status"] == status]
        return runs[:limit]

    def list_incomplete_runs(self) -> list[dict]:
        return [run for run in self.runs.values() if run["status"] in {"queued", "running"}]

    def create_results(self, run_id: str, symbols: list[str]) -> None:
        for symbol in symbols:
            self.results[(run_id, symbol)] = {
                "run_id": run_id,
                "symbol": symbol,
                "status": "pending",
                "params": {},
                "metrics": {},
            }

    def update_result(self, run_id: str, symbol: str, updates: dict) -> dict:
        self.results[(run_id, symbol)].update(updates)
        return self.results[(run_id, symbol)]

    def list_results(self, run_id: str) -> list[dict]:
        return [value for (current_run_id, _), value in self.results.items() if current_run_id == run_id]

    def append_event(self, payload: dict) -> dict:
        self.events.append(payload)
        return payload

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict]:
        return [event for event in self.events if event["run_id"] == run_id][:limit]

    def create_rule_suggestion(self, payload: dict) -> dict:
        self.rule_suggestions.append(payload.copy())
        return self.rule_suggestions[-1]

    def supersede_rule_suggestions(self, symbol: str) -> None:
        for row in self.rule_suggestions:
            if row["symbol"] == symbol.upper().strip() and row["status"] == "pending":
                row["status"] = "superseded"


def test_start_run_persists_run_and_symbol_rows(monkeypatch) -> None:
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda **_: DummyProcess(pid=321))
    monkeypatch.setattr(service, "_stream_process_output", lambda run_id, process: None)

    run = service.start_run(
        mode="bayesian",
        workers=2,
        pairs=["EURUSD", "GBPUSD"],
        n_trials=25,
        dd_limit=6.0,
        dry_run=True,
        created_by="test-user",
    )

    assert run["status"] == "queued"
    assert store.runs[run["id"]]["workers"] == 2
    assert store.results[(run["id"], "EURUSD")]["status"] == "pending"


def test_start_run_expands_all_pairs_without_scripts_import(monkeypatch) -> None:
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda **_: DummyProcess(pid=321))
    monkeypatch.setattr(service, "_stream_process_output", lambda run_id, process: None)
    monkeypatch.setattr(optimizer_service_module, "DEFAULT_PAIRS", ["EURUSD", "GBPUSD"], raising=False)

    run = service.start_run(
        mode="bayesian",
        workers=2,
        pairs=["ALL"],
        n_trials=25,
        dd_limit=6.0,
        dry_run=True,
        created_by="test-user",
    )

    assert run["pairs"] == ["EURUSD", "GBPUSD"]
    assert store.results[(run["id"], "EURUSD")]["status"] == "pending"
    assert store.results[(run["id"], "GBPUSD")]["status"] == "pending"


def test_cancel_run_terminates_process_and_marks_cancelled() -> None:
    store = InMemoryOptimizerStore.with_running_run()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))
    process = DummyProcess(pid=321)
    service._processes["run-1"] = type("Managed", (), {"process": process, "reader": None})()

    run = service.cancel_run("run-1")

    assert process.terminated is True
    assert run["status"] == "cancelled"
    assert store.results[("run-1", "EURUSD")]["status"] == "cancelled"


def test_ingest_pair_completed_event_updates_summary_and_result() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    service.ingest_event(
        {
            "event_type": "pair_completed",
            "run_id": "run-1",
            "worker_id": 0,
            "symbol": "EURUSD",
            "metrics": {
                "score": 2.1,
                "net_profit": 250.0,
                "win_rate": 61.0,
                "risk_percent": 0.4,
                "max_lot_size": 1.5,
                "pip_size": 0.0001,
                "pip_value_per_lot": 10.0,
            },
            "params": {"lookback": 20},
        }
    )

    result = store.results[("run-1", "EURUSD")]
    assert result["status"] == "completed"
    assert result["metrics"]["score"] == 2.1
    assert store.runs["run-1"]["summary"]["completed_pairs"] == 1
    assert store.runs["run-1"]["summary"]["best_symbol"] == "EURUSD"
    assert store.rule_suggestions[0]["symbol"] == "EURUSD"
    assert store.rule_suggestions[0]["suggested_risk_percent"] == 0.4
    assert store.rule_suggestions[0]["status"] == "pending"


def test_ingest_pair_completed_event_supersedes_older_pending_suggestion() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    store.rule_suggestions.append(
        {
            "symbol": "EURUSD",
            "optimizer_run_id": "old-run",
            "suggested_risk_percent": 0.6,
            "suggested_max_lot_size": 2.0,
            "suggested_pip_size": 0.0001,
            "suggested_pip_value_per_lot": 10.0,
            "status": "pending",
        }
    )
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    service.ingest_event(
        {
            "event_type": "pair_completed",
            "run_id": "run-1",
            "worker_id": 0,
            "symbol": "EURUSD",
            "metrics": {
                "score": 2.4,
                "risk_percent": 0.3,
                "max_lot_size": 1.0,
                "pip_size": 0.0001,
                "pip_value_per_lot": 10.0,
            },
            "params": {},
        }
    )

    assert store.rule_suggestions[0]["status"] == "superseded"
    assert store.rule_suggestions[-1]["status"] == "pending"
    assert store.rule_suggestions[-1]["optimizer_run_id"] == "run-1"


def test_reconcile_incomplete_runs_marks_orphans_interrupted() -> None:
    store = InMemoryOptimizerStore.with_running_run()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    service.reconcile_incomplete_runs()

    assert store.runs["run-1"]["status"] == "interrupted"
