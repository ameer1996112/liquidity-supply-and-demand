from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Test imports pull in repo-wide conftest fixtures that expect optional deps.
supabase = types.ModuleType("supabase")
supabase.create_client = lambda *args, **kwargs: None


class _Client:
    pass


supabase.Client = _Client
sys.modules.setdefault("supabase", supabase)

dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv)

from scripts.optimizer.watchdog import (
    archive_and_prepare_restart,
    build_optimizer_command,
    clear_run_artifacts,
    is_status_stale,
)


def test_is_status_stale_after_threshold() -> None:
    now = datetime.now(timezone.utc)
    status = {
        "last_progress_at": (now - timedelta(minutes=13)).isoformat(),
        "stuck_threshold_seconds": 12 * 60,
    }

    assert is_status_stale(status, now=now) is True


def test_is_status_stale_before_threshold() -> None:
    now = datetime.now(timezone.utc)
    status = {
        "last_progress_at": (now - timedelta(minutes=5)).isoformat(),
        "stuck_threshold_seconds": 12 * 60,
    }

    assert is_status_stale(status, now=now) is False


def test_archive_and_prepare_restart_clears_parallel_results(tmp_path: Path) -> None:
    (tmp_path / "parallel_results.json").write_text('{"EURJPY": {"score": 10}}', encoding="utf-8")
    (tmp_path / "optimizer_status_current.json").write_text("{}", encoding="utf-8")

    current = {
        "run_id": "run-1",
        "state": "running",
        "restart_count": 0,
        "log_file": "run.log",
    }

    archive_and_prepare_restart(results_dir=tmp_path, current_status=current, reason="stale_run")

    assert not (tmp_path / "parallel_results.json").exists()
    assert not (tmp_path / "optimizer_status_current.json").exists()

    history_lines = (tmp_path / "optimizer_restart_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 1
    archived = json.loads(history_lines[0])
    assert archived["run_id"] == "run-1"
    assert archived["reason"] == "stale_run"
    assert archived["state"] == "stuck"


def test_clear_run_artifacts_removes_worker_logs(tmp_path: Path) -> None:
    (tmp_path / "parallel_results.json").write_text("{}", encoding="utf-8")
    (tmp_path / "optimizer_status_current.json").write_text("{}", encoding="utf-8")
    (tmp_path / "optimizer_worker_0_oldrun.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "optimizer_worker_1_oldrun.jsonl").write_text("{}", encoding="utf-8")

    clear_run_artifacts(results_dir=tmp_path)

    assert not (tmp_path / "parallel_results.json").exists()
    assert not (tmp_path / "optimizer_status_current.json").exists()
    assert not (tmp_path / "optimizer_worker_0_oldrun.jsonl").exists()
    assert not (tmp_path / "optimizer_worker_1_oldrun.jsonl").exists()


def test_build_optimizer_command_translates_parallel_shorthand() -> None:
    launcher, module, passable_args = build_optimizer_command(
        python_executable="/tmp/venv/bin/python3",
        optimizer_args=["--parallel", "--workers", "6", "--bayesian"],
        use_caffeinate=False,
    )

    assert launcher == ["/tmp/venv/bin/python3", "-m", "scripts.optimizer.parallel_runner"]
    assert module == "scripts.optimizer.parallel_runner"
    assert passable_args == ["--workers", "6", "--mode", "bayesian"]
