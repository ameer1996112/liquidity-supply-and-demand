from __future__ import annotations

import json
import sys
import types
from pathlib import Path

supabase = types.ModuleType("supabase")
supabase.create_client = lambda *args, **kwargs: None


class _Client:
    pass


supabase.Client = _Client
sys.modules.setdefault("supabase", supabase)

dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv)

from scripts.optimizer.runtime_state import OptimizerRuntimeState


def test_start_run_writes_current_status_pointer(tmp_path: Path) -> None:
    store = OptimizerRuntimeState(results_dir=tmp_path)

    status = store.start_run(
        args=["--parallel", "--workers", "6", "--bayesian"],
        mode="bayesian",
        workers=6,
        log_file="run_20260413_010000.log",
        optimizer_pid=111,
        chrome_pid=222,
    )

    current = store.load_current_status()
    assert current["run_id"] == status["run_id"]
    assert current["state"] == "starting"
    assert current["workers"] == 6


def test_record_trial_event_updates_last_progress_and_worker_log(tmp_path: Path) -> None:
    store = OptimizerRuntimeState(results_dir=tmp_path)
    status = store.start_run(
        args=["--parallel", "--workers", "6", "--bayesian"],
        mode="bayesian",
        workers=6,
        log_file="run.log",
        optimizer_pid=111,
        chrome_pid=222,
    )

    before = store.load_current_status()["last_progress_at"]
    store.record_trial_event(
        run_id=status["run_id"],
        worker_id=0,
        symbol="EURJPY",
        trial=46,
        outcome="fresh",
        params_hash="params-1",
        results_hash_before="aaaa1111",
        results_hash_after="bbbb2222",
        metrics={"profit_factor": 1.22, "total_trades": 300},
    )

    current = store.load_current_status()
    assert current["active_pairs"]["worker-0"]["symbol"] == "EURJPY"
    assert current["worker_health"]["worker-0"]["status"] == "healthy"
    assert current["last_progress_at"] >= before

    event_lines = (tmp_path / f"optimizer_worker_0_{status['run_id']}.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(event_lines) == 1
    assert json.loads(event_lines[0])["outcome"] == "fresh"


def test_mark_pair_started_and_completed_update_active_pairs(tmp_path: Path) -> None:
    store = OptimizerRuntimeState(results_dir=tmp_path)
    status = store.start_run(
        args=["--parallel", "--workers", "2", "--bayesian"],
        mode="bayesian",
        workers=2,
        log_file="run.log",
        optimizer_pid=111,
        chrome_pid=222,
    )

    store.mark_pair_started(run_id=status["run_id"], worker_id=1, symbol="GBPJPY")
    current = store.load_current_status()
    assert current["active_pairs"]["worker-1"]["symbol"] == "GBPJPY"
    assert current["active_pairs"]["worker-1"]["status"] == "running"

    store.mark_pair_completed(run_id=status["run_id"], worker_id=1, symbol="GBPJPY")
    current = store.load_current_status()
    assert current["active_pairs"]["worker-1"]["status"] == "completed"


def test_mark_worker_unhealthy_persists_reason(tmp_path: Path) -> None:
    store = OptimizerRuntimeState(results_dir=tmp_path)
    status = store.start_run(
        args=["--parallel", "--workers", "2", "--bayesian"],
        mode="bayesian",
        workers=2,
        log_file="run.log",
        optimizer_pid=111,
        chrome_pid=222,
    )

    store.mark_worker_unhealthy(
        run_id=status["run_id"],
        worker_id=0,
        stale_reads=3,
        reason="repeated_stale_results",
    )

    current = store.load_current_status()
    assert current["worker_health"]["worker-0"]["status"] == "unhealthy"
    assert current["worker_health"]["worker-0"]["stale_reads"] == 3
    assert current["worker_health"]["worker-0"]["reason"] == "repeated_stale_results"
