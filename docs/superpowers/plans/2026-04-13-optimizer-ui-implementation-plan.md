# Optimizer UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated optimizer page that can start `scripts/optimizer/parallel_runner.py`, show live progress and per-symbol results, cancel active runs, and retain full run history in the database.

**Architecture:** Add a new optimizer run API plus a focused service that launches and manages the optimizer subprocess while persisting runs, events, and results to new database tables. Extend `parallel_runner.py` with machine-readable event output, then build a React Query-driven frontend page that polls the new endpoints for active-run state and history.

**Tech Stack:** FastAPI, Python service layer, PostgreSQL/Supabase SQL migrations, Next.js App Router, React 19, TanStack React Query, Vitest, pytest

---

## File Structure

### Backend API and service
- Create: `src/api_optimizer_runs.py`
  New FastAPI router for create/list/detail/results/events/cancel endpoints.
- Create: `src/services/optimizer_run_service.py`
  Own subprocess launch, process registry, event ingestion, run reconciliation, and cancel flow.
- Modify: `src/api.py`
  Import and include the new optimizer router.

### Runner integration
- Modify: `scripts/optimizer/parallel_runner.py`
  Emit stable machine-readable events for run start, pair start, pair completion, pair failure, and run finish/cancel.
- Modify: `scripts/optimizer/runtime_state.py`
  Reuse or extend structured status payloads as needed so backend ingestion has stable fields.

### Database
- Create: `migrations/072_optimizer_runs.sql`
  Add `optimizer_runs`, `optimizer_run_events`, and `optimizer_run_results` with indexes.

### Frontend
- Create: `frontend/src/app/optimizer/page.tsx`
  Route entry for the new page.
- Create: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
  Main page UI: launcher, active summary, tabs, results, timeline, history.
- Create: `frontend/src/hooks/useOptimizerRuns.ts`
  React Query hooks for launch, list, detail, events, results, and cancel.
- Modify: `frontend/src/lib/api.ts`
  Add optimizer run request/response types and fetch helpers.

### Tests
- Create: `tests/test_optimizer_runs_api.py`
  API happy-path and validation coverage with patched service behavior.
- Create: `tests/test_optimizer_run_service.py`
  Service lifecycle, cancel, and reconciliation tests with mocked subprocess and mocked persistence.
- Modify: `tests/test_optimizer_runtime_state.py`
  Add coverage for any new event/state fields emitted by runner integration.
- Create: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
  UI states: idle, running, completed, failed, cancelled, history selection.

---

### Task 1: Add database tables for optimizer runs

**Files:**
- Create: `migrations/072_optimizer_runs.sql`
- Test: no dedicated SQL runner; verify through API/service tests after migration lands

- [ ] **Step 1: Write the migration with all three tables and indexes**

```sql
-- 072_optimizer_runs.sql
CREATE TABLE IF NOT EXISTS public.optimizer_runs (
    id              UUID PRIMARY KEY,
    status          VARCHAR(24) NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
    mode            VARCHAR(32) NOT NULL,
    workers         INTEGER NOT NULL CHECK (workers > 0),
    pairs           JSONB NOT NULL DEFAULT '[]',
    n_trials        INTEGER NOT NULL CHECK (n_trials > 0),
    dd_limit        NUMERIC(10, 4) NOT NULL,
    dry_run         BOOLEAN NOT NULL DEFAULT FALSE,
    created_by      TEXT,
    summary         JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_run_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    event_type      VARCHAR(32) NOT NULL CHECK (event_type IN ('run_started', 'pair_started', 'pair_completed', 'pair_failed', 'log', 'run_finished', 'run_cancelled')),
    worker_id       INTEGER,
    symbol          VARCHAR(32),
    payload         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_run_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    symbol          VARCHAR(32) NOT NULL,
    status          VARCHAR(24) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    params          JSONB NOT NULL DEFAULT '{}',
    metrics         JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_optimizer_runs_status_created_at
    ON public.optimizer_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimizer_run_events_run_id_created_at
    ON public.optimizer_run_events (run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimizer_run_results_run_id_symbol
    ON public.optimizer_run_results (run_id, symbol);
```

- [ ] **Step 2: Sanity-check naming and constraints against the approved spec**

Run: `sed -n '1,220p' migrations/072_optimizer_runs.sql`
Expected: all statuses match the spec and all three tables exist with foreign keys and indexes.

