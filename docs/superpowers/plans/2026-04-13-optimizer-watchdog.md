# Optimizer Watchdog and Fresh-Read Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fresh-read enforcement, machine-readable optimizer health tracking, and a macOS watchdog that restarts a stuck optimizer from a completely clean state.

**Architecture:** Add a focused runtime-state helper module that owns the current run status and per-worker JSONL event logs, then wire that module into `parallel_runner.py`. Harden `tab_worker.py` and `optimizer.py` so unchanged result hashes and symbol mismatches are treated as failed trials, and add a separate `watchdog.py` entrypoint plus `launchd` install helper to restart Chrome and relaunch the optimizer when progress stops for more than 12 minutes.

**Tech Stack:** Python 3.11, asyncio, Playwright, pytest, bash, JSON/JSONL files, launchd on macOS.

---

## File Structure

- Create: `scripts/optimizer/runtime_state.py`
  Owns run metadata, current-status pointer updates, restart history, and per-worker JSONL event emission.

- Create: `scripts/optimizer/watchdog.py`
  Implements stale-run detection, run archival, Chrome restart, artifact clearing, and relaunch logic.

- Create: `scripts/optimizer/install_launchd.sh`
  Installs a `LaunchAgent` that invokes the watchdog every 2 minutes.

- Create: `tests/test_optimizer_runtime_state.py`
  Covers status bootstrap, heartbeat updates, pointer updates, and worker event logging.

- Create: `tests/test_optimizer_tab_worker_freshness.py`
  Covers unchanged result-hash rejection, symbol mismatch handling, and best-result freshness rules.

- Create: `tests/test_optimizer_watchdog.py`
  Covers stale detection, restart-history archival, artifact clearing, and launch command generation.

- Modify: `scripts/optimizer/tab_worker.py`
  Returns structured apply outcomes, rejects unchanged final hashes, and verifies symbol before reading metrics.

- Modify: `scripts/optimizer/optimizer.py`
  Accepts structured trial outcomes and ensures only fresh trial results affect the Bayesian study and best-result tracking.

- Modify: `scripts/optimizer/parallel_runner.py`
  Creates run state, records per-worker progress, and writes structured events alongside the existing human log.

- Modify: `scripts/optimizer/run.sh`
  Adds watchdog-managed start, status, force-restart, and stop entry points while keeping the current direct-run behavior.

## Task 1: Add Runtime State and Worker Event Logging

**Files:**
- Create: `scripts/optimizer/runtime_state.py`
- Create: `tests/test_optimizer_runtime_state.py`

- [ ] **Step 1: Write the failing runtime-state tests**

```python
from pathlib import Path

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

    event_lines = (tmp_path / f"optimizer_worker_0_{status['run_id']}.jsonl").read_text().splitlines()
    assert len(event_lines) == 1
    assert '"outcome": "fresh"' in event_lines[0]
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py -v
```

Expected:

```text
ERROR tests/test_optimizer_runtime_state.py
E   ModuleNotFoundError: No module named 'scripts.optimizer.runtime_state'
```

