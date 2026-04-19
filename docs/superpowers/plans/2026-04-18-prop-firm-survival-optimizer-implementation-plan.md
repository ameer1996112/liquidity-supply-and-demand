# Prop-Firm Survival Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the optimizer into a prop-firm survival system that stores full run artifacts, evaluates pair and portfolio safety, and exposes an analyst-grade optimizer workspace in the frontend.

**Architecture:** Extend the existing optimizer run pipeline instead of replacing it. Add persistence and APIs for trials, stress tests, portfolio summaries, news events, and spread profiles; then teach the optimizer runner to emit staged results; then upgrade the frontend workspace to visualize run configuration, portfolio health, pair decisions, and deep drill-downs.

**Tech Stack:** FastAPI, Supabase/Postgres migrations, Python optimizer scripts, pytest, Next.js/React, existing frontend query hooks and UI primitives.

---

## File Structure

### Existing Files To Modify

- `migrations/072_optimizer_runs.sql`
  Current optimizer tables. Keep intact as historical baseline; add a new migration instead of editing this file in-place.
- `src/services/optimizer_run_service.py`
  Extend repository contract and service methods to persist richer optimizer artifacts.
- `src/api_optimizer_runs.py`
  Add read/write endpoints for trials, stress tests, portfolio summaries, and enriched run payloads.
- `scripts/optimizer/optimizer.py`
  Add staged evaluation flow, pair decision classification, and richer payload emission.
- `scripts/optimizer/models.py`
  Add typed structures for forward windows, stress tests, and pair/portfolio decisions.
- `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
  Replace the basic launcher/results UI with the analyst workspace.
- `frontend/src/lib/api.ts`
  Add API types and fetchers for the new optimizer payloads.
- `frontend/src/hooks/useOptimizerRuns.ts`
  Add query hooks for new detail endpoints and normalized response types.
- `tests/test_optimizer_run_service.py`
  Extend service tests to cover richer persistence and run summaries.
- `tests/test_optimizer_runs_api.py`
  Add API tests for new optimizer detail endpoints.
- `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
  Add frontend coverage for the new workspace states.

### New Backend Files To Create

- `migrations/073_optimizer_survival_artifacts.sql`
  Adds tables for trials, stress tests, portfolio results, news events, and spread profiles.
- `src/services/optimizer_survival_scoring.py`
  Small focused service to compute hard gates, scores, and `PASS/REDUCE_RISK/REJECT` outcomes.
- `src/services/optimizer_portfolio_service.py`
  Simulates combined portfolio equity and assigns pair weights under internal caps.
- `src/services/optimizer_market_context_service.py`
  Maps news events to symbols and resolves spread profiles for stress runs.
- `src/services/optimizer_news_ingest.py`
  Fetches and normalizes Trading Economics events into local storage.

### New Tests To Create

- `tests/test_optimizer_survival_scoring.py`
  Covers hard gates and pair classification logic.
- `tests/test_optimizer_portfolio_service.py`
  Covers combined drawdown calculations and greedy weight reduction.
- `tests/test_optimizer_market_context_service.py`
  Covers news-to-symbol mapping and spread stress variants.

### Optional New Frontend Files

- `frontend/src/components/optimizer/PortfolioOverviewCard.tsx`
- `frontend/src/components/optimizer/PairAnalysisTable.tsx`
- `frontend/src/components/optimizer/PairDrilldownPanel.tsx`
- `frontend/src/components/optimizer/RunComparisonPanel.tsx`

Use these only if `OptimizerRunsWorkspace.tsx` becomes too large while implementing the analyst UI.

### Docs To Check While Implementing

- `docs/superpowers/specs/2026-04-18-prop-firm-survival-optimizer-design.md`
- `scripts/optimizer/README.md`

## Task 1: Add Survival Optimizer Storage

**Files:**
- Create: `migrations/073_optimizer_survival_artifacts.sql`
- Test: `tests/test_optimizer_run_service.py`

- [ ] **Step 1: Write the failing service test for richer persistence**

