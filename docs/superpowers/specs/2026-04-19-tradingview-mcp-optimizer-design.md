# DEV-152 TradingView MCP Optimizer Integration Design

## Summary

Switch optimizer runs from Google Chrome CDP automation to the TradingView Desktop app via the existing TradingView MCP integration. The optimizer path should become MCP-only, should not claim queued runs when the desktop app is unavailable, and should reuse the existing MCP interaction style already used by alert deployment.

## Goals

- Remove Google Chrome as a required runtime dependency for optimizer runs.
- Run optimizer automation against the TradingView Desktop app through `mcp/tradingview-mcp`.
- Keep queued optimizer runs unclaimed when MCP/Desktop is unavailable.
- Reuse the existing MCP command transport patterns already present in the optimizer/alert tooling.
- Preserve clear operator logs explaining whether the desktop app is ready, auto-attached, or blocking execution.

## Non-Goals

- No Chrome fallback for optimizer runs.
- No changes to trading strategy logic or optimization math.
- No changes to the alert deployment backend selection in this task.
- No broad rewrite of alert runner internals beyond extracting reusable MCP helpers if needed.
- No new top-level service or daemon outside the current optimizer tooling.

## Existing Context

The current optimizer flow is split across three main files:

- `scripts/optimizer/local_agent.py`
- `scripts/optimizer/parallel_runner.py`
- `scripts/optimizer/alert_runner.py`

Today:

- alert deployment already supports an MCP-backed path through `TradingViewMcpAlertRunner`
- optimizer runs still hard-connect to Chrome via Playwright CDP
- the local agent still manages Chrome lifecycle for optimizer work

This means the product intent and the implementation are currently misaligned. The desired operator experience is TradingView Desktop plus MCP, but optimizer execution still assumes Chrome is the automation target.

## Product Decision

The approved behavior for optimizer runs is:

- backend style: MCP-only
- when MCP/Desktop is unavailable: leave the run queued for retry
- bootstrap behavior: auto-attach or auto-bootstrap through MCP where supported, otherwise log the missing prerequisite clearly

## Proposed System Shape

Introduce a small optimizer-specific desktop control boundary and route all optimizer UI automation through it.

### New shape

1. Local agent polls for queued optimizer runs.
2. Before claiming a run, the agent performs an optimizer MCP readiness check.
3. If MCP/Desktop is not ready:
   - the run is left queued
   - the agent logs the reason
   - no claim occurs
4. If MCP/Desktop is ready:
   - the agent claims the run
   - the runner uses an MCP-backed optimizer controller
   - optimizer tasks interact with TradingView Desktop through MCP commands instead of Chrome CDP

## Component Design

### Local agent responsibilities

`local_agent.py` should:

- stop treating Chrome as the prerequisite for optimizer runs
- perform an MCP health/readiness check for optimizer execution
- attempt lightweight auto-bootstrap if the MCP supports bringing the desktop session into a usable state
- leave the run queued if readiness fails
- emit operator-friendly logs describing:
  - MCP healthy/unhealthy
  - whether Desktop was detected
  - whether the run was skipped for retry instead of claimed

The agent should only claim a run after the optimizer MCP backend is considered ready.

### Optimizer runner responsibilities

`parallel_runner.py` should:

- stop calling `connect_over_cdp()`
- stop depending on port `9222`
- use an injected optimizer controller abstraction for:
  - session readiness
  - chart/tab availability
  - symbol switching
  - timeframe and parameter interaction
  - result collection support

The runner should remain responsible for:

- worker coordination
- retries per pair
- result aggregation
- structured event logging

The runner should not own desktop transport details.

### MCP controller responsibilities

A new optimizer MCP controller should:

- wrap the TradingView MCP CLI interaction pattern
- expose optimizer-safe methods instead of raw command calls
- encapsulate Desktop-specific UI interaction assumptions
- fail with explicit, actionable errors when the app state is not usable

Recommended methods include:

- `healthcheck()`
- `ensure_ready()`
- `ensure_optimizer_workspace(required_tabs, bootstrap_symbol, broker)`
- `set_symbol(pair, broker)`
- `set_timeframe(value)`
- `apply_optimizer_params(params)`
- `read_report_state()`

These names can change during implementation, but the boundary should remain small and purpose-driven.

## Reuse Strategy

