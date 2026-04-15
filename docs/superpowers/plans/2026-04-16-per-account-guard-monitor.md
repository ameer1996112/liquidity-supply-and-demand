# Per-Account Guard Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a truthful multi-account guard monitor that shows a combined fleet summary plus separate per-account guard cards, while verifying the live guard path remains account-scoped.

**Architecture:** Extend the existing risk-monitor backend to build one account universe, compute account-scoped monitor rows, and derive the combined summary from those rows. Update the frontend guard page to consume the new shape and render a summary section plus account cards instead of relying on single-account style metrics.

**Tech Stack:** FastAPI, Supabase-backed reads, Python pytest, Next.js/React, Vitest

---

## File Structure

- Modify: `src/api_risk_monitor.py`
  - Add account-list helpers, per-account metric builders, summary aggregation, and the new response shape.
- Modify: `src/api_risk.py`
  - Reuse or align any shared multi-account balance/risk helpers if needed so the operator-facing APIs stay consistent.
- Modify: `src/pipeline/account_guards.py`
  - Verify and patch any remaining shared-state edge cases found during enforcement review.
- Modify: `frontend/src/components/risk/` guard/risk monitor components
  - Replace the single shared drawdown-style view with a combined summary plus per-account cards.
- Modify or create: `frontend/src/types/risk.ts`
  - Add types for summary and per-account monitor cards.
- Create or modify: `tests/test_api_risk_monitor.py`
  - Cover multi-account monitor response, account-specific drawdown, and partial failure behavior.
- Create or modify: `frontend/src/components/risk/__tests__/...`
  - Cover summary + account card rendering and regression against single-account fallback behavior.

### Task 1: Add failing backend tests for per-account monitor aggregation

**Files:**
- Create: `tests/test_api_risk_monitor.py`
- Modify: `src/api_risk_monitor.py`

- [ ] **Step 1: Write the failing tests for per-account monitor response**

```python
from fastapi.testclient import TestClient

from src.api import app


def test_risk_monitor_returns_summary_and_account_cards(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_two_accounts())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", lambda: _fake_settings())

    response = client.get("/api/risk/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "accounts" in payload
    assert len(payload["accounts"]) == 2
    assert payload["summary"]["total_accounts"] == 2


def test_risk_monitor_uses_account_specific_balances_for_drawdown(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_drawdown_split())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", lambda: _fake_settings())

    response = client.get("/api/risk/monitor")

    assert response.status_code == 200
    accounts = response.json()["accounts"]
    drawdowns = {row["account_name"]: row["current_drawdown_pct"] for row in accounts}
    assert drawdowns["Eval A"] != drawdowns["Eval B"]


def test_risk_monitor_summary_is_derived_from_account_rows(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_two_accounts())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", lambda: _fake_settings())

    response = client.get("/api/risk/monitor")

    payload = response.json()
    account_total = sum(row["daily_pnl_usd"] for row in payload["accounts"])
    assert payload["summary"]["total_daily_pnl_usd"] == account_total
```

- [ ] **Step 2: Run backend monitor tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py -v`
Expected: FAIL because `/api/risk/monitor` does not yet return `summary` and `accounts`.

- [ ] **Step 3: Add local fake helpers inside the test file**

```python
class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str, rows_by_table: dict[str, list[dict]]):
        self.table_name = table_name
        self.rows = list(rows_by_table.get(table_name, []))

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def in_(self, key, values):
        self.rows = [row for row in self.rows if row.get(key) in values]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def execute(self):
        return _FakeResponse(self.rows)


class _FakeSupabase:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self.rows_by_table = rows_by_table

    def table(self, table_name: str):
        return _FakeQuery(table_name, self.rows_by_table)
```

- [ ] **Step 4: Run backend monitor tests again to keep the failure targeted**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py -v`
Expected: FAIL with assertion mismatch on response shape, not fixture errors.

- [ ] **Step 5: Commit the failing test scaffold**

```bash
git add tests/test_api_risk_monitor.py
git commit -m "DEV-107: add per-account risk monitor tests"
```

### Task 2: Implement backend per-account monitor response

