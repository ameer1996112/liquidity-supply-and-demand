# Optimizer Watchdog and Fresh-Read Hardening

## Summary
Harden the TradingView optimizer so it stops trusting stale tab reads, emits machine-readable health status, and can be restarted automatically on macOS when it gets stuck.

This design intentionally treats a bad or mixed run as untrustworthy. When the watchdog decides the run is unhealthy, it archives the old run and starts a completely fresh run from trial 1 with cleared optimizer results.

## Goals
- Prevent stale TradingView reads from poisoning Bayesian optimization.
- Add a machine-readable status file that represents real optimizer health.
- Add an automatic watchdog that detects stalled runs and restarts them.
- Restart from a clean slate rather than resuming mixed or suspect results.
- Keep existing human-readable logs while adding structured per-worker event logs.

## Non-Goals
- Exact in-flight Bayesian resume.
- Reusing completed pairs from a stale or mixed run.
- Scaling concurrency beyond the current worker-per-tab model.
- Changing trading strategy logic or optimizer scoring philosophy.

## Approved Decisions
- Restart policy: clean restart from the beginning, not resume.
- Stuck threshold: 12 minutes with no healthy progress.
- Recovery action: restart Chrome as well as the optimizer process.
- Scheduler: launchd first on macOS, with cron as an optional fallback.
- Health source of truth: status file and structured worker events, not the mixed console log.

## Problems Being Solved

### 1. Mixed shared logs
The current parallel optimizer writes all worker output into one shared console stream and one shared `run_*.log`. That makes trial lines hard to trust because multiple workers can interleave text in the same file.

### 2. Stale read acceptance
The current worker logic can continue after a parameter apply did not clearly produce a fresh TradingView recalculation. Unchanged result hashes are logged as warnings, but the final retry still falls through as a successful apply. This allows stale metrics to be fed back into the Bayesian study.

### 3. Weak restartability
The current checkpointing only preserves completed pairs. If a live run stalls overnight, there is no reliable health heartbeat or supervisor that can decide when to restart the job safely.

## Design Overview
The optimizer will gain three new capabilities:

1. A machine-readable run status file that tracks health and current activity.
2. Structured per-worker event logs that record trial freshness and worker state.
3. A watchdog process that monitors the run status and performs a full clean restart when the run becomes stale.

## Architecture

### Run Status File
At optimizer start, create a new run status JSON file under:

`/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimization_results/`

Recommended filename pattern:

`optimizer_status_<run_id>.json`

Also maintain a stable pointer file:

`optimizer_status_current.json`

The status file is the source of truth for watchdog health checks.

### Status File Fields
Minimum fields:

```json
{
  "run_id": "20260413_010000",
  "state": "starting",
  "started_at": "2026-04-13T01:00:00+03:00",
  "last_progress_at": "2026-04-13T01:00:00+03:00",
  "stuck_threshold_seconds": 720,
  "restart_count": 0,
  "optimizer_pid": 12345,
  "chrome_pid": 45678,
  "log_file": "scripts/optimization_results/run_20260413_010000.log",
  "mode": "bayesian",
  "workers": 6,
  "args": ["--parallel", "--workers", "6", "--bayesian"],
  "active_pairs": {
    "worker-0": {
      "symbol": "EURJPY",
      "trial": 46,
      "last_event_at": "2026-04-13T01:12:10+03:00",
      "status": "running"
    }
  },
  "worker_health": {
    "worker-0": {
      "status": "healthy",
      "stale_reads": 0,
      "last_results_hash": "abcd1234"
    }
  }
}
```

### Worker Event Logs
Add one structured JSONL file per worker, for example:

`optimizer_worker_0_<run_id>.jsonl`

Each line is a single event. Recommended event types:
- `worker_started`
- `pair_started`
- `trial_completed`
- `trial_stale`
- `trial_timeout`
- `apply_failed`
- `pair_completed`
- `worker_unhealthy`
- `run_completed`

For trial events, include:
- run id
- worker id
- symbol
- trial number
- params hash
- results hash before
- results hash after
- outcome: `fresh`, `stale`, `timed_out`, `apply_failed`
- key metrics if fresh

These logs are for diagnosis and auditability. The watchdog can read them if needed, but the primary health check should rely on the status file.

## Healthy Progress Rules
The optimizer should update `last_progress_at` only when meaningful forward progress occurs:
- a worker starts a pair
- a fresh trial result is recorded
- a pair completes
- the full run completes

Warnings alone do not count as progress.

Stale reads, timeout retries, and unchanged result hashes do not refresh the heartbeat.

## Freshness Hardening

### Required Behavior
After parameters are applied on a TradingView tab:
- if the worker never sees a convincing update cycle and the final result hash is unchanged, the apply is considered a failure
- if the worker cannot confirm the expected symbol before reading results, the read is rejected
- if repeated stale reads happen on the same worker tab, that worker is marked unhealthy in the status file

### Trial Acceptance Rules
A trial is valid only when:
- the expected symbol matches the tab being read
- the post-apply result hash differs from the pre-apply result hash
- the Strategy Tester metrics were read successfully

If any of those checks fail:
- the trial is not treated as a successful result
- the event is recorded as stale or failed
- the Bayesian study receives a failure score path rather than a fresh metric result