```python
def test_repository_persists_trials_stress_and_portfolio_results() -> None:
    store = InMemoryOptimizerStore()

    store.create_trial(
        "run-1",
        "EURUSD",
        {
            "trial_number": 1,
            "window": "train",
            "params": {"ema_len": 200},
            "metrics": {"net_profit": 1200.0},
        },
    )
    store.create_stress_result(
        "run-1",
        "EURUSD",
        {
            "stress_type": "spread_125",
            "status": "passed",
            "metrics": {"max_drawdown_pct": 4.1},
        },
    )
    store.upsert_portfolio_result(
        "run-1",
        {
            "combined_max_drawdown_pct": 5.8,
            "combined_daily_drawdown_pct": 2.7,
            "weights": {"EURUSD": 1.0},
        },
    )

    assert store.list_trials("run-1", "EURUSD")[0]["trial_number"] == 1
    assert store.list_stress_results("run-1", "EURUSD")[0]["stress_type"] == "spread_125"
    assert store.get_portfolio_result("run-1")["combined_max_drawdown_pct"] == 5.8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -k richer_persistence -v`
Expected: FAIL with missing repository methods on `InMemoryOptimizerStore`.

- [ ] **Step 3: Add the migration for survival artifacts**

```sql
CREATE TABLE IF NOT EXISTS public.optimizer_run_trials (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    trial_number INTEGER NOT NULL,
    window VARCHAR(24) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_run_stress_tests (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    stress_type VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_portfolio_results (
    run_id UUID PRIMARY KEY REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.news_events (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    currency VARCHAR(8) NOT NULL,
    country TEXT,
    importance INTEGER NOT NULL,
    title TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS public.spread_profiles (
    id BIGSERIAL PRIMARY KEY,
    broker TEXT NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    baseline_spread NUMERIC(12, 6) NOT NULL,
    stress_125 NUMERIC(12, 6) NOT NULL,
    stress_150 NUMERIC(12, 6) NOT NULL,
    slippage_per_side NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broker, symbol)
);
```

- [ ] **Step 4: Extend the in-memory test repository to support the new records**

```python
class InMemoryOptimizerStore:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.results: dict[tuple[str, str], dict] = {}
        self.events: list[dict] = []
        self.trials: list[dict] = []
        self.stress_results: list[dict] = []
        self.portfolio_results: dict[str, dict] = {}

    def create_trial(self, run_id: str, symbol: str, payload: dict) -> dict:
        row = {"run_id": run_id, "symbol": symbol, **payload}
        self.trials.append(row)
        return row

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict]:
        return [
            row for row in self.trials
            if row["run_id"] == run_id and (symbol is None or row["symbol"] == symbol)
        ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -k richer_persistence -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add migrations/073_optimizer_survival_artifacts.sql tests/test_optimizer_run_service.py
git commit -m "DEV-138: add optimizer survival storage schema"
```

## Task 2: Extend Optimizer Run Service and Repository Contract

**Files:**
- Modify: `src/services/optimizer_run_service.py`
- Test: `tests/test_optimizer_run_service.py`

- [ ] **Step 1: Write the failing service test for new repository calls**

```python
def test_service_exposes_survival_artifacts(monkeypatch) -> None:
    store = InMemoryOptimizerStore.with_run_and_pending_symbol("run-1", "EURUSD")
    service = OptimizerRunService(store, project_root=Path("/tmp"), results_dir=Path("/tmp/results"))

    service.record_trial(
        "run-1",
        "EURUSD",
        {"trial_number": 3, "window": "forward", "params": {}, "metrics": {"net_profit": 200.0}},
    )
    service.record_stress_result(
        "run-1",
        "EURUSD",
        {"stress_type": "news_blackout_30m", "status": "passed", "metrics": {"profit_factor": 1.2}},
    )
    service.update_portfolio_result(
        "run-1",
        {"combined_max_drawdown_pct": 5.2, "weights": {"EURUSD": 1.0}},
    )

    assert service.list_trials("run-1", "EURUSD")[0]["window"] == "forward"
    assert service.list_stress_results("run-1", "EURUSD")[0]["status"] == "passed"
    assert service.get_portfolio_result("run-1")["weights"]["EURUSD"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -k exposes_survival_artifacts -v`
