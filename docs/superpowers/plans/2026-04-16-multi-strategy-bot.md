# Multi-Strategy Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the trading system from a single globally active strategy assumption into a strategy-first multi-strategy platform where every alert, guard decision, notification, optimizer run, and UI surface is tagged and filtered by strategy.

**Architecture:** Keep one TradingView webhook channel, but require `strategy_id` and `strategy_version` on every entry alert. For v1, use `strategy_configs.slug` as the canonical `strategy_id`, and compare the alert’s `strategy_version` to the row’s existing `version` column as a string. Resolve strategy identity at webhook ingest, stamp that context onto persisted signals, carry it through worker/risk/notifications, and expose strategy filters across analytics, optimizer, dashboard, and notification surfaces. Strategy-level rules stay isolated, while account-level guardrails remain shared above them.

**Tech Stack:** FastAPI, Pydantic, Supabase, Redis, Python worker pipeline, Next.js App Router, TanStack Query, Pytest, Vitest

---

## File Map

**Database**
- Create: `migrations/079_multi_strategy_identity.sql`
  - Add strategy identity columns and indexes to signal and optimizer storage

**Backend**
- Modify: `src/core/signal.py`
  - Require `strategy_id` and `strategy_version` on entry payloads
- Create: `src/services/strategy_registry.py`
  - Resolve active strategy rows by slug/version
  - Validate config and expose a typed resolved strategy object
- Modify: `src/services/strategy_config.py`
  - Reuse typed config models for resolved strategy objects and per-strategy routing
- Modify: `src/api.py`
  - Reject missing, unknown, inactive, or version-mismatched strategies before enqueueing signals
  - Stamp resolved strategy context onto saved signal payloads
- Modify: `src/api_strategies.py`
  - Remove single-global-activation behavior
  - Keep multiple strategies active at once
- Modify: `src/api_webhook_read.py`
  - Return strategy identity in signal list/read endpoints
  - Add optional strategy filters
- Modify: `src/worker.py`
  - Stop assuming one global active strategy
  - Load strategy context from the signal record/payload
- Modify: `src/pipeline/account_guards.py`
  - Evaluate strategy-level filters and risk overrides from the resolved strategy
- Modify: `src/core/risk_engine.py`
  - Accept strategy-level risk overrides without changing account-level protections
- Modify: `src/services/notification_service.py`
  - Show strategy identity in signal, guard, and close notifications
- Modify: `src/services/optimizer_run_service.py`
  - Store optimizer runs per strategy/version
- Modify: `src/api_optimizer_runs.py`
  - Require strategy identity on new runs and add read filters
- Modify: `src/api_dashboard.py`
  - Add strategy-aware dashboard filters and aggregate fields
- Modify: `src/api_analytics_signals_perf.py`
  - Add strategy and version filtering for performance views
- Modify: `src/api_notifications.py`
  - Include strategy identity in notification read models and routing metadata

**Frontend**
- Modify: `frontend/src/types/trading.ts`
  - Add strategy fields to signal types and stats payloads
- Create: `frontend/src/components/strategy/StrategyFilter.tsx`
  - Reusable strategy selector for pages and panels
- Modify: `frontend/src/components/dashboard/RecentSignalsPanel.tsx`
  - Add strategy filter control and strategy badges
- Modify: `frontend/src/components/dashboard/SignalTable.tsx`
  - Render strategy/version columns or badges
- Modify: `frontend/src/app/analytics/page.tsx`
  - Add strategy filter state and wire filtered API requests
- Modify: `frontend/src/app/notifications/page.tsx`
  - Show strategy identity in event rows and filters
- Modify: `frontend/src/components/notifications/RoutingPanel.tsx`
  - Display strategy-aware notification routing context
- Modify: `frontend/src/app/optimizer/page.tsx`
  - Require strategy selection before creating runs
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
  - Render strategy/version per optimizer run

**Tests**
- Create: `tests/test_strategy_registry.py`
  - Resolution tests for unknown, inactive, and version-mismatched strategies
