# DEV-200 Optimizer Worker Expansion Fail-Fast Design

## Summary

Change optimizer workspace provisioning so the local agent and MCP runner always try to create the full requested worker count instead of downgrading to currently visible TradingView chart tabs. If TradingView Desktop keeps returning Supercharts/new-tab shell pages and those shells cannot be promoted into real chart tabs after bounded retries, the run must fail instead of silently shrinking to fewer workers.

## Why This Is Needed

The current behavior downgrades a requested multi-worker run to the number of currently visible MCP chart tabs. That protects against tab floods, but it breaks the intended operator workflow:

- a run requesting `10` workers is expected to expand the workspace to `10`
- the current downgrade hides tab-creation problems by continuing with `1`
- the operator explicitly prefers full requested parallelism or a hard failure

So the system should no longer reinterpret "requested workers" as "best effort."

## Goals

- Preserve the requested optimizer worker count whenever TradingView Desktop can provision the missing tabs.
- Retry shell-tab promotion in a bounded way when Desktop opens intermediate Supercharts/new-tab shells.
- Fail the run if the requested chart-tab count cannot be reached after bounded retries.
- Remove automatic worker downgrades caused by current visible MCP tab count.
- Keep logs and run events explicit about retries, failures, and final worker count.

## Non-Goals

- No changes to optimization math, scoring, or strategy logic.
- No changes to alert setup flow.
- No fallback to a partial worker count after provisioning failure.
- No attempt to auto-close junk tabs in this task.

## Product Decision

Approved behavior:

- Requested worker count is authoritative.
- Missing tabs should be created.
- Shell/new-tab promotion should be retried a bounded number of times.
- If retries are exhausted and the requested real chart-tab count is still not available, fail the run.
- Do not downgrade to a smaller worker count.

## Current Problem

Two different places currently interfere with the approved behavior:

1. Local-agent preflight inspects current MCP-visible tabs and may downgrade the run before the runner starts.
2. Workspace expansion treats shell/new-tab instability defensively and can collapse to a smaller usable workspace instead of failing the run.

That means the system can run at a lower worker count than requested, which is now explicitly unwanted.

## New System Shape

### Local agent

The local agent should:

- validate Desktop/MCP readiness
- avoid interpreting current visible tab count as the final worker count
- launch `parallel_runner` with the requested worker count unchanged

The local agent may still block a run if Desktop/MCP is unavailable, but it should not proactively shrink the run merely because only one chart tab is currently visible.

### Workspace allocator

`OptimizerMcpController.ensure_optimizer_workspace(...)` should:

- start from currently reusable chart tabs
- create the missing number of tabs needed to reach the requested worker count
- treat shell/new-tab pages as an intermediate state, not a successful provision
- retry promotion of shell tabs into real chart tabs with a bounded retry budget
- raise a hard failure if the requested chart count is still not reached

### Parallel runner

`parallel_runner.py` should:

- request the full worker count from the workspace allocator
- treat allocator failure as a run failure
- stop clamping worker tasks down to the number of prepared sessions

If fewer sessions are prepared than requested, that is an allocator failure, not a runtime downgrade condition.

## Retry Policy

Recommended default:

- `3` promotion attempts per missing requested tab

Each attempt should:

1. create a new TradingView tab via MCP
2. detect whether it appears as a real chart tab or a shell/new-tab page
3. if a shell appears, attempt chart bootstrap/promotion
4. if promotion fails, retry until the per-tab attempt budget is exhausted

After the retry budget is exhausted for any still-missing slot, the allocator should fail with an actionable error.

## Failure Semantics

If the requested worker count cannot be satisfied:

- do not downgrade
- do not continue with partial workspace
- fail the run
- emit a precise reason in logs and run events

Example failure shape:

- requested workers: `10`
- reusable chart tabs: `1`
- attempted to create `9` more
- shell promotion failed after `3` retries for missing tab `2`
- run failed because requested workspace could not be prepared

## Logging Requirements

The system should log:

- requested worker count
- current reusable chart count
- each expansion retry attempt
- shell promotion failures with attempt counts
- final hard failure reason

It should no longer log a downgrade message based on current visible tabs.

## Testing Strategy

### Local agent tests

- preflight does not downgrade when only one chart tab is visible
- preflight still blocks when Desktop/MCP is unavailable
- launched optimizer command preserves requested `--workers`

### MCP workspace tests

- successful expansion from `1` reusable chart tab to requested worker count
- shell/new-tab promotion that succeeds on retry
- repeated shell/new-tab promotion failures that raise a hard error
- no partial-success return when requested worker count is not met

### Parallel runner tests

- runner preserves requested worker count
- runner fails when workspace allocator cannot prepare the requested number of sessions
- runner does not clamp worker tasks to a smaller prepared session count

## Main Risk

The main risk is reintroducing visible tab churn when TradingView Desktop is unstable. That risk is acceptable here because the product decision is explicit: full requested parallelism or failure, not silent downgrade.

Mitigation:

- keep retries bounded
- fail fast once the retry budget is exhausted
- log the exact shell-promotion failure so the operator can diagnose Desktop instability quickly

## Implementation Outcome

After this task:

- a `10`-worker run will try to create the missing `9` chart tabs
- shell/new-tab pages will be retried in a bounded way
- repeated workspace expansion failure will fail the run
- silent worker downgrades based on current tab visibility will be removed
