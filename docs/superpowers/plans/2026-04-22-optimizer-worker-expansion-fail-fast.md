# Optimizer Worker Expansion Fail-Fast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make optimizer runs preserve the requested worker count by expanding TradingView tabs to the target size, and fail the run after bounded shell-tab promotion retries instead of downgrading to fewer workers.

**Architecture:** Keep the local agent preflight read-only for Desktop/MCP health, but remove the worker-downgrade fallback. Move the hard contract into MCP workspace provisioning: create the missing tabs, retry shell-tab promotion up to a fixed budget, and raise if the requested chart-tab count is still not met. The parallel runner then treats allocator failure as a normal run failure path instead of clamping worker tasks.

**Tech Stack:** Python 3.11, asyncio, pytest, TradingView Desktop MCP control

---

### Task 1: Remove Worker Downgrade From Local Agent

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/local_agent.py`
- Test: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_optimizer_local_agent.py`

- [ ] **Step 1: Write the failing local-agent test for “preserve requested workers”**

Add/replace the downgrade-focused assertion with a test that proves the spawned command keeps the requested worker count:

```python
def test_execute_run_preserves_requested_workers_when_mcp_is_ready(local_agent, monkeypatch):
    patch_calls, post_calls, get_calls = _capture_http_calls(local_agent, monkeypatch)
    monkeypatch.setattr(local_agent, "_playwright_available", lambda: True)

    async def fake_ready(workers: int) -> tuple[bool, str]:
        assert workers == 10
        return True, ""

    monkeypatch.setattr(local_agent, "_ensure_optimizer_run_ready", fake_ready)
    monkeypatch.setattr(
        local_agent,
        "_available_optimizer_worker_count",
        mock.AsyncMock(return_value=1),
    )

    process = _FakeProcess(exit_code=0)
    popen = mock.Mock(return_value=process)
    monkeypatch.setattr(local_agent.subprocess, "Popen", popen)
    monkeypatch.setattr(local_agent, "_stream_and_report", lambda run_id, proc: None)

    local_agent.execute_run(
        {
            "id": "run-preserve",
            "mode": "bayesian",
            "workers": 10,
            "pairs": ["EURUSD", "GBPUSD"],
            "n_trials": 10,
            "dd_limit": 8.0,
            "dry_run": False,
            "broker": "fxcm",
        }
    )

    command = popen.call_args.args[0]
    assert command[command.index("--workers") + 1] == "10"
    assert not any(
        path == "/api/optimizer/runs/run-preserve/events"
        and body["payload"].get("message", "").startswith("Downgrading workers")
        for path, body in post_calls
    )
```

- [ ] **Step 2: Run the focused local-agent suite and confirm the old downgrade behavior fails**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_optimizer_local_agent.py -q
```

Expected:

```text
FAIL ... expected workers to stay at 10 / downgrade event still emitted
```

- [ ] **Step 3: Remove downgrade fallback from `execute_run()`**

Update the non-dry-run branch in `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/local_agent.py` so readiness failure blocks the run, but “available tabs < requested workers” no longer rewrites `workers`.

Target shape:

```python
if not dry_run:
    ready, reason = asyncio.run(_ensure_optimizer_run_ready(workers))
    if not ready:
        _report_optimizer_run_blocked(run_id, reason, workers=workers, dry_run=dry_run)
        return
```

Also keep `_ensure_optimizer_run_ready()` read-only:

```python
controller = OptimizerMcpController()
await controller.ensure_ready()
tabs = await controller._list_workspace_tabs()
if len(tabs) < workers:
    return False, f"TradingView MCP currently exposes {len(tabs)} tab(s); requested {workers}"
return True, ""
```

- [ ] **Step 4: Run the focused local-agent suite and verify it passes**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_optimizer_local_agent.py -q
```

Expected:

```text
... all tests pass ...
```

- [ ] **Step 5: Commit**

```bash
git add scripts/optimizer/local_agent.py tests/test_optimizer_local_agent.py
git commit -m "DEV-200: remove optimizer worker downgrade"
```

### Task 2: Make MCP Workspace Expansion Reach Requested Tabs Or Fail

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/optimizer_mcp.py`
- Test: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_optimizer_mcp.py`

- [ ] **Step 1: Write the failing MCP test for bounded retries then hard failure**

Add a test that starts with one reusable chart tab, repeatedly returns shell tabs, and expects `ensure_optimizer_workspace(required_tabs=3, ...)` to raise instead of returning one slot:

