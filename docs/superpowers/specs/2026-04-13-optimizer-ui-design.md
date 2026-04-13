# Optimizer UI and DB-Backed Run Tracking

## Summary
Add a dedicated frontend optimizer page that can start `scripts/optimizer/parallel_runner.py`, track live progress, cancel an active run, and browse historical runs from the UI.

The design keeps all changes outside the live trading path. A new optimizer API and service layer will launch the runner as a background subprocess, persist run state to the database, and expose run history plus live results to the Next.js frontend.

## Goals
- Trigger optimizer runs from the UI.
- Track live run status, timeline events, and per-symbol results from the UI.
- Persist runs in the database so history survives backend restarts.
- Allow operators to cancel an active run safely.
- Reuse the existing optimizer script rather than reimplementing optimization logic in the web app.

## Non-Goals
- Changing trading strategy logic, optimization scoring, or pair selection philosophy.
- Modifying live trade execution paths in `src/logic.py` or `src/worker.py`.
- Building run-to-run comparison in v1.
- Replacing the existing CLI workflow for engineers who still want to run the script directly.

## Approved Decisions
- UI home: dedicated optimizer page.
- Execution model: backend API starts a background job.
- Persistence: database-backed runs, not in-memory only.
- Scope: trigger, live tracking, cancel, and full run history list with detail view.
- Transport: polling in v1 rather than realtime streaming.

## Problems Being Solved

### 1. No operator-facing control surface
`parallel_runner.py` is currently a script-first workflow. Operators cannot launch or inspect runs from the product UI.

### 2. Weak visibility into progress
Even though the runner writes structured artifacts, there is no product surface that turns them into live status, symbol-level progress, or historical runs.

### 3. No persistent run registry
Without database-backed run records, backend restarts make it hard to know what ran, what failed, and what results belong to which launch.

## Design Overview
The feature adds four pieces:

1. A new backend API domain for optimizer runs.
2. A new backend service that launches and manages optimizer subprocesses.
3. Database tables for runs, events, and symbol results.
4. A dedicated frontend optimizer page with launch controls, active run tracking, result tables, timeline events, and history browsing.

## Architecture

### Backend Flow
Frontend submits a run request:

`POST /api/optimizer/runs`

The backend:
- validates launch payload
- creates a database run row with status `queued`
- creates initial result rows for requested symbols
- starts `parallel_runner.py` as a background subprocess
- updates status to `running`
- persists progress, events, and per-symbol results as the run advances

The frontend reads:
- `GET /api/optimizer/runs`
- `GET /api/optimizer/runs/{id}`
- `GET /api/optimizer/runs/{id}/events`
- `GET /api/optimizer/runs/{id}/results`
- `POST /api/optimizer/runs/{id}/cancel`

### Isolation
This work belongs in the `API Endpoints`, `Services`, `Database`, and `Frontend` modules only. It does not alter live trade execution logic or strategy logic.

### Service Boundary
Add a dedicated optimizer run service responsible for:
- subprocess launch and cancellation
- in-memory process handle registry by `run_id`
- translation from runner output into persisted run state
- recovery behavior on backend restart

API handlers stay thin and delegate orchestration to the service.

## Database Design

### `optimizer_runs`
One row per launched run.

Recommended fields:
- `id` uuid primary key
- `status` text constrained to `queued|running|completed|failed|cancelled|interrupted`
- `mode` text
- `workers` integer
- `pairs` jsonb
- `n_trials` integer
- `dd_limit` numeric
- `dry_run` boolean
- `started_at` timestamptz nullable
- `finished_at` timestamptz nullable
- `created_at` timestamptz
- `updated_at` timestamptz
- `created_by` text nullable
- `summary` jsonb

The `summary` document stores aggregate and UI-friendly values such as:
- `total_pairs`
- `running_pairs`
- `completed_pairs`
- `failed_pairs`
- `best_symbol`
- `best_score`
- `output_paths`
- `error_message`

### `optimizer_run_events`
Append-only run timeline.

Recommended fields:
- `id` bigserial primary key
- `run_id` uuid references `optimizer_runs(id)`
- `event_type` text constrained to `run_started|pair_started|pair_completed|pair_failed|log|run_finished|run_cancelled`
- `worker_id` integer nullable
- `symbol` text nullable
- `payload` jsonb
- `created_at` timestamptz

### `optimizer_run_results`
One row per run and symbol.

Recommended fields:
- `id` bigserial primary key
- `run_id` uuid references `optimizer_runs(id)`
- `symbol` text
- `status` text constrained to `pending|running|completed|failed|cancelled`
- `params` jsonb nullable
- `metrics` jsonb nullable
- `error_message` text nullable
- `started_at` timestamptz nullable
- `finished_at` timestamptz nullable
- unique `(run_id, symbol)`

The `metrics` payload should preserve the main values already emitted by the optimizer result model, including profit, trades, win rate, profit factor, drawdown, and score.

## Runner Integration

### Preferred Path
Extend `parallel_runner.py` so it can emit structured lifecycle events that the backend can consume while preserving existing CLI usage.

