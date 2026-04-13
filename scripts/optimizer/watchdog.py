"""
watchdog.py — Managed optimizer launcher and stale-run watchdog.

This module intentionally treats stale or mixed optimizer runs as untrustworthy.
When a run is detected as stuck, it archives the old run metadata, clears the
current result artifacts, restarts Chrome, and launches a fresh optimizer run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT, RESULTS_DIR

CURRENT_STATUS_FILE = RESULTS_DIR / "optimizer_status_current.json"
RESTART_HISTORY_FILE = RESULTS_DIR / "optimizer_restart_history.jsonl"


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_current_status(results_dir: Path = RESULTS_DIR) -> dict[str, Any] | None:
    current_path = results_dir / CURRENT_STATUS_FILE.name
    if not current_path.exists():
        return None
    return json.loads(current_path.read_text(encoding="utf-8"))


def is_status_stale(status: dict[str, Any], *, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    last_progress = datetime.fromisoformat(status["last_progress_at"])
    threshold = int(status.get("stuck_threshold_seconds", 12 * 60))
    return (now - last_progress).total_seconds() > threshold


def clear_run_artifacts(results_dir: Path = RESULTS_DIR) -> None:
    for filename in ("parallel_results.json", CURRENT_STATUS_FILE.name):
        target = results_dir / filename
        if target.exists():
            target.unlink()

    for pattern in ("optimizer_worker_*.jsonl",):
        for target in results_dir.glob(pattern):
            target.unlink()


def archive_and_prepare_restart(
    *,
    results_dir: Path,
    current_status: dict[str, Any],
    reason: str,
) -> None:
    archived = dict(current_status)
    archived["state"] = "stuck"
    archived["reason"] = reason
    archived["archived_at"] = _iso_now()

    run_id = archived.get("run_id")
    if run_id:
        status_path = results_dir / f"optimizer_status_{run_id}.json"
        if status_path.exists():
            status_path.write_text(json.dumps(archived, indent=2), encoding="utf-8")

    history_path = results_dir / RESTART_HISTORY_FILE.name
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(archived) + "\n")

    clear_run_artifacts(results_dir=results_dir)


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_optimizer(pid: int | None) -> None:
    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.time() + 10
    while time.time() < deadline:
        if not _pid_is_alive(pid):
            return
        time.sleep(0.5)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def restart_chrome(project_root: Path = PROJECT_ROOT) -> None:
    subprocess.run(
        ["bash", str(project_root / "scripts/optimizer/start-chrome.sh")],
        cwd=project_root,
        check=True,
    )


def _wait_for_cdp(timeout_seconds: int = 20) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            subprocess.run(
                ["curl", "-fsS", "http://127.0.0.1:9222/json/version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            time.sleep(1.0)
    return False


def _launcher_prefix(python_executable: str, *, use_caffeinate: bool) -> list[str]:
    if use_caffeinate and shutil.which("caffeinate"):
        return ["caffeinate", "-ids", python_executable]
    return [python_executable]


def resolve_project_python(project_root: Path, fallback: str) -> str:
    candidates = [
        project_root / "venv/bin/python3",
        project_root / ".venv/bin/python3",
        Path("/workspace/.venv/bin/python3"),
    ]
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return fallback


def build_optimizer_command(
    *,
    python_executable: str,
    optimizer_args: list[str],
    use_caffeinate: bool = True,
) -> tuple[list[str], str, list[str]]:
    parallel_mode = False
    raw_args: list[str] = []
    for arg in optimizer_args:
        if arg == "--parallel":
            parallel_mode = True
        else:
            raw_args.append(arg)

    if parallel_mode:
        module = "scripts.optimizer.parallel_runner"
        passable_args: list[str] = []
        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            if arg == "--bayesian":
                passable_args += ["--mode", "bayesian"]
            elif arg == "--smart":
                passable_args += ["--mode", "smart"]
            elif arg == "--fast":
                passable_args += ["--mode", "fast"]
            elif arg == "--full":
                passable_args += ["--mode", "full"]
            elif arg == "--n-trials" and i + 1 < len(raw_args):
                i += 1
                passable_args += ["--trials", raw_args[i]]
            else:
                passable_args.append(arg)
            i += 1
    else:
        module = "scripts.optimizer.main"
        passable_args = list(raw_args)

    launcher = _launcher_prefix(python_executable, use_caffeinate=use_caffeinate) + ["-m", module]
    return launcher, module, passable_args


def launch_managed_optimizer(
    optimizer_args: list[str],
    *,
    project_root: Path = PROJECT_ROOT,
    results_dir: Path = RESULTS_DIR,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    results_dir.mkdir(exist_ok=True)
    if "--parallel" not in optimizer_args:
        raise ValueError("Managed watchdog mode currently requires --parallel")
    clear_run_artifacts(results_dir=results_dir)
    python_executable = resolve_project_python(project_root, python_executable)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = results_dir / f"run_{timestamp}.log"
    launcher, module, passable_args = build_optimizer_command(
        python_executable=python_executable,
        optimizer_args=optimizer_args,
        use_caffeinate=True,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["_OPTIMIZER_VENV_ACTIVE"] = "1"
    env["OPTIMIZER_LAUNCH_LOG_FILE"] = str(log_file)

    with log_file.open("a", encoding="utf-8") as handle:
        process = subprocess.Popen(
            launcher + passable_args,
            cwd=project_root,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    return {
        "pid": process.pid,
        "module": module,
        "log_file": str(log_file),
        "args": optimizer_args,
    }


def _restart_from_status(
    current_status: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
    results_dir: Path = RESULTS_DIR,
    reason: str,
) -> dict[str, Any]:
    archive_and_prepare_restart(results_dir=results_dir, current_status=current_status, reason=reason)
    stop_optimizer(current_status.get("optimizer_pid"))
    restart_chrome(project_root=project_root)
    if not _wait_for_cdp():
        raise RuntimeError("Chrome CDP did not become healthy after restart")
    return launch_managed_optimizer(
        list(current_status.get("args", [])),
        project_root=project_root,
        results_dir=results_dir,
        python_executable=sys.executable,
    )


def run_watchdog_check(results_dir: Path = RESULTS_DIR) -> int:
    current_status = load_current_status(results_dir=results_dir)
    if not current_status:
        print("[watchdog] No active managed optimizer status found.")
        return 0

    if current_status.get("state") in {"completed", "failed"}:
        print(f"[watchdog] Run already finished with state={current_status['state']}.")
        return 0

    if not is_status_stale(current_status):
        print("[watchdog] Run healthy.")
        return 0

    relaunch = _restart_from_status(current_status, reason="stale_run", results_dir=results_dir)
    print(
        f"[watchdog] Restarted stale run {current_status.get('run_id')} "
        f"as PID {relaunch['pid']} using {relaunch['module']}."
    )
    return 0


def _print_status(results_dir: Path = RESULTS_DIR) -> int:
    current_status = load_current_status(results_dir=results_dir)
    if not current_status:
        print("[watchdog] No active managed optimizer status found.")
        return 0
    print(json.dumps(current_status, indent=2))
    return 0


def _force_restart(results_dir: Path = RESULTS_DIR) -> int:
    current_status = load_current_status(results_dir=results_dir)
    if not current_status:
        print("[watchdog] No active managed optimizer status found.")
        return 1
    relaunch = _restart_from_status(current_status, reason="manual_restart", results_dir=results_dir)
    print(
        f"[watchdog] Force-restarted run {current_status.get('run_id')} "
        f"as PID {relaunch['pid']}."
    )
    return 0


def _stop_managed(results_dir: Path = RESULTS_DIR) -> int:
    current_status = load_current_status(results_dir=results_dir)
    if not current_status:
        print("[watchdog] No active managed optimizer status found.")
        return 0

    stop_optimizer(current_status.get("optimizer_pid"))
    archived = dict(current_status)
    archived["state"] = "failed"
    archived["reason"] = "manual_stop"
    archived["archived_at"] = _iso_now()
    with (results_dir / RESTART_HISTORY_FILE.name).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(archived) + "\n")
    clear_run_artifacts(results_dir=results_dir)
    print(f"[watchdog] Stopped managed optimizer run {current_status.get('run_id')}.")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.optimizer.watchdog {check,status,start,force-restart,stop}")
        return 1

    command = sys.argv[1]

    if command == "start":
        launch = launch_managed_optimizer(sys.argv[2:], results_dir=RESULTS_DIR)
        print(
            f"[watchdog] Managed optimizer started as PID {launch['pid']} "
            f"({launch['module']}) log={launch['log_file']}"
        )
        return 0

    parser = argparse.ArgumentParser(description="Optimizer watchdog")
    parser.add_argument("command", choices=["check", "status", "force-restart", "stop"])
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = parser.parse_args()
    results_dir = Path(args.results_dir)

    if command == "check":
        return run_watchdog_check(results_dir=results_dir)
    if command == "status":
        return _print_status(results_dir=results_dir)
    if command == "force-restart":
        return _force_restart(results_dir=results_dir)
    if command == "stop":
        return _stop_managed(results_dir=results_dir)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