Expected: FAIL with missing `record_trial`, `record_stress_result`, or `update_portfolio_result`.

- [ ] **Step 3: Extend the repository protocol and Supabase repository**

```python
class OptimizerRunRepository(Protocol):
    def create_trial(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]: ...
    def create_stress_result(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]: ...
    def upsert_portfolio_result(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_portfolio_result(self, run_id: str) -> dict[str, Any] | None: ...
```

- [ ] **Step 4: Add service methods and enrich `get_run`**

```python
def record_trial(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.get_run(run_id)
    return self._repository.create_trial(run_id, symbol, payload)

def get_run(self, run_id: str) -> dict[str, Any]:
    run = self._repository.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    run["portfolio_result"] = self._repository.get_portfolio_result(run_id)
    return run
```

- [ ] **Step 5: Run focused tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -k "survival_artifacts or start_run" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/optimizer_run_service.py tests/test_optimizer_run_service.py
git commit -m "DEV-138: extend optimizer run service for survival artifacts"
```

## Task 3: Add Survival Scoring and Portfolio Services

**Files:**
- Create: `src/services/optimizer_survival_scoring.py`
- Create: `src/services/optimizer_portfolio_service.py`
- Test: `tests/test_optimizer_survival_scoring.py`
- Test: `tests/test_optimizer_portfolio_service.py`

- [ ] **Step 1: Write the failing scoring test**

```python
from src.services.optimizer_survival_scoring import classify_pair_result

def test_classify_pair_result_rejects_failed_forward_gate() -> None:
    decision = classify_pair_result(
        forward_metrics={"max_drawdown_pct": 6.4, "max_daily_loss_pct": 2.1, "net_profit": 400, "profit_factor": 1.2, "total_trades": 20},
        stress_metrics=[{"status": "passed", "metrics": {"max_drawdown_pct": 5.9}}],
        pair_dd_limit=6.0,
        pair_daily_limit=3.0,
    )
    assert decision["status"] == "REJECT"
    assert "forward" in decision["reason"].lower()
```

- [ ] **Step 2: Write the failing portfolio allocator test**

```python
from src.services.optimizer_portfolio_service import allocate_portfolio_weights

def test_allocate_portfolio_weights_reduces_pair_that_breaks_cap() -> None:
    allocation = allocate_portfolio_weights(
        [
            {"symbol": "EURUSD", "status": "PASS", "safety_rank": 0.95, "drawdown_curve": [0, -1, -2]},
            {"symbol": "GBPJPY", "status": "PASS", "safety_rank": 0.60, "drawdown_curve": [0, -2, -5]},
        ],
        portfolio_dd_limit=6.0,
        portfolio_daily_limit=3.0,
    )
    assert allocation["weights"]["EURUSD"] == 1.0
    assert allocation["weights"]["GBPJPY"] in {0.5, 0.0}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_optimizer_survival_scoring.py tests/test_optimizer_portfolio_service.py -v`
Expected: FAIL because the service modules do not exist.

- [ ] **Step 4: Implement the minimal scoring service**

```python
def classify_pair_result(*, forward_metrics: dict, stress_metrics: list[dict], pair_dd_limit: float, pair_daily_limit: float) -> dict:
    if forward_metrics["max_drawdown_pct"] > pair_dd_limit:
        return {"status": "REJECT", "reason": "Forward max drawdown exceeded internal gate"}
    if forward_metrics["max_daily_loss_pct"] > pair_daily_limit:
        return {"status": "REJECT", "reason": "Forward daily drawdown exceeded internal gate"}
    if forward_metrics["net_profit"] <= 0 or forward_metrics["profit_factor"] < 1.10 or forward_metrics["total_trades"] < 15:
        return {"status": "REJECT", "reason": "Forward survival gate failed"}

    stressed_failure = any(
        item["status"] == "failed" or item["metrics"].get("max_drawdown_pct", 0) > pair_dd_limit
        for item in stress_metrics
    )
    if stressed_failure:
        return {"status": "REDUCE_RISK", "reason": "Stress result approached or broke internal tolerance"}
    return {"status": "PASS", "reason": "Forward and stress gates passed"}
