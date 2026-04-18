# Broker-Aware Optimizer Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add broker selection to optimizer runs and write completed results into broker-specific optimizer dataset files without changing live trading logic.

**Architecture:** Extend the optimizer run contract to carry `broker` plus hidden `market="forex"`, persist those fields on runs, propagate broker context into the local optimizer runner, and swap the single shared `parallel_results.json` output path for a broker-specific file resolved from the run. The frontend launcher and run history should surface broker so operators can intentionally generate and compare separate Vantage, OANDA, and FXCM datasets.

**Tech Stack:** Next.js/React, TypeScript, FastAPI, Pydantic, Python service layer, local Python optimizer runner, pytest, vitest

---

## File Structure

- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
  Why: add the broker selector to the launcher and display broker in run metadata.
- Modify: `frontend/src/lib/api.ts`
  Why: extend optimizer run request/response types with `broker` and `market`.
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
  Why: cover default broker selection, submitted payload, and broker rendering.
- Modify: `src/api_optimizer_runs.py`
  Why: validate incoming broker values and include them in the create-run request schema.
- Modify: `src/services/optimizer_run_service.py`
  Why: persist `broker`/`market`, pass broker context to the local runner, and include broker-aware output metadata in run summaries.
- Modify: `scripts/optimizer/parallel_runner.py`
  Why: resolve broker-specific results/report file paths and stop writing all brokers into the shared file.
- Modify: `scripts/optimizer/local_agent.py`
  Why: pass the run broker into the optimizer runner subprocess/CLI.
- Modify: `scripts/optimizer/README.md`
  Why: document broker-specific output files and usage.
- Create or modify tests:
  - `tests/test_optimizer_run_service.py`
  - `tests/test_api_optimizer_runs.py`

### Task 1: Extend the Optimizer Run Contract

**Files:**
- Modify: `src/api_optimizer_runs.py`
- Modify: `src/services/optimizer_run_service.py`
- Modify: `frontend/src/lib/api.ts`
- Test: `tests/test_optimizer_run_service.py`
- Test: `tests/test_api_optimizer_runs.py`

- [ ] **Step 1: Write the failing backend service tests for broker persistence**

```python
def test_start_run_persists_broker_and_market(fake_repo):
    service = OptimizerRunService(repository=fake_repo)

    run = service.start_run(
        strategy_id="liq_sd_v1",
        strategy_version="1",
        mode="bayesian",
        workers=3,
        pairs=["EURUSD"],
        n_trials=25,
        dd_limit=6,
        dry_run=True,
        broker="vantage",
    )

    assert run["broker"] == "vantage"
    assert run["market"] == "forex"


def test_start_run_rejects_unknown_broker(fake_repo):
    service = OptimizerRunService(repository=fake_repo)

    with pytest.raises(ValueError, match="invalid broker"):
        service.start_run(
            strategy_id="liq_sd_v1",
            strategy_version="1",
            mode="bayesian",
            workers=3,
            pairs=["EURUSD"],
            n_trials=25,
            dd_limit=6,
            dry_run=True,
            broker="not-real",
        )
```

- [ ] **Step 2: Run the failing service tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -q`
Expected: FAIL because `start_run()` does not accept `broker` yet and does not persist `market`.

- [ ] **Step 3: Write the failing API validation tests**

```python
def test_create_optimizer_run_accepts_supported_broker(client, admin_headers):
    response = client.post(
        "/api/optimizer/runs",
        headers=admin_headers,
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 3,
            "pairs": ["ALL"],
            "n_trials": 25,
            "dd_limit": 6,
            "dry_run": True,
            "broker": "vantage",
        },
    )

    assert response.status_code == 200


def test_create_optimizer_run_rejects_unsupported_broker(client, admin_headers):
    response = client.post(
        "/api/optimizer/runs",
        headers=admin_headers,
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 3,
            "pairs": ["ALL"],
            "n_trials": 25,
            "dd_limit": 6,
            "dry_run": True,
            "broker": "bad-broker",
        },
    )

    assert response.status_code == 422
```

- [ ] **Step 4: Run the failing API tests**

Run: `PYTHONPATH=. pytest tests/test_api_optimizer_runs.py -q`
Expected: FAIL because the request schema does not include `broker`.

- [ ] **Step 5: Implement the minimal backend contract**

```python
# src/api_optimizer_runs.py
class OptimizerRunCreateRequest(BaseModel):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    workers: int = Field(ge=1, le=12)
    pairs: list[str]
    n_trials: int = Field(ge=1, le=1000)
    dd_limit: float = Field(gt=0)
    dry_run: bool = False
    broker: str = Field(min_length=1)

    @field_validator("broker")
    @classmethod
    def _validate_broker(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"vantage", "oanda", "fxcm"}:
            raise ValueError("invalid broker")
        return normalized