- [ ] **Step 3: Add comments for operator-facing intent**

```sql
COMMENT ON TABLE public.optimizer_runs IS 'UI-launched optimizer runs for TradingView parallel_runner.';
COMMENT ON TABLE public.optimizer_run_events IS 'Append-only event feed for optimizer runs.';
COMMENT ON TABLE public.optimizer_run_results IS 'Per-symbol optimizer results for each run.';
```

- [ ] **Step 4: Re-read the migration after comments are added**

Run: `sed -n '1,260p' migrations/072_optimizer_runs.sql`
Expected: migration is self-contained, readable, and has no placeholder text.

- [ ] **Step 5: Commit**

```bash
git add migrations/072_optimizer_runs.sql
git commit -m "DEV-104: add optimizer run tables"
```

### Task 2: Extend runner output for machine-readable events

**Files:**
- Modify: `scripts/optimizer/parallel_runner.py`
- Modify: `scripts/optimizer/runtime_state.py`
- Modify: `tests/test_optimizer_runtime_state.py`

- [ ] **Step 1: Add a failing runtime-state test for structured event payloads**

```python
def test_record_trial_event_writes_symbol_worker_and_metrics(tmp_path):
    state = OptimizerRuntimeState(tmp_path)
    started = state.start_run(
        args=["--workers", "2"],
        mode="bayesian",
        workers=2,
        log_file="parallel_run.log",
        optimizer_pid=123,
        chrome_pid=456,
    )

    state.record_trial_event(
        run_id=started["run_id"],
        worker_id=1,
        symbol="EURUSD",
        trial=3,
        outcome="fresh",
        params_hash="abc",
        results_hash_before="old",
        results_hash_after="new",
        metrics={"score": 1.7, "net_profit": 120.0},
    )

    event_path = tmp_path / f"optimizer_worker_1_{started['run_id']}.jsonl"
    payload = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["symbol"] == "EURUSD"
    assert payload["worker_id"] == 1
    assert payload["metrics"]["score"] == 1.7
```

- [ ] **Step 2: Run the targeted runtime-state test**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py -v`
Expected: fail until the new or adjusted event fields are emitted as asserted.

- [ ] **Step 3: Add runner event emission helpers**

```python
def _emit_event(event_type: str, **payload: object) -> None:
    event = {"event_type": event_type, **payload}
    print(json.dumps(event), flush=True)