**Files:**
- Modify: `src/api_risk_monitor.py`
- Test: `tests/test_api_risk_monitor.py`

- [ ] **Step 1: Add response models for summary and per-account cards**

```python
class AccountGuardCard(BaseModel):
    account_name: str
    broker_profile_id: Optional[int] = None
    account_type: str
    evaluation_phase: Optional[str] = None
    prop_firm_name: Optional[str] = None
    run_mode: str
    connection_status: Optional[str] = None
    starting_balance_usd: float
    current_equity_usd: float
    daily_pnl_usd: float
    daily_pnl_pct: float
    peak_equity_usd: float
    current_drawdown_pct: float
    max_drawdown_allowed_pct: float
    drawdown_utilization_pct: float
    daily_loss_used_usd: float
    daily_loss_limit_usd: float
    open_positions: int
    max_positions: int
    trades_today: int
    max_trades_today: int
    risk_multiplier: float
    risk_label: str
    effective_risk_pct: float
    base_risk_pct: float
    kill_switch_active: bool
    blocked: bool
    warning_message: Optional[str] = None
    blocked_reason: Optional[str] = None
    guard_rails: list[GuardRailStatus]


class RiskMonitorSummary(BaseModel):
    total_accounts: int
    active_accounts: int
    total_equity_usd: float
    total_starting_balance_usd: float
    total_daily_pnl_usd: float
    total_open_positions: int
    accounts_in_warning: int
    accounts_blocked: int
    global_kill_switch_active: bool
```

- [ ] **Step 2: Add a helper that builds the active account universe**

```python
def _load_active_account_rows(supabase) -> list[dict]:
    strategy_rows = (
        supabase.table("account_strategies")
        .select("account_name,broker_profile_id")
        .eq("is_active", True)
        .execute()
    ).data or []

    profile_rows = (
        supabase.table("broker_profiles")
        .select(
            "id,name,selected_for_trading,is_active,starting_balance,"
            "evaluation_mode,evaluation_phase,prop_firm_name,run_mode,connection_status"
        )
        .eq("is_active", True)
        .eq("selected_for_trading", True)
        .execute()
    ).data or []

    by_name: dict[str, dict] = {}
    for row in profile_rows:
        name = row.get("name")
        if not name:
            continue
        by_name[name] = row
    for strategy in strategy_rows:
        acct_name = strategy.get("account_name")
        if not acct_name:
            continue
        by_name.setdefault(acct_name, {"name": acct_name, "id": strategy.get("broker_profile_id")})
    return list(by_name.values())
```

- [ ] **Step 3: Add a helper that computes one account card from account-scoped queries**

```python
def _build_account_guard_card(supabase, settings, profile: dict) -> AccountGuardCard:
    account_name = profile.get("name") or profile.get("account_name") or "Unknown"
    profile_id = profile.get("id")
    starting_balance = float(profile.get("starting_balance") or settings.account_balance)
    daily_pnl = _get_daily_pnl_for_account(supabase, account_name, profile_id)
    current_equity = _get_equity_for_account(supabase, account_name, starting_balance) + daily_pnl
    open_positions = _get_open_positions_for_account(supabase, account_name, profile_id)
    trades_today = _get_trades_today_for_account(supabase, account_name, profile_id)
    drawdown_pct, peak_equity = _calculate_drawdown(current_equity, starting_balance)
    allowed, risk_multiplier, risk_label = check_safety(current_equity, starting_balance, daily_pnl, account_name=account_name)

    return AccountGuardCard(
        account_name=account_name,
        broker_profile_id=profile_id,
        account_type="evaluation" if profile.get("evaluation_mode") else "funded",
        evaluation_phase=profile.get("evaluation_phase"),
        prop_firm_name=profile.get("prop_firm_name"),
        run_mode=str(profile.get("run_mode") or settings.run_mode),
        connection_status=profile.get("connection_status"),
        starting_balance_usd=starting_balance,
        current_equity_usd=current_equity,
        daily_pnl_usd=daily_pnl,
        daily_pnl_pct=round((daily_pnl / starting_balance * 100.0), 2) if starting_balance else 0.0,
        peak_equity_usd=peak_equity,
        current_drawdown_pct=abs(drawdown_pct),
        max_drawdown_allowed_pct=settings.trinity_max_drawdown_pct,
        drawdown_utilization_pct=round(abs(drawdown_pct / settings.trinity_max_drawdown_pct * 100.0), 2) if settings.trinity_max_drawdown_pct else 0.0,
        daily_loss_used_usd=abs(min(0.0, daily_pnl)),
        daily_loss_limit_usd=starting_balance * 0.02,
        open_positions=open_positions,
        max_positions=settings.trinity_max_positions,
        trades_today=trades_today,
        max_trades_today=2,
        risk_multiplier=risk_multiplier,
        risk_label=risk_label,
        effective_risk_pct=round(settings.risk_percent * risk_multiplier, 2),
        base_risk_pct=settings.risk_percent,
        kill_switch_active=_is_account_kill_switch_on(account_name, settings),
        blocked=not allowed,
        warning_message=None if allowed else risk_label,
        blocked_reason=None if allowed else risk_label,
        guard_rails=[],
    )
```