```

```python
# src/services/optimizer_run_service.py
def start_run(
    self,
    *,
    strategy_id: str,
    strategy_version: str,
    mode: str,
    workers: int,
    pairs: list[str],
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
    broker: str,
    created_by: str | None = None,
) -> dict[str, Any]:
    if broker not in {"vantage", "oanda", "fxcm"}:
        raise ValueError(f"invalid broker: {broker}")

    ...
    run = self._repository.create_run(
        {
            "id": run_id,
            ...
            "broker": broker,
            "market": "forex",
            ...
        }
    )
```

```ts
// frontend/src/lib/api.ts
export interface OptimizerRunApi {
  ...
  broker?: 'vantage' | 'oanda' | 'fxcm' | null;
  market?: string | null;
}

export interface OptimizerRunCreateApi {
  ...
  broker: 'vantage' | 'oanda' | 'fxcm';
}
```

- [ ] **Step 6: Run the backend tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_api_optimizer_runs.py -q`
Expected: PASS for broker validation and persistence coverage.

- [ ] **Step 7: Commit the contract changes**

```bash
git add src/api_optimizer_runs.py src/services/optimizer_run_service.py frontend/src/lib/api.ts tests/test_optimizer_run_service.py tests/test_api_optimizer_runs.py
git commit -m "DEV-137: add broker to optimizer run contract"
```

### Task 2: Propagate Broker into the Local Runner and Output Paths

**Files:**
- Modify: `src/services/optimizer_run_service.py`
- Modify: `scripts/optimizer/local_agent.py`
- Modify: `scripts/optimizer/parallel_runner.py`
- Test: `tests/test_optimizer_run_service.py`

- [ ] **Step 1: Write the failing service test for broker-aware output metadata**

```python
def test_rebuild_summary_keeps_broker_specific_output_path(fake_repo):
    service = OptimizerRunService(repository=fake_repo)
    run = fake_repo.seed_run(
        broker="oanda",
        market="forex",
        pairs=["EURUSD"],
    )

    summary = service._rebuild_summary(
        run["id"],
        outputs={"results_file": "scripts/optimization_results/parallel_results_oanda.json"},
    )

    assert summary["output_paths"]["results_file"].endswith("parallel_results_oanda.json")
```

- [ ] **Step 2: Run the targeted service test**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -q`
Expected: FAIL until broker-aware output metadata is wired consistently.

- [ ] **Step 3: Implement broker forwarding in the service and local agent**

```python
# src/services/optimizer_run_service.py
def _spawn_process(..., broker: str) -> subprocess.Popen[str]:
    command = [
        sys.executable,
        "-m",
        "scripts.optimizer.parallel_runner",
        "--workers",
        str(workers),
        "--mode",
        mode,
        "--trials",
        str(n_trials),
        "--dd-limit",
        str(dd_limit),
        "--pairs",
        ",".join(pairs),
        "--broker",
        broker,
    ]
```

```python
# scripts/optimizer/local_agent.py
body = {
    ...
    "broker": run.get("broker") or "vantage",
}
```

- [ ] **Step 4: Implement broker-specific file resolution in the runner**

```python
# scripts/optimizer/parallel_runner.py
SUPPORTED_BROKERS = {"vantage", "oanda", "fxcm"}

def results_file_for_broker(broker: str) -> Path:
    normalized = broker.strip().lower()
    if normalized not in SUPPORTED_BROKERS:
        raise ValueError(f"Unsupported broker: {broker}")
    return RESULTS_DIR / f"parallel_results_{normalized}.json"
```

```python
async def run_parallel(..., broker: str, raw_args: list[str] | None = None) -> dict:
    results_file = results_file_for_broker(broker)
    ...
    if results_file.exists():
        with open(results_file) as f:
            existing_results = json.load(f)
    ...
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    ...
    output_paths = {"results_file": str(results_file)}
```

- [ ] **Step 5: Extend the CLI parser to accept broker**

```python
parser.add_argument(
    "--broker",
    choices=["vantage", "oanda", "fxcm"],
    default="vantage",
    help="Broker dataset namespace for output files",
)
...
asyncio.run(
    run_parallel(
        pairs=pairs,
        n_workers=args.workers,
        mode=args.mode,
        n_trials=args.trials,
        dd_limit=args.dd_limit,
        dry_run=args.dry_run,
        broker=args.broker,
        raw_args=sys.argv[1:],
    )
)
```

- [ ] **Step 6: Run the backend service tests again**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -q`
Expected: PASS with broker-aware output path summary coverage.

- [ ] **Step 7: Commit the runner-path changes**

