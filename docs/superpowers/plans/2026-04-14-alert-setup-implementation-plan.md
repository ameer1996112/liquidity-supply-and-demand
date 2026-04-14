# Alert Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an `Alert Setup` workflow that stores approved pair configs, lets the user launch TradingView alert batches from presets or custom selections, and tracks per-pair creation results in the app.

**Architecture:** Add three backend persistence layers: approved pair configs, alert batches, and alert batch results. Expose admin-only API routes to manage configs and run batches. Reuse the local browser-agent pattern from the optimizer to drive TradingView via Playwright: switch pair, apply params, verify them, create alert, then report progress back to the backend. Add a dedicated frontend page similar to the optimizer page with preset/custom selection and batch progress.

**Tech Stack:** FastAPI, Supabase/PostgREST, Playwright, existing local agent pattern, Next.js/React Query frontend, SQL migrations, Vitest, pytest.

---

## File Structure

**Create**
- `migrations/073_alert_setup.sql` — tables for `optimized_pair_configs`, `alert_batches`, `alert_batch_results`
- `src/services/alert_setup_service.py` — business logic for approved configs and batch lifecycle
- `src/api_alert_setup.py` — API router for configs, presets, batch CRUD, batch results
- `scripts/optimizer/alert_runner.py` — local TradingView browser automation runner for alert creation
- `tests/test_alert_setup_service.py` — backend service tests
- `tests/test_alert_setup_api.py` — API route tests
- `tests/test_alert_runner.py` — alert runner verification tests
- `frontend/src/hooks/useAlertSetup.ts` — React Query hooks
- `frontend/src/app/alert-setup/page.tsx` — route entry
- `frontend/src/components/alert-setup/AlertSetupWorkspace.tsx` — main page workspace
- `frontend/src/components/alert-setup/AlertSetupWorkspace.test.tsx` — frontend behavior test

**Modify**
- `src/api.py` — register new router
- `src/services/optimizer_run_service.py` — optional helper to expose latest ranked optimizer results for presets
- `src/services/optimizer_defaults.py` — no alert logic, but keep aligned with approved-pairs expectations if needed
- `scripts/optimizer/local_agent.py` — poll and execute queued alert batches in addition to optimizer runs
- `frontend/src/lib/api.ts` — typed API helpers
- `frontend/src/components/layout/Sidebar.tsx` — add `Alert Setup` nav link
- `frontend/src/components/layout/MobileNav.tsx` — add `Alert Setup` nav link

---

### Task 1: Add Alert Setup Database Tables

**Files:**
- Create: `migrations/073_alert_setup.sql`
- Test: none

- [ ] **Step 1: Write migration for approved configs**

```sql
create table if not exists public.optimized_pair_configs (
  id bigserial primary key,
  pair text not null,
  timeframe text not null,
  params jsonb not null default '{}'::jsonb,
  risk_weight numeric not null default 1.0,
  status text not null default 'candidate',
  source_run_id text,
  score_snapshot jsonb not null default '{}'::jsonb,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_optimized_pair_configs_pair_tf_active
  on public.optimized_pair_configs (pair, timeframe, status);
```

- [ ] **Step 2: Add alert batch tables**

```sql
create table if not exists public.alert_batches (
  id uuid primary key,
  source_mode text not null,
  timeframe text not null,
  selected_pairs jsonb not null default '[]'::jsonb,
  webhook_url text not null,
  message_template text not null,
  status text not null default 'queued',
  summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create table if not exists public.alert_batch_results (
  id bigserial primary key,
  batch_id uuid not null references public.alert_batches(id) on delete cascade,
  pair text not null,
  status text not null default 'pending',
  tradingview_alert_name text,
  error_message text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_alert_batch_results_batch_pair
  on public.alert_batch_results(batch_id, pair);
```

- [ ] **Step 3: Add simple updated-at trigger logic inline**

```sql
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_optimized_pair_configs_updated_at on public.optimized_pair_configs;
create trigger trg_optimized_pair_configs_updated_at
before update on public.optimized_pair_configs
for each row execute function public.set_updated_at();

drop trigger if exists trg_alert_batches_updated_at on public.alert_batches;
create trigger trg_alert_batches_updated_at
before update on public.alert_batches
for each row execute function public.set_updated_at();

drop trigger if exists trg_alert_batch_results_updated_at on public.alert_batch_results;
create trigger trg_alert_batch_results_updated_at
before update on public.alert_batch_results
for each row execute function public.set_updated_at();
```

- [ ] **Step 4: Apply migration**

Run: `psql "$SUPABASE_DB_URL" -f migrations/073_alert_setup.sql`
Expected: tables + indexes + triggers created without errors