- [ ] **Step 3: Implement the runtime-state module**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class OptimizerRuntimeState:
    results_dir: Path

    def __post_init__(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.current_status_path = self.results_dir / "optimizer_status_current.json"
        self.restart_history_path = self.results_dir / "optimizer_restart_history.jsonl"

    def start_run(
        self,
        *,
        args: list[str],
        mode: str,
        workers: int,
        log_file: str,
        optimizer_pid: int,
        chrome_pid: int | None,
        restart_count: int = 0,
    ) -> dict[str, Any]:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        payload = {
            "run_id": run_id,
            "state": "starting",
            "started_at": _iso_now(),
            "last_progress_at": _iso_now(),
            "stuck_threshold_seconds": 12 * 60,
            "restart_count": restart_count,
            "optimizer_pid": optimizer_pid,
            "chrome_pid": chrome_pid,
            "log_file": log_file,
            "mode": mode,
            "workers": workers,
            "args": args,
            "active_pairs": {},
            "worker_health": {},
        }
        self._write_status(payload)
        return payload

    def load_current_status(self) -> dict[str, Any]:
        return json.loads(self.current_status_path.read_text())

    def record_trial_event(
        self,
        *,
        run_id: str,
        worker_id: int,
        symbol: str,
        trial: int,
        outcome: str,
        params_hash: str,
        results_hash_before: str,
        results_hash_after: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        status = self.load_current_status()
        now = _iso_now()
        worker_key = f"worker-{worker_id}"
        status["active_pairs"][worker_key] = {
            "symbol": symbol,
            "trial": trial,
            "last_event_at": now,
            "status": "running",
        }
        status["worker_health"][worker_key] = {
            "status": "healthy" if outcome == "fresh" else "warning",
            "stale_reads": 0 if outcome == "fresh" else 1,
            "last_results_hash": results_hash_after,
        }
        if outcome == "fresh":
            status["last_progress_at"] = now
        self._write_status(status)

        event_path = self.results_dir / f"optimizer_worker_{worker_id}_{run_id}.jsonl"
        event = {
            "ts": now,
            "run_id": run_id,
            "worker_id": worker_id,
            "symbol": symbol,
            "trial": trial,
            "outcome": outcome,
            "params_hash": params_hash,
            "results_hash_before": results_hash_before,
            "results_hash_after": results_hash_after,
            "metrics": metrics or {},
        }
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    def _write_status(self, payload: dict[str, Any]) -> None:
        status_path = self.results_dir / f"optimizer_status_{payload['run_id']}.json"
        status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.current_status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py -v
```

Expected:

```text
tests/test_optimizer_runtime_state.py::test_start_run_writes_current_status_pointer PASSED
tests/test_optimizer_runtime_state.py::test_record_trial_event_updates_last_progress_and_worker_log PASSED
```

- [ ] **Step 5: Commit**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git add tests/test_optimizer_runtime_state.py scripts/optimizer/runtime_state.py
git commit -m "DEV-104: add optimizer runtime state store"
```

## Task 2: Reject Stale TradingView Results and Symbol Mismatches

**Files:**
- Modify: `scripts/optimizer/tab_worker.py`
- Modify: `scripts/optimizer/optimizer.py`
- Create: `tests/test_optimizer_tab_worker_freshness.py`

- [ ] **Step 1: Write failing freshness tests**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.tab_worker import TabWorker


@pytest.mark.asyncio
async def test_apply_params_returns_stale_outcome_when_hash_never_changes(monkeypatch) -> None:
    worker = TabWorker(page=SimpleNamespace(), optimizer=SimpleNamespace())

    monkeypatch.setattr(worker, "_get_results_hash", AsyncMock(side_effect=["samehash", "samehash", "samehash", "samehash"]))
    monkeypatch.setattr(worker, "_open_settings", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_ensure_custom_profile", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_click_ok", AsyncMock())
    monkeypatch.setattr(worker, "_wait_dialog_close", AsyncMock())
    monkeypatch.setattr(worker, "_wait_for_update_complete", AsyncMock(return_value=True))
    monkeypatch.setattr(worker.page, "evaluate", AsyncMock(return_value=None))

    outcome = await worker._apply_params({"risk_per_trade_pct": 0.5})

    assert outcome.applied is False
    assert outcome.reason == "stale_results"


@pytest.mark.asyncio
async def test_read_results_rejects_symbol_mismatch(monkeypatch) -> None:
    worker = TabWorker(page=SimpleNamespace(), optimizer=SimpleNamespace())

    monkeypatch.setattr(worker, "_current_symbol", AsyncMock(return_value="GBPJPY"))
    monkeypatch.setattr(worker.page, "evaluate", AsyncMock(return_value={"Net Profit": "123"}))

    with pytest.raises(RuntimeError, match="Expected EURJPY but tab shows GBPJPY"):
        await worker._read_results("EURJPY", {"rr_mode": "dynamic"})
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_tab_worker_freshness.py -v
```

Expected:

```text
FAILED tests/test_optimizer_tab_worker_freshness.py::test_apply_params_returns_stale_outcome_when_hash_never_changes
FAILED tests/test_optimizer_tab_worker_freshness.py::test_read_results_rejects_symbol_mismatch
```

- [ ] **Step 3: Introduce structured apply outcomes in `tab_worker.py`**

```python
from dataclasses import dataclass


@dataclass
class ApplyParamsOutcome:
    applied: bool
    is_fresh: bool
    reason: str
    hash_before: str = ""
    hash_after: str = ""


async def _current_symbol(self) -> str:
    title = await self.page.title()
    return title.split(" ")[0].split(":")[-1].upper().strip() if title else ""


async def _apply_params(self, params: dict) -> ApplyParamsOutcome:
    for attempt in range(1, _MAX_RETRIES + 1):
        hash_before = await self._get_results_hash()
        if not await self._open_settings():
            return ApplyParamsOutcome(applied=False, is_fresh=False, reason="open_settings_failed")
        await asyncio.sleep(0.5)
        await self.page.evaluate(
            """
            (() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent?.trim() === 'Inputs') {
                        b.click(); return;
                    }
                }
            })()
            """
        )
        await asyncio.sleep(0.3)
        await self._ensure_custom_profile()
        for name, value in params.items():
            idx = INPUT_INDEX.get(name)
            if idx is not None:
                await self._set_input(idx, value)
        await self._click_ok()
        await self._wait_dialog_close()
        completed = await self._wait_for_update_complete()
        if not completed and attempt == _MAX_RETRIES:
            return ApplyParamsOutcome(
                applied=False,
                is_fresh=False,
                reason="update_timeout",
                hash_before=hash_before,
                hash_after="",
            )
        hash_after = await self._get_results_hash()
        if hash_before and hash_after and hash_before == hash_after:
            log.warning(
                "_apply_params attempt %d: results hash unchanged (possible stale read or param rejected)",
                attempt,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_SLEEP)
                continue
            return ApplyParamsOutcome(
                applied=False,
                is_fresh=False,
                reason="stale_results",
                hash_before=hash_before,
                hash_after=hash_after,
            )

        return ApplyParamsOutcome(
            applied=True,
            is_fresh=True,
            reason="fresh_results",
            hash_before=hash_before,
            hash_after=hash_after,
        )

    return ApplyParamsOutcome(applied=False, is_fresh=False, reason="apply_failed")


async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
    current_symbol = await self._current_symbol()
    if current_symbol and current_symbol != symbol.upper():
        raise RuntimeError(f"Expected {symbol.upper()} but tab shows {current_symbol}")
    result = BacktestResult(symbol=symbol, params=params.copy(), timestamp=datetime.now().isoformat())
    metrics = await self.page.evaluate(_JS_COLLECT_METRICS)
    for key, value in (metrics or {}).items():
        if key.lower() == "profit factor":
            result.profit_factor = float(value.split("|")[0])
    result.calculate_score()
    return result
```

- [ ] **Step 4: Update the Bayesian loop to accept only fresh results**

```python
apply_outcome = await asyncio.wait_for(
    worker._apply_params(params), timeout=_TRIAL_HARD_TIMEOUT
)
if not apply_outcome.applied or not apply_outcome.is_fresh:
    study.tell(trial, 0.0)
    print(f"  -> SKIP ({apply_outcome.reason})")
    continue

result = await asyncio.wait_for(
    worker._read_results(symbol, params), timeout=_TRIAL_HARD_TIMEOUT
)

if not apply_outcome.is_fresh:
    study.tell(trial, 0.0)
    continue
```

- [ ] **Step 5: Run the targeted tests**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_tab_worker_freshness.py -v
```

Expected:

```text
tests/test_optimizer_tab_worker_freshness.py::test_apply_params_returns_stale_outcome_when_hash_never_changes PASSED
tests/test_optimizer_tab_worker_freshness.py::test_read_results_rejects_symbol_mismatch PASSED
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git add tests/test_optimizer_tab_worker_freshness.py scripts/optimizer/tab_worker.py scripts/optimizer/optimizer.py
git commit -m "DEV-104: reject stale optimizer trial reads"
```

## Task 3: Wire Runtime State into the Parallel Runner

**Files:**
- Modify: `scripts/optimizer/parallel_runner.py`
- Modify: `scripts/optimizer/optimizer.py`
- Modify: `scripts/optimizer/tab_worker.py`
- Modify: `tests/test_optimizer_runtime_state.py`

- [ ] **Step 1: Add a failing integration-style test for runner heartbeats**

```python
from pathlib import Path

from scripts.optimizer.runtime_state import OptimizerRuntimeState


def test_mark_pair_started_updates_active_pairs(tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run the expanded runtime-state tests**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py -v
```

Expected:

```text
FAILED tests/test_optimizer_runtime_state.py::test_mark_pair_started_updates_active_pairs
E   AttributeError: 'OptimizerRuntimeState' object has no attribute 'mark_pair_started'
```

- [ ] **Step 3: Implement pair-start, pair-complete, and worker-health hooks**

```python
def mark_pair_started(self, *, run_id: str, worker_id: int, symbol: str) -> None:
    status = self.load_current_status()
    worker_key = f"worker-{worker_id}"
    now = _iso_now()
    status["state"] = "running"
    status["active_pairs"][worker_key] = {
        "symbol": symbol,
        "trial": 0,
        "last_event_at": now,
        "status": "running",
    }
    status["last_progress_at"] = now
    self._write_status(status)


def mark_pair_completed(self, *, run_id: str, worker_id: int, symbol: str) -> None:
    status = self.load_current_status()
    worker_key = f"worker-{worker_id}"
    now = _iso_now()
    status["active_pairs"][worker_key] = {
        "symbol": symbol,
        "trial": status["active_pairs"].get(worker_key, {}).get("trial", 0),
        "last_event_at": now,
        "status": "completed",
    }
    status["last_progress_at"] = now
    self._write_status(status)


def mark_worker_unhealthy(self, *, worker_id: int, stale_reads: int, reason: str) -> None:
    status = self.load_current_status()
    worker_key = f"worker-{worker_id}"
    status["worker_health"][worker_key] = {
        "status": "unhealthy",
        "stale_reads": stale_reads,
        "reason": reason,
        "last_results_hash": status["worker_health"].get(worker_key, {}).get("last_results_hash", ""),
    }
    self._write_status(status)
```

- [ ] **Step 4: Connect `parallel_runner.py` to the state store**

```python
from .runtime_state import OptimizerRuntimeState


def detect_chrome_pid() -> int | None:
    try:
        output = subprocess.check_output(["lsof", "-ti", ":9222"], text=True).strip().splitlines()
        return int(output[0]) if output else None
    except Exception:
        return None


state_store = OptimizerRuntimeState(results_dir=RESULTS_DIR)
status = state_store.start_run(
    args=sys.argv[1:],
    mode=mode,
    workers=n_workers,
    log_file=str(PARALLEL_LOG_FILE),
    optimizer_pid=os.getpid(),
    chrome_pid=detect_chrome_pid(),
)
worker_run_context = {
    "run_id": status["run_id"],
    "state_store": state_store,
}

log.info(f"[worker-{worker_id}] Starting {symbol} (attempt {retries + 1})")
state_store.mark_pair_started(run_id=status["run_id"], worker_id=worker_id, symbol=symbol)
result = await optimize_pair_on_page(
    page,
    symbol,
    mode,
    n_trials,
    dd_limit,
    dry_run,
    run_context=worker_run_context,
    worker_id=worker_id,
)

state_store.mark_pair_completed(run_id=status["run_id"], worker_id=worker_id, symbol=symbol)
```

- [ ] **Step 5: Pass trial-event metadata from the Bayesian loop**

```python
opt_shell.runtime_state = run_context["state_store"]
opt_shell.run_id = run_context["run_id"]
opt_shell.worker_id = worker_id

if self.runtime_state is not None:
    self.runtime_state.record_trial_event(
        run_id=self.run_id,
        worker_id=self.worker_id,
        symbol=symbol,
        trial=trial_num,
        outcome="fresh",
        params_hash=hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8],
        results_hash_before=apply_outcome.hash_before,
        results_hash_after=apply_outcome.hash_after,
        metrics={
            "profit_factor": result.profit_factor,
            "max_drawdown_pct": result.max_drawdown_pct,
            "total_trades": result.total_trades,
            "score": result.score,
        },
    )
```

- [ ] **Step 6: Run the runtime-state tests again**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git add scripts/optimizer/runtime_state.py scripts/optimizer/parallel_runner.py scripts/optimizer/optimizer.py scripts/optimizer/tab_worker.py tests/test_optimizer_runtime_state.py
git commit -m "DEV-104: add optimizer heartbeat and event logging"
```

## Task 4: Build the Watchdog and Clean-Restart Flow

**Files:**
- Create: `scripts/optimizer/watchdog.py`
- Create: `tests/test_optimizer_watchdog.py`
- Modify: `scripts/optimizer/runtime_state.py`

- [ ] **Step 1: Write failing watchdog tests**

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.optimizer.watchdog import is_status_stale, archive_and_prepare_restart


def test_is_status_stale_after_threshold() -> None:
    now = datetime.now(timezone.utc)
    status = {
        "last_progress_at": (now - timedelta(minutes=13)).isoformat(),
        "stuck_threshold_seconds": 12 * 60,
    }
    assert is_status_stale(status, now=now) is True


def test_archive_and_prepare_restart_clears_parallel_results(tmp_path: Path) -> None:
    (tmp_path / "parallel_results.json").write_text('{"EURJPY": {"score": 10}}', encoding="utf-8")
    current = {
        "run_id": "run-1",
        "state": "running",
        "restart_count": 0,
        "log_file": "run.log",
    }

    archive_and_prepare_restart(results_dir=tmp_path, current_status=current, reason="stale_run")

    assert not (tmp_path / "parallel_results.json").exists()
    history = (tmp_path / "optimizer_restart_history.jsonl").read_text()
    assert '"reason": "stale_run"' in history
```

- [ ] **Step 2: Run the watchdog tests to verify they fail**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_watchdog.py -v
```

Expected:

```text
ERROR tests/test_optimizer_watchdog.py
E   ModuleNotFoundError: No module named 'scripts.optimizer.watchdog'
```

- [ ] **Step 3: Implement stale detection and archive helpers**

```python
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import RESULTS_DIR
from .runtime_state import OptimizerRuntimeState


def is_status_stale(status: dict, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    last_progress = datetime.fromisoformat(status["last_progress_at"])
    threshold = status.get("stuck_threshold_seconds", 12 * 60)
    return (now - last_progress).total_seconds() > threshold


def archive_and_prepare_restart(*, results_dir: Path, current_status: dict, reason: str) -> None:
    store = OptimizerRuntimeState(results_dir=results_dir)
    archived = dict(current_status)
    archived["state"] = "stuck"
    archived["archived_at"] = datetime.now(timezone.utc).astimezone().isoformat()
    archived["reason"] = reason

    with store.restart_history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(archived) + "\n")

    for filename in ("parallel_results.json", "optimizer_status_current.json"):
        target = results_dir / filename
        if target.exists():
            target.unlink()
```

- [ ] **Step 4: Implement process stop, Chrome restart, and relaunch helpers**

```python
def stop_optimizer(pid: int | None) -> None:
    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def restart_chrome(project_root: Path) -> None:
    subprocess.run(
        ["bash", str(project_root / "scripts/optimizer/start-chrome.sh")],
        check=True,
        cwd=project_root,
    )


def relaunch_optimizer(project_root: Path, args: list[str]) -> None:
    log_path = project_root / "scripts/optimization_results" / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.Popen(
            [sys.executable, "-m", "scripts.optimizer.parallel_runner", *args],
            cwd=project_root,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return
```

- [ ] **Step 5: Run the watchdog tests**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
PYTHONPATH=. pytest tests/test_optimizer_watchdog.py -v
```

Expected:

```text
tests/test_optimizer_watchdog.py::test_is_status_stale_after_threshold PASSED
tests/test_optimizer_watchdog.py::test_archive_and_prepare_restart_clears_parallel_results PASSED
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git add tests/test_optimizer_watchdog.py scripts/optimizer/watchdog.py scripts/optimizer/runtime_state.py
git commit -m "DEV-104: add optimizer watchdog restart flow"
```

## Task 5: Add Operator Commands, launchd Install, and Final Verification

**Files:**
- Modify: `scripts/optimizer/run.sh`
- Create: `scripts/optimizer/install_launchd.sh`
- Modify: `scripts/optimizer/watchdog.py`
- Modify: `tests/test_optimizer_watchdog.py`

- [ ] **Step 1: Extend `run.sh` with managed control commands**

```bash
if [[ "${1:-}" == "--status" ]]; then
    exec "$PYTHON" -m scripts.optimizer.watchdog status
fi

if [[ "${1:-}" == "--force-restart" ]]; then
    exec "$PYTHON" -m scripts.optimizer.watchdog force-restart
fi

if [[ "${1:-}" == "--stop-managed" ]]; then
    exec "$PYTHON" -m scripts.optimizer.watchdog stop
fi

if [[ "${1:-}" == "--managed" ]]; then
    shift
    exec "$PYTHON" -m scripts.optimizer.watchdog start "$@"
fi
```

- [ ] **Step 2: Add the launchd installer**

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_PATH="${HOME}/Library/LaunchAgents/com.galil.optimizer-watchdog.plist"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.galil.optimizer-watchdog</string>
    <key>ProgramArguments</key>
    <array>
      <string>${PROJECT_ROOT}/venv/bin/python3</string>
      <string>-m</string>
      <string>scripts.optimizer.watchdog</string>
      <string>check</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    <key>StartInterval</key>
    <integer>120</integer>
    <key>StandardOutPath</key>
    <string>${PROJECT_ROOT}/scripts/optimization_results/watchdog.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_ROOT}/scripts/optimization_results/watchdog.stderr.log</string>
  </dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
launchctl kickstart -k gui/"$(id -u)"/com.galil.optimizer-watchdog
```

- [ ] **Step 3: Add a CLI surface in `watchdog.py`**

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Optimizer watchdog")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    subparsers.add_parser("status")
    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("optimizer_args", nargs=argparse.REMAINDER)
    subparsers.add_parser("force-restart")
    subparsers.add_parser("stop")
    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(load_current_status_or_empty(), indent=2))
        return
    if args.command == "check":
        run_watchdog_check()
        return
    if args.command == "start":
        launch_managed_optimizer(args.optimizer_args)
        return
```

- [ ] **Step 4: Run shell and Python validation**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
bash -n scripts/optimizer/run.sh
bash -n scripts/optimizer/install_launchd.sh
PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py tests/test_optimizer_tab_worker_freshness.py tests/test_optimizer_watchdog.py -v
python3 -m py_compile scripts/optimizer/runtime_state.py scripts/optimizer/watchdog.py scripts/optimizer/parallel_runner.py scripts/optimizer/tab_worker.py scripts/optimizer/optimizer.py
```

Expected:

```text
No output from bash -n
All targeted pytest tests PASSED
No output from py_compile
```

- [ ] **Step 5: Run the smoke test**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
bash scripts/optimizer/run.sh --managed --parallel --workers 2 --dry-run
python3 -m scripts.optimizer.watchdog status
python3 -m scripts.optimizer.watchdog force-restart
```

Expected:

```text
Managed optimizer starts
optimizer_status_current.json is present
Worker JSONL files are present
Force restart archives the old run and launches a new clean run
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git add scripts/optimizer/run.sh scripts/optimizer/install_launchd.sh scripts/optimizer/watchdog.py tests/test_optimizer_watchdog.py
git commit -m "DEV-104: add optimizer watchdog controls"
```

## Task 6: Final Review and Handoff

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-optimizer-watchdog-design.md` only if implementation uncovered a design mismatch

- [ ] **Step 1: Verify spec coverage before merging**

Checklist:

```text
[ ] Status file exists and is updated by the parallel runner
[ ] Worker JSONL events include trial freshness outcomes
[ ] Unchanged final result hashes are rejected
[ ] Symbol mismatches fail reads
[ ] Watchdog archives stale runs and clears restart artifacts
[ ] Chrome restart is part of the recovery flow
[ ] run.sh exposes managed start/status/restart/stop commands
[ ] launchd installer exists and uses a 120-second interval
```

- [ ] **Step 2: Review the final diff**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- scripts/optimizer tests docs/superpowers
```

Expected:

```text
Only optimizer, tests, and plan/spec documentation files changed
No trading execution files changed
```

- [ ] **Step 3: Create the final integration commit**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
git add scripts/optimizer tests docs/superpowers
git commit -m "DEV-104: harden optimizer watchdog workflow"
```
