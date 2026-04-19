# DEV-157 Optimizer Desktop MCP Runner Design

## Summary

Refactor live optimizer execution to be MCP-only against TradingView Desktop and remove the runtime dependency on Playwright browser attachment for real runs. Keep `dry_run` on its current lightweight path so we preserve a fast smoke-test mode while replacing the live Desktop execution boundary.

## Why This Is Needed

The current implementation still assumes the optimizer can obtain Playwright `Page` objects from TradingView Desktop after MCP prepares tabs.

That assumption is false in the real runtime:

- TradingView MCP can control Desktop because it attaches to individual chart targets through `chrome-remote-interface`.
- Playwright browser-level `connect_over_cdp("http://127.0.0.1:9222")` times out against TradingView Desktop even though the websocket connects.
- Playwright page-websocket attach succeeds, but does not surface usable existing `Page` objects for the current worker model.

So the remaining blocker is architectural, not operational.

## Goals

- Remove Playwright browser attach from live Desktop optimizer runs.
- Execute live optimizer interactions through MCP-targeted Desktop control only.
- Preserve current queue behavior:
  - leave runs queued when Desktop/MCP readiness fails
  - claim only after readiness succeeds
- Keep `dry_run` working without Desktop requirements.
- Preserve structured optimizer events, run lifecycle, and result aggregation.

## Non-Goals

- No Chrome fallback.
- No changes to optimization math, scoring, or strategy logic.
- No rewrite of alert deployment.
- No broad frontend changes in this task.

## Product Decision

Approved behavior:

- live runs: MCP-only
- `dry_run`: keep lightweight current path
- unavailable Desktop/MCP: do not claim the run

## Current Constraint

Today the optimizer is built around Playwright `Page` objects:

- `scripts/optimizer/parallel_runner.py`
- `scripts/optimizer/tab_worker.py`
- `scripts/optimizer/optimizer.py`

That makes the live runner depend on a browser abstraction that TradingView Desktop does not provide reliably through Playwright.

## New System Shape

### Live Desktop path

1. Local agent confirms MCP/Desktop readiness and sufficient chart tabs.
2. Runner receives prepared MCP workspace slots.
3. Runner creates one Desktop execution handle per slot using MCP/target-level CDP primitives.
4. Workers drive optimizer actions through a Desktop controller interface instead of a Playwright `Page`.
5. Results are collected and persisted through the existing runtime/report flow.

### Dry-run path

Keep the existing browserless behavior unchanged.

## Component Design

### Desktop execution controller

Introduce an optimizer-focused controller that represents a single prepared TradingView Desktop tab.

Responsibilities:

- bind to one prepared MCP workspace slot
- switch symbol/timeframe on that slot
- apply optimizer parameters
- trigger report updates
- wait for recalculation to finish
- read strategy metrics

This controller should hide MCP command mechanics from worker code.

### Worker boundary

Refactor worker code so it depends on an abstract tab/session interface rather than Playwright `Page`.

Minimum capabilities:

- `set_symbol(...)`
- `apply_params(...)`
- `update_report(...)`
- `collect_metrics(...)`
- `reset_or_recover(...)`

The worker remains responsible for:

- retry policy
- per-pair structured events
- conversion of raw metrics into `BacktestResult`

### Parallel runner

`parallel_runner.py` should:

- stop calling Playwright `connect_over_cdp()` for live runs
- ask `OptimizerMcpController` for prepared slots
- construct one live Desktop session per slot
- pass those sessions into workers
- keep `dry_run` unchanged

### MCP transport reuse

Reuse the existing shared transport in `scripts/optimizer/tradingview_mcp.py` and the optimizer readiness logic in `scripts/optimizer/optimizer_mcp.py`.

Do not introduce a second transport stack.

## Migration Strategy

Use a staged migration.

### Stage 1

Add a Desktop session abstraction and a worker adapter that can operate without Playwright for a minimal set of actions.

### Stage 2

Move live runner execution to the new Desktop session path while keeping `dry_run` unchanged.

### Stage 3

Remove remaining live-run Playwright assumptions from worker/optimizer internals.

## Error Handling

### Pre-claim failures

- MCP unavailable
- insufficient tabs
- slot preparation failure

Handling:

- leave run queued
- log actionable reason

### Post-claim failures

- Desktop session action fails
- metrics parsing fails
- report never updates

Handling:

- mark run failed
- log specific Desktop/session cause

## Testing Strategy

### Runner tests

- live path no longer calls Playwright browser attach
- `dry_run` path remains unchanged
- runner constructs one Desktop session per prepared slot

### Worker/controller tests

- parameter application retry behavior
- report update waiting
- metric parsing and `BacktestResult` conversion
- actionable session errors

### Agent tests

- queued-run gating behavior remains unchanged

## Main Risk

The largest risk is hidden coupling inside `tab_worker.py` and `optimizer.py`, where some logic may be more page-specific than it first appears.

Mitigation:

- move one capability at a time behind the new Desktop session boundary
- keep `dry_run` intact as a stable verification mode
- verify targeted tests after each slice

## Implementation Outcome

After this task:

- real optimizer runs no longer depend on Playwright CDP browser attach
- Desktop tabs are controlled through MCP-native primitives
- queueing behavior stays operator-friendly
- `dry_run` remains available for fast validation