```python
def test_optimizer_mcp_workspace_fails_when_requested_chart_count_is_not_met(monkeypatch) -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, object]:
            if args == ("tab", "list"):
                return {
                    "success": True,
                    "tab_count": 1,
                    "page_target_count": 1,
                    "tabs": [
                        {
                            "index": 0,
                            "id": "chart-1",
                            "title": "TradingView",
                            "url": "https://www.tradingview.com/chart/AAA/",
                            "chart_id": "AAA",
                        }
                    ],
                }
            if args == ("tab", "new"):
                return {"success": True, "action": "new_tab_opened"}
            return {"success": True}

    controller = OptimizerMcpController(client=FakeClient())

    async def fake_list_workspace_pages() -> list[dict[str, object]]:
        return [
            {
                "index": 1,
                "id": "shell-x",
                "title": "New tab",
                "url": "file:///Applications/TradingView.app/Contents/Resources/app.asar/app/new-tab/index.html",
                "chart_id": None,
                "kind": "new_tab",
            }
        ]

    async def fake_promote_new_tab_to_chart(**kwargs):
        raise RuntimeError("TradingView new-tab shell did not become a chart tab after bootstrap navigation")

    monkeypatch.setattr(controller, "_list_workspace_pages", fake_list_workspace_pages)
    monkeypatch.setattr(controller, "_promote_new_tab_to_chart", fake_promote_new_tab_to_chart)

    with pytest.raises(RuntimeError):
        asyncio.run(
            controller.ensure_optimizer_workspace(
                required_tabs=3,
                bootstrap_symbol="EURUSD",
                broker="fxcm",
                bootstrap_timeframe="5m",
            )
        )
```

- [ ] **Step 2: Run the focused MCP suite and confirm the current partial-success behavior fails the new expectation**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_optimizer_mcp.py -q
```

Expected:

```text
FAIL ... ensure_optimizer_workspace returned fewer tabs instead of raising
```

- [ ] **Step 3: Implement bounded retry expansion in `optimizer_mcp.py`**

Add a retry constant near the controller constants:

```python
_WORKSPACE_EXPANSION_RETRIES_PER_MISSING_TAB = 3
```

Then refactor `ensure_optimizer_workspace()` so it:

```python
missing_tabs = max(required_tabs - len(reusable_tabs), 0)

for missing_index in range(missing_tabs):
    promoted_tab = None
    last_error = None

    for attempt in range(self._WORKSPACE_EXPANSION_RETRIES_PER_MISSING_TAB):
        await self._run_command("tab new", "tab", "new")
        fresh_page = await self._wait_for_new_workspace_page(known_page_ids=known_page_ids)
        known_page_ids.add(self._tab_id(fresh_page))

        if fresh_page.get("kind") == "chart":
            promoted_tab = fresh_page
            break

        try:
            promoted_tab = await self._promote_new_tab_to_chart(
                shell_tab=fresh_page,
                bootstrap_chart_id=bootstrap_chart_id,
                bootstrap_symbol=bootstrap_symbol,
                broker=broker,
                known_chart_ids=known_tab_ids,
                known_page_ids=known_page_ids,
            )
            known_page_ids.add(self._tab_id(promoted_tab))
            break
        except RuntimeError as exc:
            last_error = exc

    if promoted_tab is None:
        raise RuntimeError(
            f"Failed to provision requested TradingView chart tab {len(reusable_tabs) + len(fresh_tabs) + 1}/{required_tabs}: {last_error}"
        )

    fresh_tabs.append(promoted_tab)
    known_tab_ids.add(self._tab_id(promoted_tab))

if len(reusable_tabs) + len(fresh_tabs) != required_tabs:
    raise RuntimeError(
        f"Requested {required_tabs} TradingView chart tab(s) but only prepared {len(reusable_tabs) + len(fresh_tabs)}"
    )
```

- [ ] **Step 4: Update/replace MCP tests to match “expand or fail”**

Keep tests for:

```python
assert [slot.tab_id for slot in workspace] == ["tab-1", "tab-2", "tab-3"]
assert [slot.chart_id for slot in workspace] == ["AAA", "BBB", "CCC"]
```

Replace any test expecting a partial one-slot return after shell-promotion failure with a hard-failure expectation:

```python
with pytest.raises(RuntimeError) as exc_info:
    asyncio.run(controller.ensure_optimizer_workspace(...))