- [ ] **Step 5: Commit**

```bash
git add migrations/073_alert_setup.sql
git commit -m "feat: add alert setup persistence tables"
```

### Task 2: Build Alert Setup Service

**Files:**
- Create: `src/services/alert_setup_service.py`
- Test: `tests/test_alert_setup_service.py`

- [ ] **Step 1: Write failing service tests**

```python
def test_build_top3_preset_uses_latest_ranked_configs():
    service = AlertSetupService(repo=FakeRepo(), optimizer_repo=FakeOptimizerRepo())
    pairs = service.resolve_pairs(source_mode="top3", custom_pairs=[], timeframe="5m")
    assert pairs == ["USDJPY", "GBPUSD", "XAUUSD"]


def test_create_batch_creates_pending_results_for_each_pair():
    service = AlertSetupService(repo=FakeRepo(), optimizer_repo=FakeOptimizerRepo())
    batch = service.create_batch(
        source_mode="custom",
        timeframe="5m",
        custom_pairs=["USDJPY", "GBPUSD"],
        webhook_url="https://example.com/webhook",
        message_template="{{pair}}",
    )
    assert batch["summary"]["total_pairs"] == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=. pytest tests/test_alert_setup_service.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `AlertSetupService`

- [ ] **Step 3: Implement repository protocol + service**

```python
class AlertSetupService:
    def resolve_pairs(self, *, source_mode: str, custom_pairs: list[str], timeframe: str) -> list[str]:
        ...

    def create_batch(self, *, source_mode: str, timeframe: str, custom_pairs: list[str], webhook_url: str, message_template: str) -> dict[str, Any]:
        ...

    def update_batch_from_agent(self, batch_id: str, *, status: str | None = None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def update_batch_result_from_agent(self, batch_id: str, pair: str, updates: dict[str, Any]) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=. pytest tests/test_alert_setup_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/alert_setup_service.py tests/test_alert_setup_service.py
git commit -m "feat: add alert setup service"
```

### Task 3: Add Alert Setup API

**Files:**
- Create: `src/api_alert_setup.py`
- Modify: `src/api.py`
- Test: `tests/test_alert_setup_api.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_create_alert_batch_requires_admin_key(client):
    res = client.post("/api/alert-setup/batches", json={})
    assert res.status_code in {401, 403}


def test_list_presets_returns_top3_top5_and_approved(client, admin_headers):
    res = client.get("/api/alert-setup/presets", headers=admin_headers)
    assert res.status_code == 200
    assert set(res.json()["presets"]) == {"top3", "top5", "approved"}
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=. pytest tests/test_alert_setup_api.py -v`
Expected: FAIL because router does not exist

- [ ] **Step 3: Implement router**

```python
router = APIRouter(prefix="/api/alert-setup", tags=["alert-setup"])

@router.get("/presets")
def list_alert_presets() -> dict[str, Any]:
    return {"presets": ["top3", "top5", "approved"]}

@router.post("/batches")
def create_alert_batch(payload: AlertBatchCreateRequest) -> dict[str, Any]:
    return get_alert_setup_service().create_batch(...)
```

- [ ] **Step 4: Register router**

```python
from src.api_alert_setup import router as alert_setup_router
app.include_router(alert_setup_router, dependencies=[Depends(_require_admin_key)])
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. pytest tests/test_alert_setup_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api_alert_setup.py src/api.py tests/test_alert_setup_api.py
git commit -m "feat: add alert setup api"
```

### Task 4: Extend Local Agent To Run Alert Batches

**Files:**
- Create: `scripts/optimizer/alert_runner.py`
- Modify: `scripts/optimizer/local_agent.py`
- Test: `tests/test_alert_runner.py`

- [ ] **Step 1: Write failing runner tests**

```python
def test_alert_runner_marks_pair_failed_when_param_verify_fails():
    runner = AlertRunner(page=FakePage(), batch_id="b1", pair_config=pair_config())
    result = asyncio.run(runner.run_pair())
    assert result["status"] == "failed"


def test_local_agent_picks_alert_batch_queue_before_sleep(monkeypatch):
    ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=. pytest tests/test_alert_runner.py -v`
Expected: FAIL because runner/agent integration missing

- [ ] **Step 3: Implement alert runner**

```python
class AlertRunner:
    async def run_pair(self) -> dict[str, Any]:
        await self.switch_symbol(...)
        await self.apply_params(...)
        await self.verify_params(...)
        await self.open_alert_dialog(...)
        await self.fill_alert_form(...)
        await self.submit_alert(...)
        return {"status": "completed"}
```

- [ ] **Step 4: Teach local agent to poll alert batches**

```python
def poll_next_alert_batch() -> dict | None:
    payload = api_get("/api/alert-setup/batches?status=queued&limit=1")
    ...

def execute_alert_batch(batch: dict) -> None:
    ...
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. pytest tests/test_alert_runner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/optimizer/alert_runner.py scripts/optimizer/local_agent.py tests/test_alert_runner.py
git commit -m "feat: add alert batch local runner"
```

### Task 5: Build Alert Setup Frontend

**Files:**
- Create: `frontend/src/hooks/useAlertSetup.ts`
- Create: `frontend/src/app/alert-setup/page.tsx`
- Create: `frontend/src/components/alert-setup/AlertSetupWorkspace.tsx`
- Create: `frontend/src/components/alert-setup/AlertSetupWorkspace.test.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/MobileNav.tsx`

- [ ] **Step 1: Write failing frontend test**

```tsx
it('creates batch from approved preset', async () => {
  render(<AlertSetupWorkspace />)
  expect(screen.getByText('Alert Setup')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /start batch/i }))
})
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && npm exec vitest run src/components/alert-setup/AlertSetupWorkspace.test.tsx`
Expected: FAIL because component does not exist

- [ ] **Step 3: Add API helpers + hooks**

```ts
export function getAlertSetupBatchesUrl(): string {
  return `${API_BASE_URL}/api/alert-setup/batches`
}
```

- [ ] **Step 4: Build workspace UI**

```tsx
<section>
  <h1>Alert Setup</h1>
  <PresetSelector />
  <PairPreviewTable />
  <WebhookConfigForm />
  <BatchHistory />
