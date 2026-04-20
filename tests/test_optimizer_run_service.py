from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.optimizer.parallel_runner import results_file_for_broker
from src.services.optimizer_run_service import (
    OptimizerRunService,
    SupabaseOptimizerRunRepository,
    _normalize_portfolio_result,
)
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
        self.trials: list[dict] = []
        self.stress_results: list[dict] = []
        self.portfolio_results: dict[str, dict] = {}

    @classmethod
    def with_running_run(cls) -> "InMemoryOptimizerStore":
        store = cls()
        store.create_run(
            {
                "id": "run-1",
                "strategy_id": "liq_sd_v1",
                "strategy_version": "1",
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
                "strategy_id": "liq_sd_v1",
                "strategy_version": "1",
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

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict]:
        runs = list(self.runs.values())
        if status:
            runs = [run for run in runs if run["status"] == status]
        if strategy_id:
            runs = [run for run in runs if run.get("strategy_id") == strategy_id]
        if strategy_version:
            runs = [run for run in runs if str(run.get("strategy_version")) == str(strategy_version)]
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

    def create_trial(self, run_id: str, symbol: str, payload: dict) -> dict:
        row = {"run_id": run_id, "symbol": symbol, **payload}
        self.trials.append(row)
        return row

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict]:
        return [
            row
            for row in self.trials
            if row["run_id"] == run_id and (symbol is None or row["symbol"] == symbol)
        ]

    def create_stress_result(self, run_id: str, symbol: str, payload: dict) -> dict:
        row = {"run_id": run_id, "symbol": symbol, **payload}
        self.stress_results.append(row)
        return row

    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict]:
        return [
            row
            for row in self.stress_results
            if row["run_id"] == run_id and (symbol is None or row["symbol"] == symbol)
        ]

    def upsert_portfolio_result(self, run_id: str, payload: dict) -> dict:
        row = {"run_id": run_id, **payload}
        self.portfolio_results[run_id] = row
        return row

    def get_portfolio_result(self, run_id: str) -> dict | None:
        return self.portfolio_results.get(run_id)

    def append_event(self, payload: dict) -> dict:
        self.events.append(payload)
        return payload

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict]:
        events = [event for event in self.events if event["run_id"] == run_id]
        return events[-limit:]


class MissingArtifactTableError(RuntimeError):
    def __init__(self, table_name: str) -> None:
        super().__init__(f"Could not find the table '{table_name}' in the schema cache")
        self.code = "PGRST205"


class MissingOptionalArtifactsStore(InMemoryOptimizerStore):
    def get_portfolio_result(self, run_id: str) -> dict | None:
        raise MissingArtifactTableError("public.optimizer_portfolio_results")

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict]:
        raise MissingArtifactTableError("public.optimizer_run_trials")

    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict]:
        raise MissingArtifactTableError("public.optimizer_run_stress_tests")

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict]:
        raise MissingArtifactTableError("public.optimizer_run_events")