```

- [ ] **Step 5: Implement the minimal portfolio allocator**

```python
def allocate_portfolio_weights(pairs: list[dict], portfolio_dd_limit: float, portfolio_daily_limit: float) -> dict:
    weights: dict[str, float] = {}
    ordered = sorted(pairs, key=lambda row: row["safety_rank"], reverse=True)
    for pair in ordered:
        proposed = 1.0 if pair["status"] == "PASS" else 0.5
        weights[pair["symbol"]] = proposed
        combined_dd = sum(abs(min(row["drawdown_curve"])) * weights[row["symbol"]] for row in ordered if row["symbol"] in weights)
        if combined_dd > portfolio_dd_limit:
            weights[pair["symbol"]] = 0.5 if proposed == 1.0 else 0.0
    return {"weights": weights}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_optimizer_survival_scoring.py tests/test_optimizer_portfolio_service.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/services/optimizer_survival_scoring.py src/services/optimizer_portfolio_service.py tests/test_optimizer_survival_scoring.py tests/test_optimizer_portfolio_service.py
git commit -m "DEV-138: add optimizer survival scoring services"
```

## Task 4: Add News and Spread Context Services

**Files:**
- Create: `src/services/optimizer_market_context_service.py`
- Create: `src/services/optimizer_news_ingest.py`
- Test: `tests/test_optimizer_market_context_service.py`

- [ ] **Step 1: Write the failing context-service test**

```python
from src.services.optimizer_market_context_service import symbol_currencies, build_spread_stress_profiles

def test_symbol_currencies_maps_forex_pair() -> None:
    assert symbol_currencies("GBPJPY") == ["GBP", "JPY"]

def test_build_spread_stress_profiles_expands_baseline() -> None:
    profiles = build_spread_stress_profiles(baseline_spread=1.2, slippage_per_side=0.1)
    assert profiles["baseline"]["spread"] == 1.2
    assert profiles["spread_125"]["spread"] == 1.5
    assert profiles["spread_150"]["spread"] == 1.8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_optimizer_market_context_service.py -v`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement market-context helpers**

```python
def symbol_currencies(symbol: str) -> list[str]:
    symbol = symbol.upper()
    if len(symbol) >= 6 and symbol[:3].isalpha() and symbol[3:6].isalpha():
        return [symbol[:3], symbol[3:6]]
    return [symbol]

def build_spread_stress_profiles(*, baseline_spread: float, slippage_per_side: float) -> dict[str, dict[str, float]]:
    return {
        "baseline": {"spread": baseline_spread, "slippage_per_side": slippage_per_side},
        "spread_125": {"spread": baseline_spread * 1.25, "slippage_per_side": slippage_per_side},
        "spread_150": {"spread": baseline_spread * 1.50, "slippage_per_side": slippage_per_side},
        "spread_slippage": {"spread": baseline_spread * 1.25, "slippage_per_side": slippage_per_side * 2},
    }
