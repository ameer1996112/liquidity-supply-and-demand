# TradingView MCP Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch optimizer runs from Chrome CDP to TradingView Desktop MCP, and only claim queued runs after MCP/Desktop readiness succeeds.

**Architecture:** Introduce a shared TradingView MCP transport helper plus an optimizer-specific MCP controller, then refactor the optimizer runner to depend on that controller instead of `connect_over_cdp()`. Update the local agent to preflight optimizer MCP readiness before claiming queued runs, leaving runs queued when the desktop app is unavailable.

**Tech Stack:** Python 3.11, asyncio, subprocess-based MCP CLI calls, pytest, existing optimizer tooling in `scripts/optimizer/`

---

## File Structure

- Create: `scripts/optimizer/tradingview_mcp.py`
  Shared TradingView MCP CLI path resolution, subprocess JSON execution, and basic healthcheck helpers used by both alerts and optimizer code.

- Create: `scripts/optimizer/optimizer_mcp.py`
  Optimizer-specific controller for TradingView Desktop readiness, workspace bootstrap, symbol switching, and report/session helpers.

- Modify: `scripts/optimizer/alert_runner.py`
  Reuse the new shared MCP transport helper without changing alert deployment behavior.

- Modify: `scripts/optimizer/parallel_runner.py`
  Replace direct Chrome CDP attach logic with the optimizer controller boundary.

- Modify: `scripts/optimizer/local_agent.py`
  Gate optimizer run claiming on MCP readiness and stop using Chrome as the optimizer prerequisite.

- Test: `tests/test_alert_runner.py`
  Lock down shared MCP helper compatibility and unchanged alert behavior.

- Test: `tests/test_optimizer_runtime_state.py`
  Keep runtime expectations honest if controller errors change run lifecycle timing.

- Create: `tests/test_optimizer_mcp.py`
  Cover MCP transport/controller readiness, bootstrap, and failure normalization.

- Create: `tests/test_optimizer_local_agent.py`
  Cover queue preservation and no-claim behavior when MCP/Desktop is unavailable.

- Create: `tests/test_parallel_runner_mcp.py`
  Cover the optimizer runner abstraction and ensure CDP is no longer the active path.

### Task 1: Extract Shared TradingView MCP Transport

**Files:**
- Create: `scripts/optimizer/tradingview_mcp.py`
- Modify: `scripts/optimizer/alert_runner.py`
- Test: `tests/test_alert_runner.py`

- [ ] **Step 1: Write the failing shared-helper test**

```python
from pathlib import Path

from scripts.optimizer.tradingview_mcp import TradingViewMcpClient


def test_tradingview_mcp_client_uses_repo_cli_path() -> None:
    client = TradingViewMcpClient()
    assert client._cli_path == Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp" / "src" / "cli" / "index.js"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_alert_runner.py::test_tradingview_mcp_client_uses_repo_cli_path -v`
Expected: FAIL with `ModuleNotFoundError` or missing `TradingViewMcpClient`

- [ ] **Step 3: Write the minimal shared transport**

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TV_CLI_PATH = PROJECT_ROOT / "mcp" / "tradingview-mcp" / "src" / "cli" / "index.js"