_emit_event(
    "pair_started",
    run_id=run_id,
    worker_id=worker_id,
    symbol=symbol,
    attempt=retries + 1,
)
```

```python
def record_run_event(self, *, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
    event_path = self.results_dir / f"optimizer_events_{run_id}.jsonl"
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event_type": event_type, **payload}) + "\n")
```

- [ ] **Step 4: Re-run runtime-state coverage**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/optimizer/parallel_runner.py scripts/optimizer/runtime_state.py tests/test_optimizer_runtime_state.py
git commit -m "DEV-104: emit optimizer runner events"
```

### Task 3: Build backend service and API endpoints

**Files:**
- Create: `src/services/optimizer_run_service.py`
- Create: `src/api_optimizer_runs.py`
- Modify: `src/api.py`
- Create: `tests/test_optimizer_run_service.py`
- Create: `tests/test_optimizer_runs_api.py`

- [ ] **Step 1: Write failing service tests for launch and cancel lifecycle**

```python
from pathlib import Path


class DummyProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_start_run_persists_run_and_symbol_rows(monkeypatch):
    store = InMemoryOptimizerStore()
    service = OptimizerRunService(store=store, results_dir=Path("/tmp/results"))

    monkeypatch.setattr(service, "_spawn_process", lambda *args, **kwargs: DummyProcess(pid=321))

    run = service.start_run(
        mode="bayesian",
        workers=2,
        pairs=["EURUSD", "GBPUSD"],
        n_trials=25,
        dd_limit=6.0,
        dry_run=True,
        created_by="test-user",
    )

    assert run["status"] == "running"
    assert store.runs[run["id"]]["workers"] == 2
    assert store.results[(run["id"], "EURUSD")]["status"] == "pending"


def test_cancel_run_terminates_process_and_marks_cancelled(monkeypatch):
    store = InMemoryOptimizerStore.with_running_run()
    service = OptimizerRunService(store=store, results_dir=Path("/tmp/results"))
    process = DummyProcess(pid=321)
    service._processes[store.active_run_id] = process

    service.cancel_run(store.active_run_id)

    assert process.terminated is True
    assert store.runs[store.active_run_id]["status"] == "cancelled"
```

- [ ] **Step 2: Run service tests to confirm failures**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -v`
Expected: FAIL because service file and lifecycle logic do not exist yet.

- [ ] **Step 3: Implement focused service with explicit launch args and process registry**

```python
class OptimizerRunService:
    def __init__(self, store: OptimizerRunStore, results_dir: Path) -> None:
        self._store = store
        self._results_dir = results_dir
        self._processes: dict[str, subprocess.Popen[str]] = {}

    def start_run(self, *, mode: str, workers: int, pairs: list[str], n_trials: int, dd_limit: float, dry_run: bool, created_by: str | None) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        self._store.create_run(
            run_id=run_id,
            status="queued",
            mode=mode,
            workers=workers,
            pairs=pairs,
            n_trials=n_trials,
            dd_limit=dd_limit,
            dry_run=dry_run,
            created_by=created_by,
        )
        process = self._spawn_process(run_id=run_id, mode=mode, workers=workers, pairs=pairs, n_trials=n_trials, dd_limit=dd_limit, dry_run=dry_run)
        self._processes[run_id] = process
        self._store.mark_run_started(run_id=run_id, pid=process.pid)
        return self._store.get_run(run_id)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        process = self._processes.get(run_id)
        if process is None:
            raise ValueError(f"Unknown active optimizer run: {run_id}")
        process.terminate()
        self._store.mark_run_cancelled(run_id=run_id)
        return self._store.get_run(run_id)
```

- [ ] **Step 4: Add failing API tests, then implement router and register it**

```python
from fastapi.testclient import TestClient


class StubOptimizerService:
    def start_run(self, **_: object) -> dict[str, object]:
        return {"id": "run-1", "status": "running", "mode": "bayesian"}


def test_create_optimizer_run_returns_200(client, monkeypatch):
    monkeypatch.setattr("src.api_optimizer_runs.get_optimizer_run_service", lambda: StubOptimizerService())
    response = client.post(
        "/api/optimizer/runs",
        json={
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD", "GBPUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_create_optimizer_run_rejects_empty_pairs(client):
    response = client.post(
        "/api/optimizer/runs",
        json={"mode": "bayesian", "workers": 2, "pairs": [], "n_trials": 25, "dd_limit": 6.0, "dry_run": True},
    )
    assert response.status_code == 422
```

```python
router = APIRouter(prefix="/api/optimizer/runs", tags=["optimizer-runs"])


@router.post("", response_model=dict[str, Any])
def create_optimizer_run(payload: OptimizerRunCreateRequest):
    service = get_optimizer_run_service()
    return service.start_run(**payload.model_dump())
```

- [ ] **Step 5: Run backend tests and commit**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py -v`
Expected: PASS

```bash
git add src/services/optimizer_run_service.py src/api_optimizer_runs.py src/api.py tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py
git commit -m "DEV-104: add optimizer run api"
```

### Task 4: Persist runner events and reconcile active runs

**Files:**
- Modify: `src/services/optimizer_run_service.py`
- Modify: `tests/test_optimizer_run_service.py`

- [ ] **Step 1: Add a failing service test for event ingestion and result updates**

```python
def test_ingest_pair_completed_event_updates_summary_and_result():
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store=store, results_dir=Path("/tmp/results"))

    service.ingest_event(
        {
            "event_type": "pair_completed",
            "run_id": "run-1",
            "worker_id": 0,
            "symbol": "EURUSD",
            "metrics": {"score": 2.1, "net_profit": 250.0, "win_rate": 61.0},
            "params": {"lookback": 20},
        }
    )

    result = store.results[("run-1", "EURUSD")]
    assert result["status"] == "completed"
    assert result["metrics"]["score"] == 2.1
    assert store.runs["run-1"]["summary"]["completed_pairs"] == 1
```

- [ ] **Step 2: Run targeted lifecycle tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -v`
Expected: FAIL until event ingestion updates summary, result rows, and timeline rows.

- [ ] **Step 3: Implement event-to-store translation and startup reconciliation**

```python
def ingest_event(self, event: dict[str, Any]) -> None:
    self._store.append_event(
        run_id=event["run_id"],
        event_type=event["event_type"],
        worker_id=event.get("worker_id"),
        symbol=event.get("symbol"),
        payload=event,
    )
    if event["event_type"] == "pair_started":
        self._store.mark_result_running(run_id=event["run_id"], symbol=event["symbol"])
    elif event["event_type"] == "pair_completed":
        self._store.mark_result_completed(
            run_id=event["run_id"],
            symbol=event["symbol"],
            params=event.get("params", {}),
            metrics=event.get("metrics", {}),
        )
        self._store.bump_summary(run_id=event["run_id"], completed_pairs=1, best_symbol=event["symbol"], best_score=event.get("metrics", {}).get("score"))
    elif event["event_type"] == "pair_failed":
        self._store.mark_result_failed(
            run_id=event["run_id"],
            symbol=event["symbol"],
            error_message=event.get("error_message", "optimizer pair failed"),
        )
```

```python
def reconcile_incomplete_runs(self) -> None:
    for run in self._store.list_incomplete_runs():
        if run["id"] not in self._processes:
            self._store.mark_run_interrupted(run["id"])
```

- [ ] **Step 4: Re-run lifecycle tests including reconciliation**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/optimizer_run_service.py tests/test_optimizer_run_service.py
git commit -m "DEV-104: persist optimizer run progress"
```

### Task 5: Add frontend API client and React Query hooks

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useOptimizerRuns.ts`

- [ ] **Step 1: Write a failing frontend hook test for launch and polling keys**

```tsx
it('builds stable query keys for optimizer runs and run details', () => {
  expect(optimizerRunKeys.list()).toEqual(['optimizer-runs', 'list']);
  expect(optimizerRunKeys.detail('run-1')).toEqual(['optimizer-runs', 'detail', 'run-1']);
});
```

- [ ] **Step 2: Run the frontend test file to confirm failure**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: FAIL because optimizer API helpers and hooks do not exist yet.

- [ ] **Step 3: Add typed API helpers**

```ts
export interface OptimizerRunApi {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
  mode: string;
  workers: number;
  pairs: string[];
  n_trials: number;
  dd_limit: number;
  dry_run: boolean;
  summary: {
    total_pairs: number;
    running_pairs: number;
    completed_pairs: number;
    failed_pairs: number;
    best_symbol?: string;
    best_score?: number;
  };
}

export function createOptimizerRun(payload: OptimizerRunCreateApi) {
  return apiFetch<OptimizerRunApi>('/api/optimizer/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 4: Add React Query hooks with polling-friendly options**

```ts
export const optimizerRunKeys = {
  list: () => ['optimizer-runs', 'list'] as const,
  detail: (runId: string) => ['optimizer-runs', 'detail', runId] as const,
  results: (runId: string) => ['optimizer-runs', 'results', runId] as const,
  events: (runId: string) => ['optimizer-runs', 'events', runId] as const,
};

export function useOptimizerRun(runId: string | null) {
  return useQuery({
    queryKey: runId ? optimizerRunKeys.detail(runId) : ['optimizer-runs', 'detail', 'idle'],
    queryFn: () => fetchOptimizerRun(runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => query.state.data?.status === 'running' ? 3000 : false,
  });
}
```

- [ ] **Step 5: Run the hook/UI test and commit**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: partial PASS for query-key and hook wiring assertions; UI rendering may still fail until the page component exists.

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useOptimizerRuns.ts
git commit -m "DEV-104: add optimizer run hooks"
```

### Task 6: Build optimizer page UI and frontend tests

**Files:**
- Create: `frontend/src/app/optimizer/page.tsx`
- Create: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
- Create: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Write failing UI tests for launcher, running state, and history selection**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';


it('launches a run and shows running summary cards', async () => {
  render(<OptimizerRunsWorkspace />);

  await userEvent.click(screen.getByRole('button', { name: /start run/i }));

  expect(await screen.findByText(/running/i)).toBeInTheDocument();
  expect(screen.getByText(/completed pairs/i)).toBeInTheDocument();
});

it('loads selected history row into results tab', async () => {
  render(<OptimizerRunsWorkspace />);

  await userEvent.click(await screen.findByRole('button', { name: /run-2026-04-13/i }));

  expect(await screen.findByText(/eurusd/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the UI test file to verify failure**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: FAIL because page and workspace component do not exist yet.

- [ ] **Step 3: Implement page route and workspace component**

```tsx
export default function OptimizerPage() {
  return (
    <div className="space-y-4 animate-fade-in-up">
      <div>
        <h1 className="page-title text-lg font-semibold">Optimizer</h1>
        <p className="page-subtitle mt-0.5 text-xs">
          Launch parallel optimizer runs, track live progress, and inspect history.
        </p>
      </div>
      <OptimizerRunsWorkspace />
    </div>
  );
}
```

```tsx
export function OptimizerRunsWorkspace() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const createRun = useCreateOptimizerRun();
  const cancelRun = useCancelOptimizerRun();
  const { data: runs = [] } = useOptimizerRuns();
  const { data: activeRun } = useActiveOptimizerRun(runs);
  const currentRunId = selectedRunId ?? activeRun?.id ?? runs[0]?.id ?? null;
  const { data: currentRun } = useOptimizerRun(currentRunId);
  const { data: results = [] } = useOptimizerRunResults(currentRunId);
  const { data: events = [] } = useOptimizerRunEvents(currentRunId);

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={() =>
          createRun.mutate({
            mode: 'bayesian',
            workers: 2,
            pairs: ['EURUSD', 'GBPUSD'],
            n_trials: 25,
            dd_limit: 6,
            dry_run: true,
          })
        }
      >
        Start run
      </button>
      <button type="button" onClick={() => currentRunId && cancelRun.mutate(currentRunId)}>
        Cancel run
      </button>
      <section>
        <h2>Status</h2>
        <p>{currentRun?.status ?? 'idle'}</p>
        <p>Completed pairs: {currentRun?.summary?.completed_pairs ?? 0}</p>
      </section>
      <section>
        <h2>History</h2>
        {runs.map((run) => (
          <button key={run.id} type="button" onClick={() => setSelectedRunId(run.id)}>
            {run.id}
          </button>
        ))}
      </section>
      <section>
        <h2>Results</h2>
        {results.map((result) => (
          <p key={result.symbol}>{result.symbol}</p>
        ))}
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run frontend tests and production build**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: build succeeds, ignoring the known pre-existing `tradingMetrics.test.ts` failure because build does not execute Vitest.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/optimizer/page.tsx frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx
git commit -m "DEV-104: add optimizer ui"
```

### Task 7: Final integration verification

**Files:**
- Modify: none unless verification exposes a gap
- Test: `tests/test_optimizer_runs_api.py`
- Test: `tests/test_optimizer_run_service.py`
- Test: `tests/test_optimizer_runtime_state.py`
- Test: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Run backend optimizer test slice**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runtime_state.py tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py -v`
Expected: PASS

- [ ] **Step 2: Run frontend optimizer test slice**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 3: Run dry-run smoke path manually**

Run: `source ./venv/bin/activate && PYTHONPATH=. python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000`
Expected: API boots with new optimizer router loaded.

Run in a second shell: `curl -s -X POST http://localhost:8000/api/optimizer/runs -H 'Content-Type: application/json' -d '{"mode":"bayesian","workers":2,"pairs":["EURUSD","GBPUSD"],"n_trials":5,"dd_limit":6.0,"dry_run":true}'`
Expected: JSON response with `status` set to `running` and a new run id.

- [ ] **Step 4: Verify no live trading paths changed unintentionally**

Run: `git diff --stat HEAD~7..HEAD`
Expected: changes limited to migration, optimizer script/service/API, frontend optimizer page, and tests.

- [ ] **Step 5: Commit any final verification-only fixes**

```bash
git add .
git commit -m "DEV-104: finalize optimizer ui integration"
```

---

## Spec Coverage Check
- Dedicated optimizer page: Task 6.
- Backend API create/list/detail/results/events/cancel: Task 3 plus Task 4.
- DB-backed runs, events, results: Task 1.
- Structured runner output for ingestion: Task 2.
- Active run polling and history detail loading: Task 5 plus Task 6.
- Cancel flow and reconciliation after restart: Task 3 plus Task 4.
- Backend and frontend tests: Tasks 2 through 7.

## Placeholder Scan
- No `TODO`, `TBD`, or “implement later” markers remain.
- Every task lists exact files and concrete commands.
- Every code-writing step contains a concrete snippet to anchor implementation.

## Type Consistency Check
- Persisted run status set: `queued|running|completed|failed|cancelled|interrupted`
- Result row status set: `pending|running|completed|failed|cancelled`
- API path family stays under `/api/optimizer/runs`
- Frontend query keys stay under `optimizer-runs`