assert "Failed to provision requested TradingView chart tab" in str(exc_info.value)
```

- [ ] **Step 5: Run the focused MCP suite and verify it passes**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_optimizer_mcp.py -q
```

Expected:

```text
... all tests pass ...
```

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/optimizer_mcp.py tests/test_optimizer_mcp.py
git commit -m "DEV-200: fail optimizer workspace expansion"
```

### Task 3: Remove Parallel Runner Clamping And Treat Under-Provisioning As Failure

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/parallel_runner.py`
- Test: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_parallel_runner_mcp.py`

- [ ] **Step 1: Write the failing runner test for “no clamp on under-provisioned sessions”**

Add a test that returns one prepared slot for a three-worker request and expects `run_parallel(...)` to raise:

```python
def test_run_parallel_fails_when_workspace_slots_do_not_match_requested_workers(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(
        parallel_runner,
        "results_file_for_broker",
        lambda broker, results_label=None: tmp_path / "parallel_results.json",
    )
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: 4321)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    class FakeController:
        async def ensure_optimizer_workspace(self, **kwargs):
            return [OptimizerWorkspaceSlot(index=0, tab_id="tab-a", chart_id="AAA")]

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())

    with pytest.raises(RuntimeError):
        asyncio.run(
            parallel_runner.run_parallel(
                pairs=["EURUSD", "GBPUSD"],
                n_workers=3,
                mode="bayesian",
                n_trials=1,
                dd_limit=10.0,
                dry_run=False,
                broker="vantage",
            )
        )
```

- [ ] **Step 2: Run the focused runner suite and confirm the existing clamp behavior fails**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_parallel_runner_mcp.py -q
```

Expected:

```text
FAIL ... runner continued with 1 worker instead of raising
```

- [ ] **Step 3: Remove the clamp in `parallel_runner.py` and enforce exact session count**

Replace the current post-allocation clamp with an exact-count guard:

```python
workspace_slots = await controller.ensure_optimizer_workspace(
    required_tabs=n_workers,
    bootstrap_symbol=remaining_pairs[0],
    broker=broker,
)
pages = _prepare_mcp_backed_pages(workspace_slots)
if len(pages) != n_workers:
    raise RuntimeError(
        f"Requested {n_workers} TradingView Desktop MCP session(s) but prepared {len(pages)}"
    )
log.info("Prepared %d TradingView Desktop MCP session(s)", len(pages))
```

- [ ] **Step 4: Update runner tests to expect failure instead of clamping**

Keep the happy-path assignment test:

```python
assert worker_pages == [
    (0, "tab-a", "https://www.tradingview.com/chart/AAA/"),
    (1, "tab-b", "https://www.tradingview.com/chart/BBB/"),
]
```

Replace the clamp test with:

```python
with pytest.raises(RuntimeError) as exc_info:
    asyncio.run(parallel_runner.run_parallel(...))
assert "Requested 3 TradingView Desktop MCP session(s) but prepared 1" in str(exc_info.value)
```

- [ ] **Step 5: Run the focused runner suite and verify it passes**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_parallel_runner_mcp.py -q
```

Expected:

```text
... all tests pass ...
```

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/parallel_runner.py tests/test_parallel_runner_mcp.py
git commit -m "DEV-200: enforce requested optimizer sessions"
```

### Task 4: Run Combined Verification

**Files:**
- Verify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_optimizer_local_agent.py`
- Verify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_optimizer_mcp.py`
- Verify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_parallel_runner_mcp.py`

- [ ] **Step 1: Run the combined focused suite**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest \
  tests/test_optimizer_local_agent.py \
  tests/test_optimizer_mcp.py \
  tests/test_parallel_runner_mcp.py -q
```

Expected:

```text
all targeted optimizer worker-expansion tests pass
```

- [ ] **Step 2: Run one live smoke command manually after code changes**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. python -m scripts.optimizer.parallel_runner \
  --workers 10 \
  --mode bayesian \
  --trials 1 \
  --dd-limit 8.0 \
  --pairs EURUSD \
  --broker fxcm \
  --backtest-range 365d \
  --results-label dev200_smoke
```

Expected:

```text
either:
- 10 MCP sessions prepared successfully
or:
- a hard failure explaining which requested chart tab could not be provisioned
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-04-22-optimizer-worker-expansion-fail-fast.md
git commit -m "DEV-200: add worker expansion fail-fast plan"
```