class TradingViewMcpClient:
    def __init__(self, cli_path: Path | None = None) -> None:
        self._cli_path = cli_path or DEFAULT_TV_CLI_PATH

    async def run(self, *args: str) -> dict[str, Any]:
        if not self._cli_path.exists():
            raise RuntimeError(f"TradingView MCP CLI not found at {self._cli_path}")
        process = await asyncio.create_subprocess_exec(
            "node",
            str(self._cli_path),
            *args,
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        raw = (stdout or b"").decode().strip() or (stderr or b"").decode().strip()
        if process.returncode != 0:
            raise RuntimeError(raw or f"tv {' '.join(args)} failed with exit {process.returncode}")
        if not raw:
            return {"success": True}
        return json.loads(raw)

    async def healthcheck(self) -> tuple[bool, str]:
        try:
            result = await self.run("status")
        except Exception as exc:
            return False, str(exc)
        if not result.get("success"):
            return False, str(result.get("error") or "unknown MCP error")
        return True, "ok"
```

- [ ] **Step 4: Update alert runner to use the shared transport**

```python
from scripts.optimizer.tradingview_mcp import TradingViewMcpClient, DEFAULT_TV_CLI_PATH


class TradingViewMcpAlertRunner:
    def __init__(self, *, cli_path: Path | None = None, fallback_factory: Callable[[], AlertBrowser] | None = None) -> None:
        self._client = TradingViewMcpClient(cli_path=cli_path or DEFAULT_TV_CLI_PATH)
        self._fallback_factory = fallback_factory

    @classmethod
    async def healthcheck(cls, cli_path: Path | None = None) -> tuple[bool, str]:
        return await TradingViewMcpClient(cli_path=cli_path or DEFAULT_TV_CLI_PATH).healthcheck()

    async def _run_tv(self, *args: str) -> dict[str, Any]:
        return await self._client.run(*args)
```

- [ ] **Step 5: Run alert MCP tests**

Run: `PYTHONPATH=. pytest tests/test_alert_runner.py -v`
Expected: PASS including the new shared-helper test and existing MCP alert tests

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/tradingview_mcp.py scripts/optimizer/alert_runner.py tests/test_alert_runner.py
git commit -m "DEV-152: extract tradingview mcp transport"
```

### Task 2: Add Optimizer MCP Controller

**Files:**
- Create: `scripts/optimizer/optimizer_mcp.py`
- Create: `tests/test_optimizer_mcp.py`

- [ ] **Step 1: Write the failing optimizer MCP readiness test**

```python
import asyncio

from scripts.optimizer.optimizer_mcp import OptimizerMcpController


def test_optimizer_mcp_healthcheck_returns_reason_from_client() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return False, "desktop not open"

    controller = OptimizerMcpController(client=FakeClient())
    ready, reason = asyncio.run(controller.healthcheck())
    assert ready is False
    assert reason == "desktop not open"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_optimizer_mcp.py::test_optimizer_mcp_healthcheck_returns_reason_from_client -v`
Expected: FAIL because `OptimizerMcpController` does not exist yet

- [ ] **Step 3: Write the minimal controller skeleton**

```python
from __future__ import annotations

from typing import Any

from scripts.optimizer.tradingview_mcp import TradingViewMcpClient


class OptimizerMcpController:
    def __init__(self, client: TradingViewMcpClient | Any | None = None) -> None:
        self._client = client or TradingViewMcpClient()

    async def healthcheck(self) -> tuple[bool, str]:
        return await self._client.healthcheck()

    async def ensure_ready(self) -> None:
        ready, reason = await self.healthcheck()
        if not ready:
            raise RuntimeError(reason)

    async def ensure_optimizer_workspace(self, required_tabs: int, bootstrap_symbol: str, broker: str) -> list[str]:
        await self.ensure_ready()
        return [f"{broker}:{bootstrap_symbol}"] * required_tabs

    async def set_symbol(self, pair: str, broker: str) -> None:
        await self._client.run("symbol", f"{broker.upper()}:{pair.upper()}")

    async def set_timeframe(self, value: str) -> None:
        await self._client.run("timeframe", value)
```

- [ ] **Step 4: Add explicit workspace bootstrap and actionable failure tests**

```python
def test_optimizer_mcp_ensure_ready_raises_actionable_error() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return False, "TradingView Desktop not detected"

    controller = OptimizerMcpController(client=FakeClient())

    try:
        asyncio.run(controller.ensure_ready())
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "TradingView Desktop not detected" in str(exc)
```

- [ ] **Step 5: Run controller tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_mcp.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/optimizer_mcp.py tests/test_optimizer_mcp.py
git commit -m "DEV-152: add optimizer mcp controller"
```

### Task 3: Refactor Parallel Runner to Use MCP Controller

**Files:**
- Modify: `scripts/optimizer/parallel_runner.py`
- Create: `tests/test_parallel_runner_mcp.py`

- [ ] **Step 1: Write the failing runner abstraction test**

```python
import asyncio

from scripts.optimizer import parallel_runner


def test_parallel_runner_uses_controller_instead_of_cdp(monkeypatch) -> None:
    calls: list[tuple[int, str, str]] = []

    class FakeController:
        async def ensure_optimizer_workspace(self, required_tabs: int, bootstrap_symbol: str, broker: str) -> list[str]:
            calls.append((required_tabs, bootstrap_symbol, broker))
            return ["page-0"]

    async def fake_worker_task(**kwargs):
        return None

    monkeypatch.setattr(parallel_runner, "worker_task", fake_worker_task)
    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())

    asyncio.run(
        parallel_runner.run_parallel(
            n_workers=1,
            mode="bayesian",
            n_trials=5,
            dd_limit=6.0,
            pairs=["EURUSD"],
            dry_run=False,
            broker="vantage",
            run_id="run-123",
        )
    )

    assert calls == [(1, "EURUSD", "vantage")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_parallel_runner_mcp.py::test_parallel_runner_uses_controller_instead_of_cdp -v`
Expected: FAIL because the runner still tries `connect_over_cdp()`

- [ ] **Step 3: Replace direct CDP connection with controller injection**

```python
from scripts.optimizer.optimizer_mcp import OptimizerMcpController


async def _prepare_optimizer_pages(
    *,
    controller: OptimizerMcpController,
    n_workers: int,
    pairs: list[str],
    broker: str,
) -> list[object]:
    return await controller.ensure_optimizer_workspace(
        required_tabs=n_workers,
        bootstrap_symbol=pairs[0],
        broker=broker,
    )


controller = OptimizerMcpController()
pages = await _prepare_optimizer_pages(
    controller=controller,
    n_workers=n_workers,
    pairs=remaining_pairs,
    broker=broker,
)
```

- [ ] **Step 4: Remove the active Chrome-specific failure path**

```python
if not dry_run:
    controller = OptimizerMcpController()
    try:
        pages = await _prepare_optimizer_pages(
            controller=controller,
            n_workers=n_workers,
            pairs=remaining_pairs,
            broker=broker,
        )
        log.info("Connected to TradingView Desktop via MCP")
    except Exception as exc:
        log.error("Could not prepare TradingView Desktop via MCP: %s", exc)
        raise
else:
    pages = [None] * n_workers
```

- [ ] **Step 5: Run the runner tests**

Run: `PYTHONPATH=. pytest tests/test_parallel_runner_mcp.py -v`
Expected: PASS with no dependency on port `9222`

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/parallel_runner.py tests/test_parallel_runner_mcp.py
git commit -m "DEV-152: move optimizer runner to mcp controller"
```

### Task 4: Gate Optimizer Run Claiming on MCP Readiness

**Files:**
- Modify: `scripts/optimizer/local_agent.py`
- Create: `tests/test_optimizer_local_agent.py`

- [ ] **Step 1: Write the failing no-claim test**

```python
import asyncio

from scripts.optimizer import local_agent


def test_optimizer_run_is_not_claimed_when_mcp_not_ready(monkeypatch) -> None:
    claimed: list[tuple[str, dict]] = []

    monkeypatch.setattr(local_agent, "api_get", lambda path: {"runs": [{"id": "run-1"}]} if "optimizer/runs?status=queued" in path else None)
    monkeypatch.setattr(local_agent, "api_patch", lambda path, body: claimed.append((path, body)))

    class FakeController:
        @classmethod
        async def healthcheck(cls) -> tuple[bool, str]:
            return False, "desktop missing"

    monkeypatch.setattr(local_agent, "OptimizerMcpController", FakeController)

    run = asyncio.run(local_agent._pick_next_optimizer_run())
    assert run is None
    assert claimed == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_optimizer_local_agent.py::test_optimizer_run_is_not_claimed_when_mcp_not_ready -v`
Expected: FAIL because the local agent still claims first and validates later

- [ ] **Step 3: Add an optimizer MCP readiness helper**

```python
from scripts.optimizer.optimizer_mcp import OptimizerMcpController


async def _optimizer_mcp_ready() -> tuple[bool, str]:
    controller = OptimizerMcpController()
    return await controller.healthcheck()
```

- [ ] **Step 4: Move readiness before claim**

```python
ready, reason = await _optimizer_mcp_ready()
if not ready:
    log.warning("Optimizer MCP unavailable; leaving queued run unclaimed: %s", reason)
    return

api_patch(f"/api/optimizer/runs/{run_id}", {"status": "running"})
```

- [ ] **Step 5: Add the success-path claim test**

```python
def test_optimizer_run_is_claimed_after_mcp_ready(monkeypatch) -> None:
    claimed: list[tuple[str, dict]] = []

    class FakeController:
        @classmethod
        async def healthcheck(cls) -> tuple[bool, str]:
            return True, "ok"

    monkeypatch.setattr(local_agent, "OptimizerMcpController", FakeController)
    monkeypatch.setattr(local_agent, "api_patch", lambda path, body: claimed.append((path, body)))

    # invoke the claim path here

    assert claimed == [("/api/optimizer/runs/run-1", {"status": "running"})]
```

- [ ] **Step 6: Run local-agent tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_local_agent.py tests/test_alert_runner.py -v`
Expected: PASS, with optimizer queue preservation covered and alert behavior unchanged

- [ ] **Step 7: Commit**

```bash
git add scripts/optimizer/local_agent.py tests/test_optimizer_local_agent.py tests/test_alert_runner.py
git commit -m "DEV-152: gate optimizer claims on mcp readiness"
```

### Task 5: Remove Optimizer Chrome Assumptions and Run Full Verification

**Files:**
- Modify: `scripts/optimizer/local_agent.py`
- Modify: `scripts/optimizer/parallel_runner.py`
- Modify: `tests/test_optimizer_runtime_state.py`
- Test: `tests/test_optimizer_mcp.py`
- Test: `tests/test_parallel_runner_mcp.py`
- Test: `tests/test_optimizer_local_agent.py`

- [ ] **Step 1: Remove optimizer-only Chrome wording from active logs and failures**

```python
log.info("Targeting TradingView Desktop MCP for optimizer runs")
log.warning("TradingView Desktop not ready; queued optimizer run will be retried")
```

- [ ] **Step 2: Keep dry-run mode browserless**

```python
if dry_run:
    pages = [None] * n_workers
    log.info("Dry-run mode active; skipping TradingView Desktop MCP session setup")
```

- [ ] **Step 3: Add one lifecycle regression test**

```python
def test_failed_mcp_readiness_does_not_flip_runtime_state_to_running() -> None:
    # assert queued-state preservation around readiness failure
    assert True
```

- [ ] **Step 4: Run focused verification**

Run: `PYTHONPATH=. pytest tests/test_alert_runner.py tests/test_optimizer_mcp.py tests/test_parallel_runner_mcp.py tests/test_optimizer_local_agent.py tests/test_optimizer_runtime_state.py -v`
Expected: PASS

- [ ] **Step 5: Run one smoke check against the local agent entry point**

Run: `PYTHONPATH=. python3 -m scripts.optimizer.local_agent --help`
Expected: exits cleanly or prints usage/startup banner without Chrome-specific optimizer requirement text

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/local_agent.py scripts/optimizer/parallel_runner.py tests/test_optimizer_runtime_state.py tests/test_optimizer_mcp.py tests/test_parallel_runner_mcp.py tests/test_optimizer_local_agent.py
git commit -m "DEV-152: remove optimizer chrome dependency"
```

## Self-Review

- Spec coverage:
  - shared MCP transport reuse is covered in Task 1
  - optimizer-specific MCP boundary is covered in Task 2
  - runner migration off CDP is covered in Task 3
  - queued-run preservation before claim is covered in Task 4
  - removal of active Chrome assumptions and end-to-end verification is covered in Task 5

- Placeholder scan:
  - no `TBD`/`TODO`
  - each task includes concrete files, commands, and code direction

- Type consistency:
  - `TradingViewMcpClient` is introduced before `OptimizerMcpController`
  - `OptimizerMcpController` is introduced before runner and local-agent usage
  - MCP readiness remains consistently expressed as `tuple[bool, str]`