Examples of backend-relevant event types:
- `run_started`
- `pair_started`
- `pair_completed`
- `pair_failed`
- `run_finished`
- `run_cancelled`
- `log`

This can be implemented by:
- writing machine-readable JSON lines to stdout
- writing machine-readable JSON lines to a sidecar file that the backend tails
- or invoking a lightweight callback adapter injected through the service layer

The exact mechanism can be chosen during implementation, but the contract must be stable and machine-readable.

### Fallback Path
If the runner changes become too invasive, the backend may parse existing structured artifacts and logs in v1. This is acceptable only if symbol-level progress and final results remain reliable.

## API Contract

### `POST /api/optimizer/runs`
Creates a new run and starts execution.

Request body:
- `mode`
- `workers`
- `pairs`
- `n_trials`
- `dd_limit`
- `dry_run`

Response:
- run id
- initial status
- normalized launch config

### `GET /api/optimizer/runs`
Returns recent runs for history browsing. Supports limit and status filtering.

### `GET /api/optimizer/runs/{id}`
Returns run summary, launch config, aggregate progress, timestamps, and top summary values.

### `GET /api/optimizer/runs/{id}/events`
Returns timeline events sorted newest-first or oldest-first depending on frontend preference.

### `GET /api/optimizer/runs/{id}/results`
Returns per-symbol results for table rendering and sorting.

### `POST /api/optimizer/runs/{id}/cancel`
Cancels an active run. If the run is already terminal, return a no-op success or validation error based on the existing API conventions.

## Frontend Design

### Route
Add a dedicated page under `frontend/src/app/` for optimizer runs. The page should be reachable through the existing app navigation patterns.

### Layout
One page with three stacked areas:

1. Launch controls
2. Active run summary
3. Tabbed detail area

### Launch Controls
Fields:
- mode
- workers
- pairs
- `n_trials`
- `dd_limit`
- `dry_run`

Actions:
- `Start run`
- `Cancel run` when an active run exists

Validation:
- reject empty pair lists
- reject invalid worker counts
- disable submit while launch mutation is pending

### Active Run Summary
Show:
- status badge
- progress bar
- counts for total, running, completed, failed
- started time
- elapsed duration
- best current symbol and score
- output file paths if available

If there is an active run, the page loads that run by default.

### Tabs
`Results`
- sortable table
- columns for symbol, status, score, net profit, total trades, win rate, profit factor, max drawdown

`Timeline`
- live event feed
- worker id, symbol, event type, timestamp, and compact payload rendering

`History`
- recent run list
- click a row to load run detail into the page

### Refresh Strategy
Use polling in v1.

Recommended intervals:
- active run summary and results: every 2 to 5 seconds while running
- history list: on page load and after mutations

## Cancellation Semantics
- UI asks for confirmation before cancel.
- Backend may track `cancel_requested` only as an in-memory transitional state, but persisted database status remains `running` until the subprocess exits and the run can be finalized as `cancelled`.
- Per-symbol rows still in flight become `cancelled` or `failed` based on what the service can determine reliably.

## Recovery and Restart Behavior
- The database is the source of truth for history.
- The backend keeps an in-memory process handle map only for active process management.
- On backend startup, any run left in `queued` or `running` without a live process should be reconciled to `interrupted` or `failed`.
- v1 does not need full process reattachment after backend restart.

## Error Handling
- invalid launch payload returns `400`
- script launch failure marks run `failed` with a top-level error message
- pair-level errors are persisted without failing the entire run unless the subprocess aborts
- repeated database persistence failures should fail the run rather than pretending tracking succeeded

## Security and Safety
- Only allow known optimizer arguments from the API. Do not pass arbitrary shell input through from the UI.
- Launch subprocesses with explicit command arrays, not shell string interpolation.
- Keep all work outside live trading endpoints and worker pipeline paths.

## Testing

### Backend
- payload validation tests
- run lifecycle tests
- cancel flow tests
- integration test using `dry_run`

### Frontend
- launcher form behavior
- polling and status rendering
- history selection behavior
- empty, loading, running, failed, completed, and cancelled states

### Regression Boundary
Do not modify or broaden tests for live trade execution as part of this feature.

## Implementation Notes
- Reuse existing frontend patterns based on React Query hooks for query and mutation state.
- Add a dedicated optimizer hook rather than overloading the existing portfolio optimizer hook.
- Prefer a new API router file and a focused service file rather than adding this behavior to unrelated endpoints.

## Open Questions Resolved
- Page location: dedicated optimizer page.
- Persistence: database-backed runs.
- History scope: full history list with detail loading.
- Cancel support: included in v1.

## Risks
- The runner may need small structured-output changes to support reliable progress ingestion.
- Backend restart during a run may leave orphaned processes if process cleanup is not handled carefully.
- Excessively frequent polling could create noisy load if the results payload grows too large; pagination or capped result sets may be needed if pair counts grow.

## Recommendation
Ship v1 with polling, database-backed persistence, and a single dedicated page. Keep the subprocess control service narrow and explicit so a later v2 can add realtime updates or richer run comparison without changing the page model.