- Modify: `tests/test_signal_transport.py`
  - Webhook validation and strategy stamping tests
- Modify: `tests/test_optimizer_run_service.py`
  - Optimizer run persistence now keyed by strategy/version
- Modify: `tests/test_optimizer_runs_api.py`
  - API coverage for required strategy identity and list filters
- Modify: `tests/test_notification_service.py`
  - Notification titles/fields include strategy context
- Create: `tests/test_api_dashboard_strategy_filters.py`
  - Dashboard and analytics filters by strategy/version
- Modify: `frontend/src/components/dashboard/RecentSignalsPanel.test.tsx`
  - UI shows strategy badges and filter changes
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`
  - Strategy selection gates new optimizer runs

**Docs**
- Modify: `docs/superpowers/specs/2026-04-16-multi-strategy-bot-design.md`
  - Update the approved spec only if implementation details diverge from the `slug + version` choice

---

### Task 1: Add Strategy Identity Persistence And Resolution

**Files:**
- Create: `migrations/079_multi_strategy_identity.sql`
- Modify: `src/core/signal.py`
- Create: `src/services/strategy_registry.py`
- Modify: `tests/test_signal_transport.py`
- Create: `tests/test_strategy_registry.py`

- [ ] **Step 1: Write the failing backend tests for required alert identity and strategy resolution**

```python
def test_entry_payload_requires_strategy_identity():
    from pydantic import ValidationError
    from src.core.signal import EntryWebhookPayload

    with pytest.raises(ValidationError):
        EntryWebhookPayload.model_validate(
            {
                "symbol": "EURUSD",
                "side": "buy",
                "entry": 1.10,
                "sl": 1.09,
                "tp": 1.12,
                "size": 1.0,
            }
        )
```

```python
def test_resolve_strategy_rejects_unknown_slug(fake_supabase):
    from src.services.strategy_registry import UnknownStrategyError, resolve_strategy_or_raise

    with pytest.raises(UnknownStrategyError):
        resolve_strategy_or_raise(
            supabase=fake_supabase,
            strategy_id="liq_sd_v1",
            strategy_version="1",
        )