```bash
git add src/services/optimizer_run_service.py scripts/optimizer/local_agent.py scripts/optimizer/parallel_runner.py tests/test_optimizer_run_service.py
git commit -m "DEV-137: route optimizer results by broker"
```

### Task 3: Add Broker Selection to the Optimizer UI

**Files:**
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write the failing UI tests**

```tsx
it('defaults broker selection to Vantage', () => {
  render(<OptimizerRunsWorkspace />);
  expect(screen.getByLabelText(/broker/i)).toHaveValue('vantage');
});

it('submits the selected broker in the create-run payload', async () => {
  const createRun = vi.fn();
  mockCreateOptimizerRun(createRun);

  render(<OptimizerRunsWorkspace />);

  await user.selectOptions(screen.getByLabelText(/broker/i), 'oanda');
  await user.click(screen.getByRole('button', { name: /start run/i }));

  expect(createRun).toHaveBeenCalledWith(
    expect.objectContaining({ broker: 'oanda' }),
    expect.anything()
  );
});
```

- [ ] **Step 2: Run the frontend test file to verify failure**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: FAIL because no broker selector exists yet.

- [ ] **Step 3: Implement the broker selector and broker display**

```tsx
const [broker, setBroker] = useState<'vantage' | 'oanda' | 'fxcm'>('vantage');

const payload: OptimizerRunCreateApi = {
  strategy_id: strategyId.trim(),
  strategy_version: strategyVersion.trim(),
  mode,
  workers: Number(workers),
  pairs: allPairs ? ['ALL'] : pairs.split(',').map((item) => item.trim()).filter(Boolean),
  n_trials: Number(nTrials),
  dd_limit: Number(ddLimit),
  dry_run: dryRun,
  broker,
};
```

```tsx
<label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
  <span>Broker</span>
  <select
    aria-label='Broker'
    value={broker}
    onChange={(event) => setBroker(event.target.value as typeof broker)}
    className='h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 text-sm text-[var(--to-text-primary)]'
  >
    <option value='vantage'>Vantage</option>
    <option value='oanda'>OANDA</option>
    <option value='fxcm'>FXCM</option>
  </select>
</label>
```

```tsx
<div className='rounded-lg border border-[var(--to-border)] p-3'>
  <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Broker</p>
  <p className='mt-2 text-sm text-[var(--to-text-primary)]'>
    {currentRun?.broker ? currentRun.broker.toUpperCase() : 'Unknown'}
  </p>
</div>
```

- [ ] **Step 4: Run the frontend tests again**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS for default broker and submitted payload coverage.

- [ ] **Step 5: Commit the UI changes**

```bash
git add frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx frontend/src/lib/api.ts
git commit -m "DEV-137: add optimizer broker selector"
```

### Task 4: Document and Verify Broker-Specific Datasets

**Files:**
- Modify: `scripts/optimizer/README.md`
- Modify: `tests/test_api_optimizer_runs.py`
- Modify: `tests/test_optimizer_run_service.py`

- [ ] **Step 1: Add or extend verification tests for output file naming**

```python
def test_parallel_runner_uses_broker_specific_results_filename(tmp_path):
    path = results_file_for_broker("fxcm")
    assert path.name == "parallel_results_fxcm.json"
```

- [ ] **Step 2: Run focused Python tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_api_optimizer_runs.py -q`
Expected: PASS with broker validation and broker output coverage.

- [ ] **Step 3: Update the optimizer README**

```md
- `parallel_results_vantage.json` — latest completed forex optimizer dataset for Vantage
- `parallel_results_oanda.json` — latest completed forex optimizer dataset for OANDA
- `parallel_results_fxcm.json` — latest completed forex optimizer dataset for FXCM
```

```bash
python -m scripts.optimizer.parallel_runner --workers 3 --mode bayesian --broker vantage
python -m scripts.optimizer.parallel_runner --workers 3 --mode bayesian --broker oanda
```

- [ ] **Step 4: Run end-to-end verification commands**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_api_optimizer_runs.py -q`
Expected: PASS

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit documentation and final verification updates**

```bash
git add scripts/optimizer/README.md tests/test_optimizer_run_service.py tests/test_api_optimizer_runs.py docs/superpowers/specs/2026-04-18-broker-aware-optimizer-datasets-design.md docs/superpowers/plans/2026-04-18-broker-aware-optimizer-datasets.md
git commit -m "DEV-137: document broker-aware optimizer datasets"
```

## Self-Review

- Spec coverage: covered launcher UX, broker validation, run persistence, broker-specific file output, run history display, backward compatibility fallback, and futures-ready `market="forex"` storage.
- Placeholder scan: no `TODO`, `TBD`, or “implement later” placeholders remain.
- Type consistency: the plan consistently uses `broker` with values `vantage|oanda|fxcm` and `market="forex"` across frontend, API, service, and runner tasks.