```

- [ ] **Step 4: Stub the Trading Economics ingestion entry point**

```python
def normalize_trading_economics_event(event: dict) -> dict:
    return {
        "source": "tradingeconomics",
        "external_id": str(event["CalendarId"]),
        "event_time": event["Date"],
        "currency": event["Currency"],
        "country": event.get("Country"),
        "importance": int(event.get("Importance", 0)),
        "title": event["Event"],
        "payload": event,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_optimizer_market_context_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/optimizer_market_context_service.py src/services/optimizer_news_ingest.py tests/test_optimizer_market_context_service.py
git commit -m "DEV-138: add optimizer market context helpers"
```

## Task 5: Teach the Optimizer Runner to Emit Staged Survival Results

**Files:**
- Modify: `scripts/optimizer/models.py`
- Modify: `scripts/optimizer/optimizer.py`
- Test: `tests/test_api_optimizer_runs_strategy.py`

- [ ] **Step 1: Write the failing test around structured optimizer metrics**

```python
def test_backtest_result_serializes_pair_decision() -> None:
    result = BacktestResult(
        symbol="EURUSD",
        params={"ema_mode": "ema200_aligned"},
        net_profit=1200.0,
        total_trades=22,
        win_rate=55.0,
        profit_factor=1.24,
        max_drawdown_pct=4.6,
        score=78.0,
    )
    result.decision = {"status": "PASS", "risk_weight": 1.0}
    payload = result.to_dict()
    assert payload["decision"]["status"] == "PASS"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_api_optimizer_runs_strategy.py -k pair_decision -v`
Expected: FAIL because `BacktestResult` does not expose decision payloads yet.

- [ ] **Step 3: Extend optimizer models for decision and stress payloads**

```python
@dataclass
class BacktestResult:
    ...
    decision: dict[str, Any] = field(default_factory=dict)
    forward_metrics: dict[str, Any] = field(default_factory=dict)
    validation_metrics: dict[str, Any] = field(default_factory=dict)
    stress_results: list[dict[str, Any]] = field(default_factory=list)
```

- [ ] **Step 4: Add staged flow in `scripts/optimizer/optimizer.py`**

```python
decision = classify_pair_result(
    forward_metrics=forward_metrics,
    stress_metrics=stress_results,
    pair_dd_limit=self.dd_limit,
    pair_daily_limit=self.daily_dd_limit,
)
result.decision = {
    "status": decision["status"],
    "reason": decision["reason"],
    "risk_weight": 1.0 if decision["status"] == "PASS" else 0.5 if decision["status"] == "REDUCE_RISK" else 0.0,
}
```

- [ ] **Step 5: Emit new agent payloads to the API service**

```python
self._post_result_update(
    symbol,
    {
        "status": "completed",
        "params": result.params,
        "metrics": result.to_dict(),
    },
)
```

- [ ] **Step 6: Run focused tests**

Run: `PYTHONPATH=. pytest tests/test_api_optimizer_runs_strategy.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/optimizer/models.py scripts/optimizer/optimizer.py tests/test_api_optimizer_runs_strategy.py
git commit -m "DEV-138: emit staged survival optimizer results"
```

## Task 6: Add Enriched Optimizer API Endpoints

**Files:**
- Modify: `src/api_optimizer_runs.py`
- Test: `tests/test_optimizer_runs_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_get_optimizer_run_returns_portfolio_summary(client, optimizer_store) -> None:
    optimizer_store.portfolio_results["run-1"] = {"combined_max_drawdown_pct": 5.9}
    response = client.get("/api/optimizer/runs/run-1")
    assert response.status_code == 200
    assert response.json()["run"]["portfolio_result"]["combined_max_drawdown_pct"] == 5.9

def test_get_optimizer_run_stress_results(client) -> None:
    response = client.get("/api/optimizer/runs/run-1/stress-results")
    assert response.status_code == 200
    assert "results" in response.json()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runs_api.py -k "portfolio_summary or stress_results" -v`
Expected: FAIL because the endpoints and payload fields do not exist.

- [ ] **Step 3: Add read endpoints and richer response models**

```python
@router.get("/runs/{run_id}/trials", response_model=dict[str, Any])
def get_optimizer_run_trials(run_id: str, symbol: str | None = Query(None)) -> dict[str, Any]:
    service = get_optimizer_run_service()
    service.get_run(run_id)
    return {"trials": service.list_trials(run_id, symbol)}

@router.get("/runs/{run_id}/stress-results", response_model=dict[str, Any])
def get_optimizer_run_stress_results(run_id: str, symbol: str | None = Query(None)) -> dict[str, Any]:
    service = get_optimizer_run_service()
    service.get_run(run_id)
    return {"results": service.list_stress_results(run_id, symbol)}
```

- [ ] **Step 4: Enrich `get_optimizer_run` response**

```python
@router.get("/runs/{run_id}", response_model=dict[str, Any])
def get_optimizer_run(run_id: str) -> dict[str, Any]:
    run = get_optimizer_run_service().get_run(run_id)
    return {"run": run}
```

- [ ] **Step 5: Run focused API tests**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runs_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api_optimizer_runs.py tests/test_optimizer_runs_api.py
git commit -m "DEV-138: add enriched optimizer detail endpoints"
```

## Task 7: Extend Frontend API Types and Query Hooks

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useOptimizerRuns.ts`
- Test: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Write the failing hook-level UI test**

```tsx
it('renders portfolio overview metrics from enriched run payload', async () => {
  render(<OptimizerRunsWorkspace />);
  expect(await screen.findByText(/combined max dd/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: FAIL because the workspace does not request or render portfolio metrics yet.

- [ ] **Step 3: Extend API types**

```ts
export type OptimizerPortfolioResultApi = {
  combined_max_drawdown_pct?: number;
  combined_daily_drawdown_pct?: number;
  worst_day_pct?: number;
  weights?: Record<string, number>;
};

export type OptimizerRunApi = {
  ...
  portfolio_result?: OptimizerPortfolioResultApi | null;
};
```

- [ ] **Step 4: Add new query hooks**

```ts
export function useOptimizerRunStressResults(runId: string | null, symbol?: string | null) {
  return useQuery({
    queryKey: ['optimizer-run-stress-results', runId, symbol],
    queryFn: async () => apiClient.getOptimizerRunStressResults(runId!, symbol ?? undefined),
    enabled: Boolean(runId),
    refetchInterval: 5000,
  });
}
```

- [ ] **Step 5: Run the frontend test**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS or narrower failure only in the still-unfinished workspace UI.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useOptimizerRuns.ts frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx
git commit -m "DEV-138: add frontend optimizer survival data hooks"
```

## Task 8: Build the Analyst Optimizer Workspace

**Files:**
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
- Optionally Create: `frontend/src/components/optimizer/PortfolioOverviewCard.tsx`
- Optionally Create: `frontend/src/components/optimizer/PairAnalysisTable.tsx`
- Optionally Create: `frontend/src/components/optimizer/PairDrilldownPanel.tsx`
- Optionally Create: `frontend/src/components/optimizer/RunComparisonPanel.tsx`
- Test: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Write the failing UI tests for the analyst layout**

```tsx
it('shows pair decisions and risk weights', async () => {
  render(<OptimizerRunsWorkspace />);
  expect(await screen.findByText(/approved pairs/i)).toBeInTheDocument();
  expect(await screen.findByText(/risk weight/i)).toBeInTheDocument();
});

it('opens pair drill-down details', async () => {
  render(<OptimizerRunsWorkspace />);
  await userEvent.click(await screen.findByRole('button', { name: /EURUSD/i }));
  expect(await screen.findByText(/validation vs forward/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: FAIL because the current UI has only the basic launcher/table/timeline.

- [ ] **Step 3: Build the portfolio overview and pair analysis surface**

```tsx
<section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
  <PortfolioOverviewCard run={selectedRun} />
  <Card>
    <CardHeader>
      <CardTitle>Run Config</CardTitle>
      <CardDescription>Internal pair and portfolio safety limits.</CardDescription>
    </CardHeader>
    <CardContent>{/* existing launcher inputs plus new fields */}</CardContent>
  </Card>
</section>
```

- [ ] **Step 4: Build the pair grid and drill-down**

```tsx
<PairAnalysisTable
  results={results}
  onSelectSymbol={setSelectedSymbol}
  selectedSymbol={selectedSymbol}
/>
<PairDrilldownPanel
  result={selectedPairResult}
  stressResults={stressResults}
/>
```

- [ ] **Step 5: Add run comparison and reasons**

```tsx
<RunComparisonPanel
  runs={runs}
  selectedRunId={selectedRunId}
  comparisonRunId={comparisonRunId}
/>
```

- [ ] **Step 6: Run the frontend test suite**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx frontend/src/components/optimizer/*.tsx frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx
git commit -m "DEV-138: upgrade optimizer workspace to analyst UI"
```

## Task 9: Integrate End-to-End Persistence and UI Wiring

**Files:**
- Modify: `src/services/optimizer_run_service.py`
- Modify: `src/api_optimizer_runs.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useOptimizerRuns.ts`
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
- Test: `tests/test_optimizer_runs_api.py`
- Test: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Write the failing end-to-end tests**

```python
def test_run_details_include_results_trials_stress_and_portfolio(client) -> None:
    response = client.get("/api/optimizer/runs/run-1")
    assert response.status_code == 200
    payload = response.json()["run"]
    assert "portfolio_result" in payload
```

```tsx
it('renders saved run details from enriched API payload', async () => {
  render(<OptimizerRunsWorkspace />);
  expect(await screen.findByText(/portfolio overview/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runs_api.py -v`
Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: One or both fail until the full payload wiring is complete.

- [ ] **Step 3: Finish response wiring and polling**

```ts
const { data: runResponse } = useOptimizerRun(selectedRunId);
const selectedRun = runResponse?.run ?? null;
```

```python
return {
    "run": run,
    "results": self.list_results(run_id),
    "portfolio_result": self.get_portfolio_result(run_id),
}
```

- [ ] **Step 4: Run the backend and frontend tests again**

Run: `PYTHONPATH=. pytest tests/test_optimizer_runs_api.py tests/test_optimizer_run_service.py -v`
Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/optimizer_run_service.py src/api_optimizer_runs.py frontend/src/lib/api.ts frontend/src/hooks/useOptimizerRuns.ts frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx tests/test_optimizer_runs_api.py frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx
git commit -m "DEV-138: wire optimizer survival data end to end"
```

## Task 10: Final Verification and Docs Sync

**Files:**
- Modify: `scripts/optimizer/README.md`
- Test: `tests/test_optimizer_run_service.py`
- Test: `tests/test_optimizer_runs_api.py`
- Test: `tests/test_optimizer_survival_scoring.py`
- Test: `tests/test_optimizer_portfolio_service.py`
- Test: `tests/test_optimizer_market_context_service.py`
- Test: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Document the new optimizer modes and artifacts**

```md
## Survival Optimizer Outputs

- pair decisions: PASS / REDUCE_RISK / REJECT
- stress results: spread, slippage, news, trend
- portfolio summary: combined drawdown, worst day, weights
- saved artifacts: trials, stress results, portfolio result, JSON snapshots
```

- [ ] **Step 2: Run the backend test suite for optimizer changes**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py tests/test_optimizer_survival_scoring.py tests/test_optimizer_portfolio_service.py tests/test_optimizer_market_context_service.py -v`
Expected: PASS

- [ ] **Step 3: Run the frontend workspace tests**

Run: `cd frontend && npx vitest run src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 4: Run the build check**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/optimizer/README.md tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py tests/test_optimizer_survival_scoring.py tests/test_optimizer_portfolio_service.py tests/test_optimizer_market_context_service.py frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx
git commit -m "DEV-138: verify optimizer survival upgrade"
```

## Self-Review

### Spec Coverage

- survival-first scoring and forward gates: covered in Tasks 3 and 5
- stored run artifacts and reuse: covered in Tasks 1, 2, and 9
- Trading Economics news and spread stress: covered in Tasks 1 and 4
- portfolio simulation and weighting: covered in Task 3
- enriched API surface: covered in Task 6
- advanced analyst UI: covered in Tasks 7, 8, and 9

### Placeholder Scan

No `TODO`, `TBD`, or “implement later” placeholders remain. Each task includes exact files, concrete tests, explicit commands, and the minimal code shape expected in the step.

### Type Consistency

The plan consistently uses:

- `PASS`, `REDUCE_RISK`, `REJECT` for pair decisions
- `optimizer_run_trials`, `optimizer_run_stress_tests`, and `optimizer_portfolio_results` for persistence
- `portfolio_result` for the enriched run payload