- [ ] **Step 4: Add account-scoped query helpers and keep them small**

```python
def _get_daily_pnl_for_account(supabase, account_name: str, profile_id: Optional[int]) -> float:
    query = supabase.table("trading_signals").select("pnl_usd").in_("status", ["CLOSED", "closed"]).gte("created_at", _today_start_iso())
    if profile_id is not None:
        query = query.eq("broker_profile_id", profile_id)
    else:
        query = query.eq("account_name", account_name)
    rows = query.execute().data or []
    return sum(float(row.get("pnl_usd") or 0.0) for row in rows)
```

- [ ] **Step 5: Change `/api/risk/monitor` to return the new shape**

```python
@router.get("/monitor", response_model=RiskMonitorResponse)
async def get_risk_monitor():
    settings = get_settings()
    supabase = get_supabase()
    profiles = _load_active_account_rows(supabase)
    account_cards = [_build_account_guard_card(supabase, settings, profile) for profile in profiles]
    summary = _build_summary(account_cards, settings)
    return RiskMonitorResponse(
        summary=summary,
        accounts=account_cards,
        symbol_overrides=_get_symbol_overrides(supabase),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 6: Run backend monitor tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py -v`
Expected: PASS

- [ ] **Step 7: Commit backend monitor implementation**

```bash
git add src/api_risk_monitor.py tests/test_api_risk_monitor.py
git commit -m "DEV-107: add per-account risk monitor response"
```

### Task 3: Verify and harden per-account guard enforcement

**Files:**
- Modify: `src/pipeline/account_guards.py`
- Test: `tests/test_api_risk_monitor.py`

- [ ] **Step 1: Write a regression test that proves one account’s defensive state does not leak**

```python
def test_defensive_state_does_not_leak_between_accounts(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_leaking_accounts())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", lambda: _fake_settings())

    response = client.get("/api/risk/monitor")
    cards = {row["account_name"]: row for row in response.json()["accounts"]}

    assert cards["Eval A"]["risk_multiplier"] != cards["Eval B"]["risk_multiplier"]
    assert cards["Eval A"]["blocked"] is not cards["Eval B"]["blocked"]
```

- [ ] **Step 2: Run the regression test and verify current behavior**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py::test_defensive_state_does_not_leak_between_accounts -v`
Expected: PASS if monitor uses account-scoped calculations, otherwise FAIL and expose the leak.

- [ ] **Step 3: Patch any shared-state guard lookup that still ignores profile scope**

```python
allowed, risk_multiplier, risk_label = check_safety(
    current_equity,
    acct_balance,
    daily_pnl,
    account_name=account_name,
    risk_pct_override=profile_risk_pct,
)
payload[f"_risk_multiplier_{account_name}"] = risk_multiplier
```

- [ ] **Step 4: Run the full backend guard-monitor suite**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py tests/test_risk_engine.py tests/test_pass_eval_risk.py -v`
Expected: PASS

