# DEV-157 Optimizer Desktop MCP Runner Plan

> Execute staged. Keep `dry_run` unchanged while migrating live Desktop runs away from Playwright browser attach.

## Goal

Replace the live optimizer runner’s Playwright browser attach path with an MCP-only TradingView Desktop execution boundary.

## Files

- Modify: `scripts/optimizer/parallel_runner.py`
- Modify: `scripts/optimizer/tab_worker.py`
- Modify: `scripts/optimizer/optimizer.py`
- Modify: `scripts/optimizer/optimizer_mcp.py`
- Create or modify tests under:
  - `tests/test_parallel_runner_mcp.py`
  - `tests/test_optimizer_mcp.py`
  - `tests/test_optimizer_local_agent.py`
  - targeted new worker/controller tests if needed

## Stage 1: Introduce a Live Desktop Session Boundary

- [ ] Define the minimum worker-facing session interface needed by live optimizer runs.
- [ ] Identify which `tab_worker.py` methods are pure orchestration versus raw `Page` manipulation.
- [ ] Move one slice of page-specific logic behind a new Desktop session/controller boundary.
- [ ] Add failing tests first for the new boundary.

Verification:

- `PYTHONPATH=. pytest tests/test_optimizer_mcp.py -v`

## Stage 2: Switch Live Runner Off Browser-Level Playwright Attach

- [ ] Refactor `parallel_runner.py` so live runs do not call `pw.chromium.connect_over_cdp("http://127.0.0.1:9222")`.
- [ ] Construct one live Desktop session per prepared MCP slot instead.
- [ ] Keep `dry_run` exactly as it works today.
- [ ] Preserve runtime-state and structured event behavior.

Verification:

- `PYTHONPATH=. pytest tests/test_parallel_runner_mcp.py -v`

## Stage 3: Remove Remaining Live-Run Playwright Page Coupling

- [ ] Replace remaining live-run `Page` assumptions in `tab_worker.py` / `optimizer.py`.
- [ ] Keep retries, metrics extraction, and result conversion behavior intact.
- [ ] Ensure actionable errors when Desktop state is unusable after claim.

Verification:

- `PYTHONPATH=. pytest tests/test_parallel_runner_mcp.py tests/test_optimizer_mcp.py -v`

## Stage 4: Re-verify Agent Gating

- [ ] Confirm the local agent still leaves runs queued when readiness fails.
- [ ] Confirm successful readiness leads to claim and spawn.
- [ ] Confirm new runner failures surface real Desktop/session causes.

Verification:

- `PYTHONPATH=. pytest tests/test_optimizer_local_agent.py -v`

## Stage 5: Smoke Test

- [ ] Run a small local optimizer smoke test against TradingView Desktop tabs.
- [ ] Confirm:
  - no `connect_over_cdp("http://127.0.0.1:9222")` timeout
  - run moves to `running`
  - worker activity starts

## Notes

- Do not touch trading logic or scoring formulas.
- Do not reintroduce Chrome fallback.
- If the first live Desktop session slice reveals deep `Page` coupling, stop and narrow the next adapter boundary before continuing.