class FakeQuery:
    def __init__(self, response: object = None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def order(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def limit(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def eq(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def execute(self):
        if self._exc is not None:
            raise self._exc
        return self._response


class FakeSupabaseClient:
    def __init__(self, query: FakeQuery) -> None:
        self._query = query

    def table(self, _name: str) -> FakeQuery:
        return self._query


class RemoteProtocolLikeError(RuntimeError):
    pass


def test_start_run_persists_run_and_symbol_rows(monkeypatch) -> None:
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda **_: DummyProcess(pid=321))
    monkeypatch.setattr(service, "_stream_process_output", lambda run_id, process: None)

    run = service.start_run(
        strategy_id="liq_sd_v1",
        strategy_version="1",
        mode="bayesian",
        workers=2,
        pairs=["EURUSD", "GBPUSD"],
        n_trials=25,
        dd_limit=6.0,
        dry_run=True,
        broker="vantage",
        created_by="test-user",
    )

    assert run["status"] == "queued"
    assert run["strategy_id"] == "liq_sd_v1"
    assert run["strategy_version"] == "1"
    assert run["broker"] == "vantage"
    assert run["market"] == "forex"
    assert store.runs[run["id"]]["workers"] == 2
    assert store.results[(run["id"], "EURUSD")]["status"] == "pending"


def test_start_run_expands_all_pairs_without_scripts_import(monkeypatch) -> None:
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda **_: DummyProcess(pid=321))
    monkeypatch.setattr(service, "_stream_process_output", lambda run_id, process: None)
    monkeypatch.setattr(optimizer_service_module, "DEFAULT_PAIRS", ["EURUSD", "GBPUSD"], raising=False)

    run = service.start_run(
        strategy_id="liq_sd_v1",
        strategy_version="1",
        mode="bayesian",
        workers=2,
        pairs=["ALL"],
        n_trials=25,
        dd_limit=6.0,
        dry_run=True,
        broker="vantage",
        created_by="test-user",
    )

    assert run["pairs"] == ["EURUSD", "GBPUSD"]
    assert store.results[(run["id"], "EURUSD")]["status"] == "pending"
    assert store.results[(run["id"], "GBPUSD")]["status"] == "pending"


def test_start_run_requires_strategy_identity(monkeypatch) -> None:
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda **_: DummyProcess(pid=321))
    monkeypatch.setattr(service, "_stream_process_output", lambda run_id, process: None)

    try:
        service.start_run(
            strategy_id="",
            strategy_version="1",
            mode="bayesian",
            workers=2,
            pairs=["EURUSD"],
            n_trials=25,
            dd_limit=6.0,
            dry_run=True,
            broker="vantage",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "strategy_id" in str(exc)


def test_start_run_rejects_unknown_broker(monkeypatch) -> None:
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda **_: DummyProcess(pid=321))
    monkeypatch.setattr(service, "_stream_process_output", lambda run_id, process: None)

    try:
        service.start_run(
            strategy_id="liq_sd_v1",
            strategy_version="1",
            mode="bayesian",
            workers=2,
            pairs=["EURUSD"],
            n_trials=25,
            dd_limit=6.0,
            dry_run=True,
            broker="bad-broker",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "invalid broker" in str(exc)


def test_service_exposes_survival_artifacts(monkeypatch) -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    service.record_trial(
        "run-1",
        "EURUSD",
        {"trial_number": 3, "window": "forward", "params": {}, "metrics": {"net_profit": 200.0}},
    )
    service.record_stress_result(
        "run-1",
        "EURUSD",
        {"stress_type": "news_blackout_30m", "status": "passed", "metrics": {"profit_factor": 1.2}},
    )
    service.update_portfolio_result(
        "run-1",
        {"combined_max_drawdown_pct": 5.2, "weights": {"EURUSD": 1.0}},
    )

    assert service.list_trials("run-1", "EURUSD")[0]["window"] == "forward"
    assert service.list_stress_results("run-1", "EURUSD")[0]["status"] == "passed"
    assert service.get_portfolio_result("run-1")["weights"]["EURUSD"] == 1.0
    assert service.get_run("run-1")["portfolio_result"]["weights"]["EURUSD"] == 1.0


def test_survival_artifacts_get_run_returns_detached_payload() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    store.update_run("run-1", {"status": "completed"})
    store.update_result(
        "run-1",
        "EURUSD",
        {
            "status": "completed",
            "metrics": {"score": 2.1},
            "validation_metrics": {"score": 1.7},
            "forward_metrics": {"score": 1.5},
        },
    )
    store.create_trial(
        "run-1",
        "EURUSD",
        {"trial_number": 3, "window": "forward", "metrics": {"score": 1.5}},
    )
    store.create_stress_result(
        "run-1",
        "EURUSD",
        {"scenario": "spread_125", "status": "pass", "metrics": {"profit_factor": 1.2}},
    )
    store.append_event(
        {"run_id": "run-1", "event_type": "pair_completed", "symbol": "EURUSD", "payload": {"message": "done"}}
    )
    store.upsert_portfolio_result(
        "run-1",
        {"combined_max_drawdown_pct": 5.2, "weights": {"EURUSD": 1.0}},
    )
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    run = service.get_run("run-1")
    run["pairs"].append("GBPUSD")
    run["summary"]["completed_pairs"] = 99
    run["portfolio_result"]["weights"]["EURUSD"] = 0.5
    run["results"][0]["metrics"]["score"] = 9.9
    run["artifacts"]["trials"][0]["metrics"]["score"] = 7.7
    run["artifacts"]["stress_results"][0]["metrics"]["profit_factor"] = 0.8
    run["artifacts"]["events"][0]["payload"]["message"] = "mutated"

    assert store.runs["run-1"]["pairs"] == ["EURUSD"]
    assert store.runs["run-1"]["summary"]["completed_pairs"] == 0
    assert store.portfolio_results["run-1"]["weights"]["EURUSD"] == 1.0
    assert store.results[("run-1", "EURUSD")]["metrics"]["score"] == 2.1
    assert store.trials[0]["metrics"]["score"] == 1.5
    assert store.stress_results[0]["metrics"]["profit_factor"] == 1.2
    assert store.events[0]["payload"]["message"] == "done"


def test_get_run_includes_embedded_results_and_artifact_collections() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    store.update_run("run-1", {"status": "completed"})
    store.update_result(
        "run-1",
        "EURUSD",
        {
            "status": "completed",
            "metrics": {"score": 2.1},
            "decision": "reduce_risk",
            "reason": "forward window survived but DD was close to cap",
        },
    )
    store.create_trial(
        "run-1",
        "EURUSD",
        {"trial_number": 1, "window": "validation", "metrics": {"score": 1.8}},
    )
    store.create_stress_result(
        "run-1",
        "EURUSD",
        {"scenario": "spread_125", "status": "pass", "metrics": {"profit_factor": 1.15}},
    )
    store.append_event(
        {"run_id": "run-1", "event_type": "pair_completed", "symbol": "EURUSD", "payload": {"message": "saved"}}
    )
    store.upsert_portfolio_result(
        "run-1",
        {"combined_max_drawdown_pct": 5.2, "weights": {"EURUSD": 0.5}},
    )
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    run = service.get_run("run-1")

    assert run["results"][0]["decision"] == "reduce_risk"
    assert run["results"][0]["reason"] == "forward window survived but DD was close to cap"
    assert run["artifacts"]["trials"][0]["window"] == "validation"
    assert run["artifacts"]["stress_results"][0]["scenario"] == "spread_125"
    assert run["artifacts"]["events"][0]["event_type"] == "pair_completed"
    assert run["artifacts"]["summary"] == {
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
    }


def test_get_run_embeds_latest_event_window_for_busy_runs() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    store.update_run("run-1", {"status": "completed"})
    for index in range(205):
        store.append_event(
            {
                "run_id": "run-1",
                "event_type": f"event_{index}",
                "symbol": "EURUSD",
                "payload": {"index": index},
            }
        )
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    run = service.get_run("run-1")

    assert len(run["artifacts"]["events"]) == 200
    assert run["artifacts"]["events"][0]["event_type"] == "event_5"
    assert run["artifacts"]["events"][-1]["event_type"] == "event_204"
    assert run["artifacts"]["summary"]["symbols"]["EURUSD"]["latest_event_type"] == "event_204"


def test_get_run_keeps_active_runs_lightweight() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    store.update_result("run-1", "EURUSD", {"status": "running", "metrics": {"score": 1.2}})
    store.create_trial("run-1", "EURUSD", {"trial_number": 1, "window": "validation", "metrics": {"score": 1.1}})
    store.create_stress_result("run-1", "EURUSD", {"scenario": "spread_125", "status": "pass"})
    store.append_event({"run_id": "run-1", "event_type": "pair_started", "symbol": "EURUSD", "payload": {}})
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    run = service.get_run("run-1")

    assert "results" not in run
    assert "artifacts" not in run


def test_get_run_degrades_gracefully_when_optional_artifact_tables_are_missing() -> None:
    store = MissingOptionalArtifactsStore.with_run_and_pending_symbol("run-1", "EURUSD")
    store.update_run("run-1", {"status": "completed"})
    store.update_result("run-1", "EURUSD", {"status": "completed", "metrics": {"score": 1.2}})
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    run = service.get_run("run-1")

    assert run["portfolio_result"] is None
    assert run["results"][0]["metrics"]["score"] == 1.2
    assert run["artifacts"]["trials"] == []
    assert run["artifacts"]["stress_results"] == []
    assert run["artifacts"]["events"] == []
    assert run["artifacts"]["summary"] == {
        "trial_count": 0,
        "stress_result_count": 0,
        "event_count": 0,
        "symbols": {},
    }


def test_list_trials_degrades_gracefully_when_optional_artifact_tables_are_missing() -> None:
    store = MissingOptionalArtifactsStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    assert service.list_trials("run-1") == []


def test_list_stress_results_degrades_gracefully_when_optional_artifact_tables_are_missing() -> None:
    store = MissingOptionalArtifactsStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    assert service.list_stress_results("run-1") == []


def test_list_events_degrades_gracefully_when_optional_artifact_tables_are_missing() -> None:
    store = MissingOptionalArtifactsStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    assert service.list_events("run-1") == []


def test_get_portfolio_result_degrades_gracefully_when_optional_artifact_tables_are_missing() -> None:
    store = MissingOptionalArtifactsStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    assert service.get_portfolio_result("run-1") is None


def test_optional_artifact_warning_is_logged_once_per_artifact_type(caplog) -> None:
    store = MissingOptionalArtifactsStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    optimizer_service_module._LOGGED_OPTIONAL_ARTIFACT_WARNINGS.clear()
    caplog.set_level("WARNING", logger="src.services.optimizer_run_service")

    assert service.list_trials("run-1") == []
    assert service.list_trials("run-1") == []
    assert service.list_stress_results("run-1") == []
    assert service.list_stress_results("run-1") == []

    warnings = [record.getMessage() for record in caplog.records]
    assert len(warnings) == 2
    assert "optional artifact 'trials'" in warnings[0]
    assert "optional artifact 'stress_results'" in warnings[1]


def test_supabase_repository_retries_once_on_connection_error(monkeypatch) -> None:
    class Response:
        data = [
            {
                "id": "run-1",
                "strategy_id": "liq_sd_v1",
                "strategy_version": "1",
                "status": "completed",
                "mode": "bayesian",
                "workers": 2,
                "pairs": ["EURUSD"],
                "n_trials": 25,
                "dd_limit": "6.0",
                "dry_run": True,
                "summary": {},
                "created_at": "2026-04-19T00:00:00+00:00",
                "updated_at": "2026-04-19T00:00:00+00:00",
            }
        ]

    first_client = FakeSupabaseClient(FakeQuery(exc=RemoteProtocolLikeError("ConnectionTerminated")))
    second_client = FakeSupabaseClient(FakeQuery(response=Response()))
    clients = iter([first_client, second_client])
    reset_calls: list[str] = []

    monkeypatch.setattr(optimizer_service_module, "get_api_supabase", lambda: next(clients))
    monkeypatch.setattr(optimizer_service_module, "reset_api_supabase", lambda: reset_calls.append("reset"))
    monkeypatch.setattr(optimizer_service_module, "is_supabase_connection_error", lambda exc: isinstance(exc, RemoteProtocolLikeError))

    repository = SupabaseOptimizerRunRepository()

    runs = repository.list_runs()

    assert [run["id"] for run in runs] == ["run-1"]
    assert reset_calls == ["reset"]


def test_portfolio_result_normalization_returns_flat_metrics_payload() -> None:
    row = {
        "run_id": "run-1",
        "metrics": {"combined_max_drawdown_pct": 5.2, "weights": {"EURUSD": 1.0}},
        "created_at": "2026-04-18T00:00:00+00:00",
        "updated_at": "2026-04-18T00:00:00+00:00",
    }

    normalized = _normalize_portfolio_result(row)

    assert normalized == {"combined_max_drawdown_pct": 5.2, "weights": {"EURUSD": 1.0}}


def test_list_runs_filters_by_strategy_identity() -> None:
    store = InMemoryOptimizerStore()
    store.create_run(
        {
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
            "summary": {},
        }
    )
    store.create_run(
        {
            "id": "run-2",
            "strategy_id": "breakout_v1",
            "strategy_version": "2",
            "status": "completed",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["NAS100"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
            "summary": {},
        }
    )
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    runs = service.list_runs(strategy_id="breakout_v1", strategy_version="2")

    assert [run["id"] for run in runs] == ["run-2"]


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
            "metrics": {"score": 2.1, "net_profit": 250.0, "win_rate": 61.0},
            "params": {"lookback": 20},
        }
    )

    result = store.results[("run-1", "EURUSD")]
    assert result["status"] == "completed"
    assert result["metrics"]["score"] == 2.1
    assert store.runs["run-1"]["summary"]["completed_pairs"] == 1
    assert store.runs["run-1"]["summary"]["best_symbol"] == "EURUSD"


def test_reconcile_incomplete_runs_marks_orphans_interrupted() -> None:
    store = InMemoryOptimizerStore.with_running_run()
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    service.reconcile_incomplete_runs()

    assert store.runs["run-1"]["status"] == "interrupted"


def test_rebuild_summary_keeps_broker_specific_output_path() -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    summary = service._rebuild_summary(
        "run-1",
        outputs={"results_file": "scripts/optimization_results/parallel_results_oanda.json"},
    )

    assert summary["output_paths"]["results_file"].endswith("parallel_results_oanda.json")


def test_results_file_for_broker_uses_broker_specific_filename() -> None:
    assert results_file_for_broker("fxcm").name == "parallel_results_fxcm.json"
    assert results_file_for_broker("oanda", "phase2-top10").name == "parallel_results_oanda_phase2-top10.json"


def test_repository_persists_trials_stress_and_portfolio_results_richer_persistence() -> None:
    store = InMemoryOptimizerStore()

    store.create_trial(
        "run-1",
        "EURUSD",
        {
            "trial_number": 1,
            "window": "train",
            "params": {"ema_len": 200},
            "metrics": {"net_profit": 1200.0},
        },
    )
    store.create_stress_result(
        "run-1",
        "EURUSD",
        {
            "stress_type": "spread_125",
            "status": "passed",
            "metrics": {"max_drawdown_pct": 4.1},
        },
    )
    store.upsert_portfolio_result(
        "run-1",
        {
            "combined_max_drawdown_pct": 5.8,
            "combined_daily_drawdown_pct": 2.7,
            "weights": {"EURUSD": 1.0},
        },
    )

    assert store.list_trials("run-1", "EURUSD")[0]["trial_number"] == 1
    assert store.list_stress_results("run-1", "EURUSD")[0]["stress_type"] == "spread_125"
    assert store.get_portfolio_result("run-1")["combined_max_drawdown_pct"] == 5.8