The existing MCP integration in `alert_runner.py` should be treated as the starting point for transport patterns, not copied wholesale into the optimizer runner.

Recommended reuse:

- reuse the CLI path discovery
- reuse the subprocess JSON command execution pattern
- reuse general MCP healthcheck conventions
- reuse low-level UI helper patterns where they are generic

Recommended separation:

- alert deployment behaviors stay in `alert_runner.py`
- optimizer-specific desktop control should live in optimizer-focused code

This keeps the boundary understandable and avoids turning `alert_runner.py` into a shared catch-all for unrelated desktop automation logic.

## Queue and Claiming Rules

The claim timing changes are important.

### Current problem

The local agent can claim a run and only fail later when the browser attach step breaks. That burns operator attention and creates noisy failed runs caused by environment readiness instead of optimizer logic.

### New rule

Queued optimizer runs should only be claimed after MCP/Desktop readiness is confirmed.

If readiness fails:

- do not patch the run to `running`
- do not emit a false start
- do not mark the run failed
- leave it in `queued` so the next poll can retry

This treats desktop availability as a local prerequisite, not as a business-level run failure.

## Error Handling

There are two distinct failure classes and they should be handled differently.

### Pre-claim readiness failures

Examples:

- MCP CLI unavailable
- TradingView Desktop app not detected
- MCP healthcheck unhealthy
- required workspace/tabs cannot be prepared

Handling:

- leave run queued
- log locally with the blocking reason
- optionally emit lightweight agent-status diagnostics if that channel already exists

### Post-claim run failures

Examples:

- symbol-specific automation failure
- report parsing failure
- optimizer parameter interaction failure after the run starts

Handling:

- run can move to failed
- runner events should include the real cause
- local logs should show actionable MCP/Desktop context

## Logging and Operator Experience

The operator should be able to tell, from the local terminal alone:

- whether the agent is using MCP for optimizer runs
- whether TradingView Desktop was found and considered ready
- why a queued run was skipped instead of claimed
- when a run moves from queued to running
- whether a failure is environmental or run-specific

Recommended log examples:

- `Optimizer MCP healthy; desktop ready`
- `Optimizer MCP unavailable; leaving queued run unclaimed`
- `TradingView Desktop not ready; retrying on next poll`
- `Claiming queued optimizer run via MCP backend`

## Testing Strategy

Add regression tests for both behavior and control flow.

### Local agent tests

- does not require Chrome for optimizer polling
- leaves queued runs unclaimed when MCP readiness fails
- claims runs only after MCP readiness succeeds
- logs clear reasons when readiness fails

### Parallel runner tests

- uses the optimizer controller abstraction instead of direct CDP attach
- surfaces controller readiness/setup failures clearly
- preserves worker/result orchestration behavior with the new backend boundary

### MCP controller tests

- healthcheck success/failure normalization
- command failure surfaces actionable errors
- workspace readiness logic handles missing app state deterministically

## Rollout Plan

Implement in one task, but in this order:

1. Introduce the optimizer MCP controller boundary.
2. Change `parallel_runner.py` to depend on that controller instead of CDP.
3. Update `local_agent.py` to gate claiming on optimizer MCP readiness.
4. Remove optimizer Chrome management and port assumptions from the active path.
5. Add tests for queued-run preservation and MCP-only execution.

## Risks

### MCP command coverage gaps

The MCP may already support alert workflows well but still be missing one or more optimizer interactions. This is the main implementation risk. The controller boundary should make those gaps obvious instead of burying them in runner logic.

### Desktop state variability

TradingView Desktop may start in a different workspace or chart state than expected. The readiness/bootstrap flow should make the expected state explicit and fail clearly when it cannot be established.

### Over-coupling alert and optimizer code

Reusing transport helpers is good. Folding optimizer logic into `alert_runner.py` is not. The implementation should share low-level MCP patterns without collapsing two different workflows into one oversized module.

## Success Criteria

- A queued optimizer run no longer requires Google Chrome to start.
- The local agent does not claim queued runs unless TradingView Desktop MCP is ready.
- The optimizer runner no longer uses `connect_over_cdp()` or port `9222` in its active execution path.
- The local operator logs clearly state MCP/Desktop readiness and failure reasons.
- Optimizer runs execute through the TradingView Desktop MCP path end-to-end.