- [ ] **Step 5: Commit guard verification/hardening**

```bash
git add src/pipeline/account_guards.py tests/test_api_risk_monitor.py
git commit -m "DEV-107: verify per-account guard isolation"
```

### Task 4: Update frontend types and guard page rendering

**Files:**
- Modify: `frontend/src/types/risk.ts`
- Modify: `frontend/src/components/risk/*`
- Test: `frontend/src/components/risk/__tests__/...`

- [ ] **Step 1: Write the failing frontend rendering tests**

```tsx
import { render, screen } from "@testing-library/react";

import { GuardMonitorPanel } from "../GuardMonitorPanel";


test("renders combined summary and per-account cards", async () => {
  render(<GuardMonitorPanel initialData={mockPerAccountMonitor} />);

  expect(screen.getByText(/total accounts/i)).toBeInTheDocument();
  expect(screen.getByText("Eval A")).toBeInTheDocument();
  expect(screen.getByText("Eval B")).toBeInTheDocument();
});


test("does not render a single shared drawdown block", async () => {
  render(<GuardMonitorPanel initialData={mockPerAccountMonitor} />);

  expect(screen.queryByText(/^Current DD$/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/risk/__tests__/GuardMonitorPanel.test.tsx`
Expected: FAIL because the component still expects the old single-account shape.

- [ ] **Step 3: Add the new shared types**

```ts
export type RiskMonitorSummary = {
  total_accounts: number;
  active_accounts: number;
  total_equity_usd: number;
  total_starting_balance_usd: number;
  total_daily_pnl_usd: number;
  total_open_positions: number;
  accounts_in_warning: number;
  accounts_blocked: number;
  global_kill_switch_active: boolean;
};

export type AccountGuardCard = {
  account_name: string;
  account_type: string;
  evaluation_phase?: string | null;
  run_mode: string;
  connection_status?: string | null;
  starting_balance_usd: number;
  current_equity_usd: number;
  daily_pnl_usd: number;
  current_drawdown_pct: number;
  risk_multiplier: number;
  risk_label: string;
  blocked: boolean;
  warning_message?: string | null;
  guard_rails: GuardRailStatus[];
};
```

- [ ] **Step 4: Implement the combined summary row and per-account cards**

```tsx
return (
  <div className="space-y-4">
    <SummaryStrip summary={data.summary} />
    <div className="grid gap-4 xl:grid-cols-2">
      {data.accounts.map((account) => (
        <AccountGuardCardView key={account.account_name} account={account} />
      ))}
    </div>
  </div>
);
```

- [ ] **Step 5: Run frontend tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/risk/__tests__/GuardMonitorPanel.test.tsx`
Expected: PASS

- [ ] **Step 6: Build the frontend to catch typing/layout regressions**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 7: Commit frontend monitor update**

```bash
git add frontend/src/types/risk.ts frontend/src/components/risk
git commit -m "DEV-107: render per-account guard monitor cards"
```

### Task 5: Final verification and cleanup

**Files:**
- Modify: `src/api_risk.py` if alignment is needed
- Verify: `src/api_risk_monitor.py`, `src/pipeline/account_guards.py`, frontend risk monitor files

- [ ] **Step 1: Align any remaining shared risk status endpoint naming or fields**

```python
# Keep field naming aligned where practical so operator pages
# do not need special-case adapters between risk endpoints.
```

- [ ] **Step 2: Run the backend verification suite**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py tests/test_risk_engine.py tests/test_pass_eval_risk.py tests/test_api_rules.py -v`
Expected: PASS

- [ ] **Step 3: Run the frontend verification suite**

Run: `cd frontend && npx vitest run src/components/risk/__tests__/GuardMonitorPanel.test.tsx src/components/rules/__tests__/RiskRulesPanel.test.tsx`
Expected: PASS

- [ ] **Step 4: Run production build verification**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit final verification/alignment changes**

```bash
git add src/api_risk.py src/api_risk_monitor.py src/pipeline/account_guards.py tests frontend
git commit -m "DEV-107: finalize per-account guard monitor"
```