```

```python
def test_resolve_strategy_rejects_version_mismatch(fake_supabase):
    fake_supabase.seed_strategy(
        {"id": 7, "slug": "liq_sd_v1", "name": "Liquidity", "version": 2, "is_active": True, "config": {"name": "Liquidity"}}
    )

    from src.services.strategy_registry import StrategyVersionMismatchError, resolve_strategy_or_raise

    with pytest.raises(StrategyVersionMismatchError):
        resolve_strategy_or_raise(
            supabase=fake_supabase,
            strategy_id="liq_sd_v1",
            strategy_version="1",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_signal_transport.py tests/test_strategy_registry.py -v`

Expected: FAIL because entry payloads do not require strategy identity and the registry service does not exist yet.

- [ ] **Step 3: Add the migration for signal and optimizer identity**

```sql
alter table trading_signals
  add column if not exists strategy_id text,
  add column if not exists strategy_version text,
  add column if not exists strategy_name text,
  add column if not exists strategy_config_id bigint;

create index if not exists idx_trading_signals_strategy_id_created_at
  on trading_signals (strategy_id, created_at desc);

alter table optimizer_runs
  add column if not exists strategy_id text,
  add column if not exists strategy_version text;

create index if not exists idx_optimizer_runs_strategy_id_created_at
  on optimizer_runs (strategy_id, created_at desc);
```

- [ ] **Step 4: Require strategy identity on entry payloads**

```python
class EntryWebhookPayload(BaseModel):
    strategy_id: str = Field(..., min_length=1, description="Canonical strategy slug from strategy_configs.slug")
    strategy_version: str = Field(..., min_length=1, description="Expected active strategy version")
    symbol: str = Field(..., min_length=1, description="Instrument symbol")
    ...
```

- [ ] **Step 5: Implement the strategy registry service**

```python
@dataclass(frozen=True)
class ResolvedStrategy:
    record_id: int
    strategy_id: str
    strategy_version: str
    name: str
    config: StrategyConfig
    is_active: bool
```

```python
def resolve_strategy_or_raise(
    *,
    strategy_id: str,
    strategy_version: str,
    supabase=None,
) -> ResolvedStrategy:
    sb = supabase or get_api_supabase()
    resp = (
        sb.table("strategy_configs")
        .select("id, slug, name, version, is_active, config")
        .eq("slug", strategy_id)
        .limit(1)
        .execute()
    )
    ...
    if not row["is_active"]:
        raise InactiveStrategyError(strategy_id)
    if str(row["version"]) != str(strategy_version):
        raise StrategyVersionMismatchError(strategy_id, strategy_version, str(row["version"]))
    cfg = validate_strategy_config(row["config"])
    return ResolvedStrategy(...)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_signal_transport.py tests/test_strategy_registry.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add migrations/079_multi_strategy_identity.sql src/core/signal.py src/services/strategy_registry.py tests/test_signal_transport.py tests/test_strategy_registry.py
git commit -m "DEV-115: add strategy identity primitives"
```

### Task 2: Resolve Strategy At Webhook Ingest And Stamp Signal Context

**Files:**
- Modify: `src/api.py`
- Modify: `src/api_webhook_read.py`
- Modify: `tests/test_signal_transport.py`

- [ ] **Step 1: Write the failing webhook tests for reject-on-missing-strategy and successful stamping**

```python
def test_entry_webhook_rejects_inactive_strategy(client, fake_supabase):
    fake_supabase.seed_strategy(
        {"id": 7, "slug": "liq_sd_v1", "name": "Liquidity", "version": 1, "is_active": False, "config": {"name": "Liquidity"}}
    )

    response = client.post(
        "/webhook",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.10,
            "sl": 1.09,
            "tp": 1.12,
            "size": 1.0,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "inactive_strategy"
```

```python
def test_entry_webhook_stamps_strategy_context_on_saved_signal(client, fake_supabase):
    fake_supabase.seed_strategy(
        {"id": 7, "slug": "liq_sd_v1", "name": "Liquidity", "version": 1, "is_active": True, "config": {"name": "Liquidity"}}
    )

    response = client.post("/webhook", json=VALID_MULTI_STRATEGY_SIGNAL)
    assert response.status_code == 200

    saved = fake_supabase.last_insert("trading_signals")
    assert saved["strategy_id"] == "liq_sd_v1"
    assert saved["strategy_version"] == "1"
    assert saved["strategy_name"] == "Liquidity"
    assert saved["strategy_config_id"] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_signal_transport.py -k strategy -v`

Expected: FAIL because the webhook path does not resolve or stamp strategies yet.

- [ ] **Step 3: Resolve strategy before enqueueing or persisting**

```python
payload = validate_webhook_payload(body)
resolved = resolve_strategy_or_raise(
    strategy_id=payload["strategy_id"],
    strategy_version=payload["strategy_version"],
)

payload["strategy_name"] = resolved.name
payload["strategy_config_id"] = resolved.record_id
payload["strategy_config_snapshot"] = resolved.config.model_dump()
```

- [ ] **Step 4: Return strategy fields from signal read APIs**

```python
resp = (
    sb.table("trading_signals")
    .select("id, created_at, symbol, side, status, strategy_id, strategy_version, strategy_name, ...")
    .order("created_at", desc=True)
    .execute()
)
```

```python
@router.get("/signals")
def list_signals(strategy_id: str | None = None, strategy_version: str | None = None, ...):
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_signal_transport.py -k strategy -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api.py src/api_webhook_read.py tests/test_signal_transport.py
git commit -m "DEV-115: resolve strategy at webhook ingest"
```

### Task 3: Make Worker, Guards, And Risk Strategy-Aware

**Files:**
- Modify: `src/worker.py`
- Modify: `src/pipeline/account_guards.py`
- Modify: `src/core/risk_engine.py`
- Modify: `tests/test_signal_transport.py`

- [ ] **Step 1: Write the failing worker/guard tests for strategy-level filters**

```python
def test_strategy_symbol_filter_blocks_unapproved_symbol():
    decision = run_account_guards(
        signal={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "symbol": "GBPUSD",
            "strategy_config_snapshot": {
                "name": "Liquidity",
                "signal_filters": {"symbols": ["EURUSD"], "sessions": []},
                "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 1.5},
            },
        },
        ...
    )

    assert decision.allowed is False
    assert decision.reason == "strategy_symbol_not_allowed"
```

```python
def test_strategy_risk_override_is_passed_to_risk_engine():
    sizing = build_position_size(
        signal={"strategy_config_snapshot": {"risk": {"risk_percent": 0.35}}},
        ...
    )

    assert sizing.metadata["risk_percent_used"] == 0.35
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_signal_transport.py -k 'strategy_symbol or risk_override' -v`

Expected: FAIL because worker and guards still assume one globally active strategy.

- [ ] **Step 3: Remove the global-active lookup from the worker path**

```python
strategy_snapshot = signal.get("strategy_config_snapshot") or {}
strategy_cfg = validate_strategy_config(strategy_snapshot)

guard_result = run_account_guards(
    signal=signal,
    profile=profile,
    strategy_config=strategy_cfg,
)
```

- [ ] **Step 4: Apply strategy-level symbol/session/RR/risk settings before account-level protections**

```python
if strategy_config.signal_filters.symbols and signal["symbol"] not in strategy_config.signal_filters.symbols:
    return GuardDecision.blocked("strategy_symbol_not_allowed")

if strategy_config.risk.min_rr_ratio and rr_ratio < strategy_config.risk.min_rr_ratio:
    return GuardDecision.blocked("strategy_min_rr_not_met")
```

```python
risk_percent = strategy_config.risk.risk_percent or settings.risk_percent
position = build_position_size(..., risk_percent_override=risk_percent)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_signal_transport.py -k 'strategy_symbol or risk_override' -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/worker.py src/pipeline/account_guards.py src/core/risk_engine.py tests/test_signal_transport.py
git commit -m "DEV-115: route worker with strategy context"
```

### Task 4: Add Strategy Context To Notifications And Operator Surfaces

**Files:**
- Modify: `src/services/notification_service.py`
- Modify: `src/api_notifications.py`
- Modify: `tests/test_notification_service.py`

- [ ] **Step 1: Write the failing notification tests**

```python
def test_format_signal_includes_strategy_badge():
    payload = NotificationService().format_signal(
        {
            "id": 12,
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.10,
            "sl": 1.09,
            "tp": 1.12,
            "size": 1.0,
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "strategy_name": "Liquidity",
        }
    )

    assert payload.fields["Strategy"] == "liq_sd_v1@1"
    assert "liq_sd_v1@1" in payload.title
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_notification_service.py -k strategy -v`

Expected: FAIL because notifications do not include strategy context yet.

- [ ] **Step 3: Add strategy identity to notification payload formatting**

```python
strategy_badge = _format_strategy_badge(signal)
trade_fields["Strategy"] = strategy_badge

return NotificationPayload(
    title=f"[{strategy_badge}] {side} Signal - {symbol}",
    ...
)
```

```python
def _format_strategy_badge(signal: dict[str, Any]) -> str:
    strategy_id = signal.get("strategy_id") or "legacy"
    strategy_version = signal.get("strategy_version") or "?"
    return f"{strategy_id}@{strategy_version}"
```

- [ ] **Step 4: Expose strategy fields on notification read endpoints**

```python
@router.get("/events")
def list_notification_events(strategy_id: str | None = None, ...):
    ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_notification_service.py -k strategy -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/notification_service.py src/api_notifications.py tests/test_notification_service.py
git commit -m "DEV-115: add strategy-aware notifications"
```

### Task 5: Make Optimizer Runs Strategy-Aware

**Files:**
- Modify: `src/services/optimizer_run_service.py`
- Modify: `src/api_optimizer_runs.py`
- Modify: `tests/test_optimizer_run_service.py`
- Modify: `tests/test_optimizer_runs_api.py`

- [ ] **Step 1: Write the failing optimizer tests**

```python
def test_start_run_requires_strategy_identity(service):
    with pytest.raises(ValueError, match="strategy_id"):
        service.start_run(
            mode="grid",
            workers=2,
            pairs=["EURUSD"],
            n_trials=10,
            dd_limit=4.0,
            dry_run=True,
        )
```

```python
def test_start_run_persists_strategy_id_and_version(service, repo):
    run = service.start_run(
        strategy_id="liq_sd_v1",
        strategy_version="1",
        mode="grid",
        workers=2,
        pairs=["EURUSD"],
        n_trials=10,
        dd_limit=4.0,
        dry_run=True,
    )

    assert run["strategy_id"] == "liq_sd_v1"
    assert run["strategy_version"] == "1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py -k strategy -v`

Expected: FAIL because optimizer runs do not require strategy identity yet.

- [ ] **Step 3: Extend optimizer run models and persistence**

```python
def start_run(
    self,
    *,
    strategy_id: str,
    strategy_version: str,
    mode: str,
    workers: int,
    pairs: list[str],
    ...
) -> dict[str, Any]:
    if not strategy_id:
        raise ValueError("strategy_id is required")
    if not strategy_version:
        raise ValueError("strategy_version is required")
    ...
```

```python
run = self._repository.create_run(
    {
        "id": run_id,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        ...
    }
)
```

- [ ] **Step 4: Require strategy selection on the optimizer API**

```python
class OptimizerRunCreateBody(BaseModel):
    strategy_id: str = Field(..., min_length=1)
    strategy_version: str = Field(..., min_length=1)
    ...
```

- [ ] **Step 5: Add list filters for strategy**

```python
@router.get("")
def list_optimizer_runs(limit: int = 20, status: str | None = None, strategy_id: str | None = None):
    ...
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py -k strategy -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/services/optimizer_run_service.py src/api_optimizer_runs.py tests/test_optimizer_run_service.py tests/test_optimizer_runs_api.py
git commit -m "DEV-115: store optimizer runs by strategy"
```

### Task 6: Remove Single-Global Activation Behavior From Strategy Management

**Files:**
- Modify: `src/api_strategies.py`
- Modify: `tests/test_strategy_registry.py`

- [ ] **Step 1: Write the failing strategy activation test**

```python
def test_activate_strategy_does_not_deactivate_other_active_rows(client, fake_supabase):
    fake_supabase.seed_strategy({"id": 1, "slug": "liq_sd_v1", "name": "Liquidity", "version": 1, "is_active": True, "config": {"name": "Liquidity"}})
    fake_supabase.seed_strategy({"id": 2, "slug": "breakout_v1", "name": "Breakout", "version": 1, "is_active": False, "config": {"name": "Breakout"}})

    response = client.patch("/api/strategies/2/activate?active=true")
    assert response.status_code == 200

    liq = fake_supabase.get_strategy(1)
    breakout = fake_supabase.get_strategy(2)
    assert liq["is_active"] is True
    assert breakout["is_active"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_strategy_registry.py -k activate -v`

Expected: FAIL because activation still deactivates all other rows.

- [ ] **Step 3: Remove the global deactivate-on-activate update**

```python
@router.patch("/{strategy_id}/activate")
def activate_strategy(strategy_id: int, active: bool = True):
    resp = (
        sb.table("strategy_configs")
        .update({"is_active": active})
        .eq("id", strategy_id)
        .execute()
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_strategy_registry.py -k activate -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api_strategies.py tests/test_strategy_registry.py
git commit -m "DEV-115: allow multiple active strategies"
```

### Task 7: Add Strategy Filters To Dashboard And Analytics APIs

**Files:**
- Modify: `src/api_dashboard.py`
- Modify: `src/api_analytics_signals_perf.py`
- Create: `tests/test_api_dashboard_strategy_filters.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_dashboard_recent_signals_can_be_filtered_by_strategy(client, fake_supabase):
    fake_supabase.seed_signal({"id": 1, "symbol": "EURUSD", "strategy_id": "liq_sd_v1", "strategy_version": "1", "status": "executed"})
    fake_supabase.seed_signal({"id": 2, "symbol": "NAS100", "strategy_id": "breakout_v1", "strategy_version": "1", "status": "executed"})

    response = client.get("/api/dashboard/summary?strategy_id=liq_sd_v1")
    assert response.status_code == 200
    assert all(row["strategy_id"] == "liq_sd_v1" for row in response.json()["recent_signals"])
```

```python
def test_analytics_perf_endpoint_filters_by_strategy_version(client, fake_supabase):
    response = client.get("/api/analytics/signals-performance?strategy_id=liq_sd_v1&strategy_version=2")
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_dashboard_strategy_filters.py -v`

Expected: FAIL because the read APIs do not accept or apply strategy filters yet.

- [ ] **Step 3: Apply strategy-aware filtering to read queries**

```python
def _apply_strategy_filters(query, strategy_id: str | None, strategy_version: str | None):
    if strategy_id:
        query = query.eq("strategy_id", strategy_id)
    if strategy_version:
        query = query.eq("strategy_version", strategy_version)
    return query
```

- [ ] **Step 4: Include strategy identity in response models**

```python
{
    "id": row["id"],
    "symbol": row["symbol"],
    "status": row["status"],
    "strategy_id": row.get("strategy_id"),
    "strategy_version": row.get("strategy_version"),
    "strategy_name": row.get("strategy_name"),
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_dashboard_strategy_filters.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api_dashboard.py src/api_analytics_signals_perf.py tests/test_api_dashboard_strategy_filters.py
git commit -m "DEV-115: add strategy filters to dashboard analytics"
```

### Task 8: Make Frontend Pages And Tables Strategy-Aware

**Files:**
- Modify: `frontend/src/types/trading.ts`
- Create: `frontend/src/components/strategy/StrategyFilter.tsx`
- Modify: `frontend/src/components/dashboard/RecentSignalsPanel.tsx`
- Modify: `frontend/src/components/dashboard/SignalTable.tsx`
- Modify: `frontend/src/app/analytics/page.tsx`
- Modify: `frontend/src/app/notifications/page.tsx`
- Modify: `frontend/src/app/optimizer/page.tsx`
- Modify: `frontend/src/components/notifications/RoutingPanel.tsx`
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx`
- Modify: `frontend/src/components/dashboard/RecentSignalsPanel.test.tsx`
- Modify: `frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
it('shows strategy badges in recent signals', () => {
  render(<RecentSignalsPanel signals={[{ id: '1', symbol: 'EURUSD', side: 'buy', status: 'executed', strategy_id: 'liq_sd_v1', strategy_version: '1' } as TradingSignal]} />)
  expect(screen.getByText('liq_sd_v1@1')).toBeInTheDocument()
})
```

```tsx
it('requires strategy selection before starting optimizer run', async () => {
  render(<OptimizerRunsWorkspace />)
  expect(screen.getByRole('button', { name: /start optimizer/i })).toBeDisabled()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/dashboard/RecentSignalsPanel.test.tsx src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

Expected: FAIL because strategy fields and UI gating do not exist yet.

- [ ] **Step 3: Extend signal and optimizer types**

```ts
export interface TradingSignal {
  ...
  strategy_id?: string | null;
  strategy_version?: string | null;
  strategy_name?: string | null;
}
```

- [ ] **Step 4: Add a reusable strategy filter**

```tsx
export function StrategyFilter({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">All strategies</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}
```

- [ ] **Step 5: Render strategy identity on dashboard, notifications, and optimizer pages**

```tsx
const strategyBadge = signal.strategy_id
  ? `${signal.strategy_id}@${signal.strategy_version ?? "?"}`
  : "legacy"
```

```tsx
<StrategyFilter value={strategyId} onChange={setStrategyId} options={strategyOptions} />
```

```tsx
const canStartRun = Boolean(selectedStrategyId && selectedStrategyVersion && selectedPairs.length > 0)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/dashboard/RecentSignalsPanel.test.tsx src/components/optimizer/OptimizerRunsWorkspace.test.tsx`

Expected: PASS

- [ ] **Step 7: Build the frontend**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/types/trading.ts frontend/src/components/strategy/StrategyFilter.tsx frontend/src/components/dashboard/RecentSignalsPanel.tsx frontend/src/components/dashboard/SignalTable.tsx frontend/src/app/analytics/page.tsx frontend/src/app/notifications/page.tsx frontend/src/app/optimizer/page.tsx frontend/src/components/notifications/RoutingPanel.tsx frontend/src/components/optimizer/OptimizerRunsWorkspace.tsx frontend/src/components/dashboard/RecentSignalsPanel.test.tsx frontend/src/components/optimizer/OptimizerRunsWorkspace.test.tsx
git commit -m "DEV-115: add strategy-aware frontend views"
```

### Task 9: End-To-End Verification And Safe Rollout

**Files:**
- Modify: `docs/superpowers/specs/2026-04-16-multi-strategy-bot-design.md` (only if needed)

- [ ] **Step 1: Run backend verification**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest \
  tests/test_strategy_registry.py \
  tests/test_signal_transport.py \
  tests/test_optimizer_run_service.py \
  tests/test_optimizer_runs_api.py \
  tests/test_notification_service.py \
  tests/test_api_dashboard_strategy_filters.py -v
```

Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run:

```bash
cd frontend && npx vitest run src/components/dashboard/RecentSignalsPanel.test.tsx src/components/optimizer/OptimizerRunsWorkspace.test.tsx
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Run migration and app smoke test locally**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. python3 -m src.worker
```

Expected: worker boots without import or model errors.

- [ ] **Step 4: Smoke test the webhook with trial payloads**

```bash
curl -s -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id":"liq_sd_v1",
    "strategy_version":"1",
    "symbol":"EURUSD",
    "side":"buy",
    "entry":1.1000,
    "sl":1.0950,
    "tp":1.1100,
    "size":1.0
  }'
```

Expected: accepted response, saved signal row contains strategy fields, and the notification title includes `liq_sd_v1@1`.

- [ ] **Step 5: Smoke test rejection behavior**

```bash
curl -s -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id":"unknown_strategy",
    "strategy_version":"1",
    "symbol":"EURUSD",
    "side":"buy",
    "entry":1.1000,
    "sl":1.0950,
    "tp":1.1100,
    "size":1.0
  }'
```

Expected: 400/422 style rejection with an explicit strategy error, not fallback execution.

- [ ] **Step 6: Roll out safely**

1. Keep only `liq_sd_v1` live at first.
2. Create the second strategy as active but route it to paper/shadow only.
3. Verify dashboard/analytics filters separate the two strategies cleanly.
4. Only after the second strategy proves itself in paper/shadow should it route to any live account.

- [ ] **Step 7: Final commit**

```bash
git add docs/superpowers/specs/2026-04-16-multi-strategy-bot-design.md
git commit -m "DEV-115: finalize multi-strategy rollout notes"
```

---

## Notes For Implementation

- Treat `strategy_configs.slug` as the single source of truth for `strategy_id` in v1. Do not add a second identifier column unless the existing slug model proves insufficient.
- Compare alert `strategy_version` to `strategy_configs.version` using `str(version)` so existing integer rows stay compatible.
- Do not fall back to `get_active_strategy()` anywhere in the live signal path after Task 3.
- Keep account-level kill switches and drawdown protections unchanged; strategy-specific logic is additive, not a replacement.
- New strategies should start paper/shadow only even after the multi-strategy code lands.