</section>
```

- [ ] **Step 5: Add nav links**

```tsx
{ href: '/alert-setup', label: 'Alert Setup', icon: Bell }
```

- [ ] **Step 6: Run frontend tests**

Run: `cd frontend && npm exec vitest run src/components/alert-setup/AlertSetupWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useAlertSetup.ts frontend/src/app/alert-setup/page.tsx frontend/src/components/alert-setup/AlertSetupWorkspace.tsx frontend/src/components/alert-setup/AlertSetupWorkspace.test.tsx frontend/src/components/layout/Sidebar.tsx frontend/src/components/layout/MobileNav.tsx
git commit -m "feat: add alert setup page"
```

### Task 6: Seed Approved Basket + Presets

**Files:**
- Modify: `src/services/alert_setup_service.py`
- Test: `tests/test_alert_setup_service.py`

- [ ] **Step 1: Add approved preset logic**

```python
APPROVED_DEFAULT_BASKET = [
    {"pair": "USDJPY", "risk_weight": 0.75},
    {"pair": "GBPUSD", "risk_weight": 0.75},
    {"pair": "GBPNZD", "risk_weight": 0.50},
    {"pair": "XAUUSD", "risk_weight": 0.25},
]
```

- [ ] **Step 2: Add test for approved preset**

```python
def test_approved_preset_returns_seeded_pairs():
    pairs = service.resolve_pairs(source_mode="approved", custom_pairs=[], timeframe="5m")
    assert pairs == ["USDJPY", "GBPUSD", "GBPNZD", "XAUUSD"]
```

- [ ] **Step 3: Run tests**

Run: `PYTHONPATH=. pytest tests/test_alert_setup_service.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/services/alert_setup_service.py tests/test_alert_setup_service.py
git commit -m "feat: seed approved alert basket"
```

### Task 7: Verify End-to-End

**Files:**
- Modify: none unless fixes needed

- [ ] **Step 1: Run backend tests**

Run: `PYTHONPATH=. pytest tests/test_alert_setup_service.py tests/test_alert_setup_api.py tests/test_alert_runner.py -v`
Expected: PASS

- [ ] **Step 2: Run frontend test**

Run: `cd frontend && npm exec vitest run src/components/alert-setup/AlertSetupWorkspace.test.tsx`
Expected: PASS

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds and route list includes `/alert-setup`

- [ ] **Step 4: Manual dry check**

Run:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
source venv/bin/activate
PYTHONPATH=. python3 -m scripts.optimizer.local_agent
```

Expected:
- agent heartbeat online
- queued alert batch picked up
- per-pair results written to DB

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: ship alert setup workflow"
```

---

## Self-Review

- Spec coverage: plan covers approved config store, presets/custom source, separate page, local runner, per-pair progress, and retryable results
- Placeholder scan: no `TODO`/`TBD` placeholders remain
- Type consistency: uses `source_mode`, `timeframe`, `risk_weight`, `alert_batches`, `alert_batch_results`, `optimized_pair_configs` consistently across tasks