### Best Result Rules
Only fresh trial results are allowed to:
- update the pair best result
- update the compliant best result
- update heartbeat progress for the current worker

This ensures stale reads cannot silently become the “best” output for a pair.

## Watchdog Design

### Purpose
The watchdog is a separate process that checks whether the optimizer is still making progress.

### Check Frequency
Run every 2 minutes.

### Stuck Definition
If:

`now - last_progress_at > 12 minutes`

then the run is considered stuck.

### Restart Flow
When the watchdog detects a stuck run:
1. Mark the current status file state as `stuck`.
2. Write an archive record to a restart-history file.
3. Kill the optimizer process if it is still running.
4. Restart Chrome with the optimizer profile.
5. Wait for CDP on port `9222` to become healthy.
6. Clear run-local optimizer result artifacts for the new run.
7. Launch a brand-new optimizer run with the configured arguments.
8. Write a fresh current status file with incremented `restart_count`.

### Restart History
Maintain an append-only history file, for example:

`optimizer_restart_history.jsonl`

Each record should include:
- old run id
- old log path
- stale detection time
- reason for restart
- restart count
- new run id

## Clean Restart Policy
When the watchdog restarts the optimizer, the new run must not trust artifacts from the stale run.

Artifacts to clear before launch:
- `parallel_results.json`
- current status pointer file
- any active worker event files associated with the old run
- any run-local current metadata that could make a fresh run appear resumed

Artifacts to preserve:
- historical `run_*.log` files
- archived status files
- restart history records
- per-worker structured logs from the stale run

This policy intentionally sacrifices partial work in favor of correctness.

## Scheduling

### Primary
Use macOS `launchd` for recurring watchdog checks because it is the native scheduler on the target machine.

### Secondary
Support a cron-style wrapper only as a fallback for users who specifically prefer cron.

### Helper Scripts
Recommended scripts:
- `scripts/optimizer/watchdog.py`
- `scripts/optimizer/install_launchd.sh`
- optional `scripts/optimizer/watchdog_cron.sh`

## Operator Commands
Provide simple commands for daily use:
- start watchdog-managed optimizer
- check current status
- force restart
- stop watchdog and optimizer cleanly

Expected behavior:
- the start command should launch a fresh status-managed run
- the status command should print a concise summary from the status file
- the force-restart command should archive the current run and relaunch cleanly
- the stop command should shut down both the watchdog and the optimizer without deleting history

## File-Level Plan

### `scripts/optimizer/tab_worker.py`
- enforce hard failure on unchanged final result hashes
- verify symbol before reading results
- emit structured freshness metadata for each trial
- mark unhealthy worker state when stale reads repeat

### `scripts/optimizer/optimizer.py`
- ensure only fresh trial results can update best-result tracking
- route stale and failed applies into deterministic trial failure handling

### `scripts/optimizer/parallel_runner.py`
- create and update run status files
- emit per-worker structured event logs
- publish worker/pair/trial heartbeat updates

### `scripts/optimizer/run.sh`
- support watchdog-managed startup
- expose clean status and force-restart entry points if implemented as shell wrappers

### `scripts/optimizer/watchdog.py`
- read current status file
- detect stale runs
- archive stale runs
- restart Chrome and relaunch the optimizer

### `scripts/optimizer/install_launchd.sh`
- install or update a launchd job that runs the watchdog every 2 minutes

## Error Handling
- Missing status file: treat as no active managed run and exit cleanly unless start mode is requested.
- Dead optimizer PID but stale status file: archive and relaunch.
- Chrome restart failure: mark restart attempt failed and leave a clear error in restart history.
- CDP not healthy after timeout: do not launch optimizer; leave run state as failed.
- Repeated watchdog restart loop: cap restart frequency and surface a clear operator error.

## Testing Strategy

### Unit-Level
- stale result handling rejects unchanged final hashes
- symbol mismatch rejects result reads
- heartbeat updates only on valid progress events

### Integration-Level
- dry-run mode writes status and worker event files
- watchdog reads healthy status and exits quietly
- watchdog reads stale status and triggers archive + restart

### Manual Smoke Test
1. Start a small run with a few pairs.
2. Confirm status file and worker JSONL files are updating.
3. Simulate a stall by killing the optimizer or freezing progress.
4. Confirm watchdog archives the old run.
5. Confirm Chrome restarts and a fresh run launches from zero.

## Risks and Trade-Offs
- Clean restart throws away partial work, but that is acceptable because correctness is more important than preserving suspect results.
- Structured status and event files add implementation complexity, but they remove ambiguity caused by mixed console output.
- Restarting Chrome is heavier than restarting the optimizer alone, but it better addresses stale TradingView tab state.

## Success Criteria
- Stale reads no longer enter the Bayesian study as successful fresh trials.
- A healthy run continuously updates `last_progress_at`.
- A stalled run is automatically restarted within roughly 12 to 14 minutes.
- Restarted runs begin from a clean state with cleared optimizer result artifacts.
- Operators can inspect current health without depending on the mixed human log.

## Open Questions Resolved
- Resume behavior: resolved to clean restart only.
- Stuck threshold: resolved to 12 minutes.
- Recovery scope: resolved to restart Chrome and the optimizer.
- Scheduler choice: resolved to launchd first, cron optional.
