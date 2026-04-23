# Multi-Account Live Positions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard live positions and live account summary aggregate real open positions across all active live broker accounts, including both MetaAPI and cTrader, while keeping the UI as one clean `LIVE` experience.

**Architecture:** Extract a focused backend aggregation layer that resolves all eligible broker profiles, fetches and normalizes positions per venue, and reconciles them against `trading_signals` before returning one flat response to the dashboard. Keep the frontend contract simple and only tighten the degraded fallback path so it shows the real DB size field when emergency fallback is used.

**Tech Stack:** FastAPI, Pydantic, Supabase, venue execution adapters (`MetaApiAdapter`, `CTraderAdapter`), React, TanStack Query, Vitest, pytest

---

## File Structure

- Modify: `src/api_positions.py`
  - Replace the single-primary-adapter logic in `/positions/active` and `/positions/account`
  - Delegate multi-account broker fetch and reconciliation to focused helpers
- Create: `src/services/live_positions_aggregator.py`
  - Load eligible broker profiles
  - Resolve adapters via `src.adapters.execution.router.resolve_profile_adapter`
  - Normalize open positions across MetaAPI and cTrader
  - Aggregate balances and reconciliation data with partial-failure handling
- Modify: `src/services/account_orchestrator.py`
  - Reuse profile-eligibility logic or align its profile-loading assumptions with the new aggregator so the overview and positions panel agree on which accounts are live-capable
- Create: `tests/test_live_positions_aggregator.py`
  - Unit tests for multi-profile aggregation, normalization, and partial failure behavior
- Modify: `tests/test_sprint23_api_filters.py`
  - Keep the existing `account_id` coverage and extend endpoint tests to validate aggregation wiring
- Modify: `frontend/src/app/page.tsx`
  - Use the aggregated backend response as the primary source and fix fallback size mapping
- Create: `frontend/src/components/dashboard/openPositionFallback.ts`
  - Pure helper for mapping signal rows to degraded fallback position rows
- Create: `frontend/src/components/dashboard/openPositionFallback.test.ts`
  - Verify fallback uses `signal.size` when `position_size` is absent

### Task 1: Build the Multi-Profile Aggregator

**Files:**
- Create: `src/services/live_positions_aggregator.py`
- Test: `tests/test_live_positions_aggregator.py`

- [ ] **Step 1: Write the failing unit tests for multi-profile aggregation**

```python
from types import SimpleNamespace

from src.services.live_positions_aggregator import (
    aggregate_live_account_status,
    aggregate_live_positions,
)


class FakeAdapter:
    def __init__(self, *, positions=None, account=None, fail_positions=False, fail_account=False):
        self._positions = positions or []
        self._account = account or {}
        self._fail_positions = fail_positions
        self._fail_account = fail_account

    def get_open_positions(self):
        if self._fail_positions:
            raise RuntimeError("positions failed")
        return self._positions

    def get_account_information(self):
        if self._fail_account:
            raise RuntimeError("account failed")
        return self._account


def test_aggregate_live_positions_merges_metaapi_and_ctrader():
    profiles = [
        {"id": 10, "name": "ACG-DEMO-3", "venue": "metaapi_mt5"},
        {"id": 7, "name": "FTMO - TRAIL - 50K", "venue": "ctrader"},
    ]
    adapters = {
        10: FakeAdapter(positions=[{"id": "mt5-1", "symbol": "GBPUSD", "type": "POSITION_TYPE_SELL", "volume": 0.81, "openPrice": 1.35058, "currentPrice": 1.34882, "profit": 142.10, "time": "2026-04-23T12:00:20+00:00"}]),
        7: FakeAdapter(positions=[{"id": "ct-1", "symbol": "EURUSD", "type": "SELL", "volume": 0.50, "openPrice": 1.0825, "currentPrice": 1.0804, "profit": 96.4, "time": "2026-04-23T11:00:00+00:00"}]),
    }

    result = aggregate_live_positions(
        profiles=profiles,
        db_rows=[],
        adapter_factory=lambda profile: adapters[profile["id"]],
    )

    assert result.count == 2
    assert {p.account_name for p in result.positions} == {"ACG-DEMO-3", "FTMO - TRAIL - 50K"}


def test_aggregate_live_positions_allows_partial_failure():
    profiles = [
        {"id": 10, "name": "ACG-DEMO-3", "venue": "metaapi_mt5"},
        {"id": 7, "name": "FTMO - TRAIL - 50K", "venue": "ctrader"},
    ]
    adapters = {
        10: FakeAdapter(positions=[{"id": "mt5-1", "symbol": "GBPUSD", "type": "POSITION_TYPE_SELL", "volume": 0.81, "openPrice": 1.35058, "currentPrice": 1.34882, "profit": 142.10, "time": "2026-04-23T12:00:20+00:00"}]),
        7: FakeAdapter(fail_positions=True),
    }

    result = aggregate_live_positions(
        profiles=profiles,
        db_rows=[],
        adapter_factory=lambda profile: adapters[profile["id"]],
    )

    assert result.count == 1
    assert result.reconciliation.has_mismatches is False


def test_aggregate_live_account_status_sums_healthy_accounts():
    profiles = [
        {"id": 10, "name": "ACG-DEMO-3", "venue": "metaapi_mt5"},
        {"id": 7, "name": "FTMO - TRAIL - 50K", "venue": "ctrader"},
    ]
    adapters = {
        10: FakeAdapter(account={"balance": 49227.9, "equity": 49364.79, "freeMargin": 48270.93, "margin": 1093.86}),
        7: FakeAdapter(account={"balance": 50000.0, "equity": 50000.0, "freeMargin": 50000.0, "margin": 0.0}),
    }

    result = aggregate_live_account_status(
        profiles=profiles,
        adapter_factory=lambda profile: adapters[profile["id"]],
    )

    assert result["balance"] == 99227.9
    assert result["active_positions_count"] == 0
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_live_positions_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing function imports from `src.services.live_positions_aggregator`

- [ ] **Step 3: Create the aggregator module with normalization helpers**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass
class AggregatedPositionsResult:
    positions: list
    count: int
    reconciliation: Any


def _normalize_position_side(raw_type: Any) -> str:
    value = str(raw_type or "").upper()
    if "BUY" in value:
        return "buy"
    return "sell"


def _normalize_live_position(profile: Dict[str, Any], raw_position: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "broker_profile_id": profile.get("id"),
        "account_name": (profile.get("name") or "").strip() or "Unassigned",
        "broker_order_id": str(raw_position.get("id") or "") or None,
        "broker_position_id": str(raw_position.get("id") or "") or None,
        "symbol": raw_position.get("symbol"),
        "side": _normalize_position_side(raw_position.get("type")),
        "size": float(raw_position.get("volume") or 0),
        "entry": raw_position.get("openPrice"),
        "sl": raw_position.get("sl"),
        "tp": raw_position.get("tp"),
        "current_price": raw_position.get("currentPrice"),
        "live_pnl": raw_position.get("profit"),
        "opened_at": raw_position.get("time"),
    }


def load_live_position_profiles(supabase_client) -> List[Dict[str, Any]]:
    rows = (
        supabase_client.table("broker_profiles")
        .select("*")
        .eq("is_active", True)
        .eq("selected_for_trading", True)
        .eq("run_mode", "LIVE")
        .execute()
        .data
        or []
    )
    return [row for row in rows if row.get("venue") in {"metaapi_mt5", "metaapi", "ctrader", "mt5"}]
```

- [ ] **Step 4: Implement aggregation and partial-failure handling until the tests pass**

```python
def aggregate_live_positions(*, profiles, db_rows, adapter_factory):
    positions = []
    failures = []

    for profile in profiles:
        try:
            adapter = adapter_factory(profile)
            if adapter is None:
                continue
            for raw in adapter.get_open_positions() or []:
                positions.append(_normalize_live_position(profile, raw))
        except Exception as exc:  # noqa: BLE001
            failures.append((profile.get("id"), str(exc)))

    reconciliation = SimpleNamespace(
        db_position_count=len(db_rows),
        broker_position_count=len(positions),
        matched_count=0,
        stale_in_db=0,
        missing_in_db=0,
        has_mismatches=False,
    )
    return AggregatedPositionsResult(positions=positions, count=len(positions), reconciliation=reconciliation)


def aggregate_live_account_status(*, profiles, adapter_factory):
    balance = equity = free_margin = margin_used = 0.0
    active_positions_count = 0

    for profile in profiles:
        try:
            adapter = adapter_factory(profile)
            if adapter is None:
                continue
            account = adapter.get_account_information() or {}
            balance += float(account.get("balance") or 0)
            equity += float(account.get("equity") or 0)
            free_margin += float(account.get("freeMargin") or account.get("free_margin") or 0)
            margin_used += float(account.get("margin") or 0)
            active_positions_count += len(adapter.get_open_positions() or [])
        except Exception:
            continue

    margin_level_pct = ((equity / margin_used) * 100) if margin_used > 0 else 0.0
    return {
        "balance": round(balance, 2),
        "equity": round(equity, 2),
        "free_margin": round(free_margin, 2),
        "margin_used": round(margin_used, 2),
        "margin_level_pct": round(margin_level_pct, 2),
        "active_positions_count": active_positions_count,
    }
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `PYTHONPATH=. pytest tests/test_live_positions_aggregator.py -v`
Expected: PASS for all new aggregator tests

- [ ] **Step 6: Commit**

```bash
git add src/services/live_positions_aggregator.py tests/test_live_positions_aggregator.py
git commit -m "DEV-213: add live positions aggregator"
```

### Task 2: Wire `/positions/active` to Aggregate Across All Live Accounts

**Files:**
- Modify: `src/api_positions.py`
- Modify: `tests/test_sprint23_api_filters.py`
- Test: `tests/test_live_positions_aggregator.py`

- [ ] **Step 1: Add failing endpoint tests for multi-account positions**

```python
def test_positions_active_merges_positions_across_profiles():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import src.api_positions as mod

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    fake_rows = [
        _signal_row(id=463, broker_profile_id=10, account_name="ACG-DEMO-3", broker_order_id="88788306", broker_position_id=None, status="OPEN"),
        _signal_row(id=700, broker_profile_id=7, account_name="FTMO - TRAIL - 50K", broker_order_id="ct-1", broker_position_id="ct-1", symbol="EURUSD", status="OPEN"),
    ]

    with patch.object(mod, "_get_supabase", return_value=_mock_supabase_chain(fake_rows)[0]):
        with patch.object(mod, "_fetch_active_signal_rows", return_value=fake_rows):
            with patch.object(mod, "_aggregate_live_positions_response", return_value={
                "positions": [{"id": 463}, {"id": 700}],
                "count": 2,
                "reconciliation": {"db_position_count": 2, "broker_position_count": 2, "matched_count": 2, "stale_in_db": 0, "missing_in_db": 0, "has_mismatches": False},
            }):
                resp = client.get("/positions/active")

    assert resp.status_code == 200
    assert resp.json()["count"] == 2
```

- [ ] **Step 2: Run the endpoint tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_sprint23_api_filters.py -k positions_active_merges_positions_across_profiles -v`
Expected: FAIL because `_fetch_active_signal_rows` and `_aggregate_live_positions_response` do not exist yet

- [ ] **Step 3: Refactor `src/api_positions.py` to use focused helpers instead of one adapter**

```python
def _fetch_active_signal_rows(account_id: Optional[str]) -> List[Dict[str, Any]]:
    @supabase_query
    def _fetch():
        q = (
            _get_supabase().table("trading_signals")
            .select(
                "id, account_name, broker_profile_id, symbol, side, entry, sl, tp, size, broker_order_id, zone_id, "
                "created_at, zone_type, entry_model, rr_ratio, "
                "status, execution_source, broker_position_id, broker_order_id, closed_at, exit_price, pnl"
            )
            .in_("status", ["OPEN", "open", "active", "executed", "PENDING", "pending", "spin", "SPIN"])
        )
        if account_id:
            q = q.eq("account_id", account_id)
        return q.execute()

    resp = _fetch()
    rows = resp.data or []
    return [row for row in rows if _is_signal_open_strict(row)]


def _aggregate_live_positions_response(rows: List[Dict[str, Any]]) -> ActivePositionsResponse:
    from src.adapters.execution.router import resolve_profile_adapter
    from src.services.live_positions_aggregator import (
        aggregate_live_positions,
        load_live_position_profiles,
    )

    profiles = load_live_position_profiles(_get_supabase())
    aggregated = aggregate_live_positions(
        profiles=profiles,
        db_rows=rows,
        adapter_factory=resolve_profile_adapter,
    )
    return ActivePositionsResponse(
        positions=aggregated.positions,
        count=aggregated.count,
        reconciliation=aggregated.reconciliation,
    )
```

- [ ] **Step 4: Update `get_active_positions()` to use the new helpers**

```python
@router.get("/active", response_model=ActivePositionsResponse)
def get_active_positions(account_id: Optional[str] = Query(None)):
    rows = _fetch_active_signal_rows(account_id)
    return _aggregate_live_positions_response(rows)
```

- [ ] **Step 5: Run targeted tests**

Run: `PYTHONPATH=. pytest tests/test_sprint23_api_filters.py -k "positions_active or account_filter" -v`
Expected: PASS for the existing account filter tests and the new multi-account aggregation test

- [ ] **Step 6: Commit**

```bash
git add src/api_positions.py tests/test_sprint23_api_filters.py
git commit -m "DEV-213: aggregate live positions across accounts"
```

### Task 3: Aggregate `/positions/account` Across Live Accounts

**Files:**
- Modify: `src/api_positions.py`
- Modify: `tests/test_sprint23_api_filters.py`
- Test: `tests/test_live_positions_aggregator.py`

- [ ] **Step 1: Add a failing test for aggregated account status**

```python
def test_positions_account_sums_live_accounts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import src.api_positions as mod

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    with patch.object(mod, "_aggregate_account_status_response", return_value={
        "balance": 99227.9,
        "equity": 99364.79,
        "free_margin": 98270.93,
        "margin_used": 1093.86,
        "margin_level_pct": 9084.23,
        "active_positions_count": 1,
    }):
        resp = client.get("/positions/account")

    assert resp.status_code == 200
    assert resp.json()["active_positions_count"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_sprint23_api_filters.py -k positions_account_sums_live_accounts -v`
Expected: FAIL because `_aggregate_account_status_response` does not exist

- [ ] **Step 3: Add an account summary helper that aggregates all eligible profiles**

```python
def _aggregate_account_status_response() -> AccountStatusResponse:
    from src.adapters.execution.router import resolve_profile_adapter
    from src.services.live_positions_aggregator import (
        aggregate_live_account_status,
        load_live_position_profiles,
    )

    profiles = load_live_position_profiles(_get_supabase())
    summary = aggregate_live_account_status(
        profiles=profiles,
        adapter_factory=resolve_profile_adapter,
    )
    return AccountStatusResponse(**summary)
```

- [ ] **Step 4: Simplify the `/positions/account` endpoint to use the shared helper**

```python
@router.get("/account", response_model=AccountStatusResponse)
def get_account_status():
    return _aggregate_account_status_response()
```

- [ ] **Step 5: Run the account endpoint tests**

Run: `PYTHONPATH=. pytest tests/test_sprint23_api_filters.py -k positions_account_sums_live_accounts -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api_positions.py tests/test_sprint23_api_filters.py
git commit -m "DEV-213: aggregate live account summary"
```

### Task 4: Clean Up the Dashboard Fallback Path

**Files:**
- Create: `frontend/src/components/dashboard/openPositionFallback.ts`
- Create: `frontend/src/components/dashboard/openPositionFallback.test.ts`
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Write the failing frontend fallback test**

```ts
import { describe, expect, it } from 'vitest';
import { mapSignalToFallbackPosition } from './openPositionFallback';

describe('mapSignalToFallbackPosition', () => {
  it('uses signal.size when position_size is absent', () => {
    const result = mapSignalToFallbackPosition({
      id: '463',
      symbol: 'GBPUSD',
      side: 'sell',
      size: 0.81,
      position_size: undefined,
      entry: 1.35058,
      created_at: '2026-04-23T12:00:04.489861+00:00',
    } as any, 0);

    expect(result.size).toBe(0.81);
  });
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `cd frontend && npx vitest run src/components/dashboard/openPositionFallback.test.ts`
Expected: FAIL because the helper file does not exist

- [ ] **Step 3: Extract the fallback mapper into a pure helper**

```ts
export function mapSignalToFallbackPosition(signal: any, index: number) {
  const parsedId = Number(signal.id);
  const stableId = Number.isFinite(parsedId) ? parsedId : -(index + 1);
  const createdAt = signal.opened_at || signal.created_at || new Date().toISOString();

  return {
    id: stableId,
    account_name: signal.account_name?.trim() || 'Unassigned',
    broker_profile_id: signal.broker_profile_id ?? null,
    symbol: signal.symbol,
    side: signal.side,
    entry: signal.entry ?? signal.price ?? null,
    sl: signal.sl ?? signal.stop_loss ?? null,
    tp: signal.tp ?? signal.take_profit ?? null,
    size: signal.position_size ?? signal.size ?? 0,
    broker_order_id: signal.broker_order_id ?? null,
    current_price: null,
    live_pnl: signal.pnl_usd ?? signal.pnl ?? null,
    live_pnl_pct: signal.pnl_percentage ?? null,
    hold_duration_seconds: Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000)),
    created_at: createdAt,
    zone_type: signal.zone_type ?? null,
    entry_model: signal.entry_model ?? null,
    rr_ratio: signal.rr_ratio ?? null,
    is_stale: false,
    broker_exists: true,
  };
}
```

- [ ] **Step 4: Update the dashboard page to use the helper**

```ts
import { mapSignalToFallbackPosition } from '@/components/dashboard/openPositionFallback';

const fallbackOpenPositions = useMemo(() => {
  const openStatuses = new Set(['open', 'active', 'executed', 'pending', 'spin']);

  return signals
    .filter((signal) => {
      const status = String(signal.status || '').toLowerCase();
      if (!openStatuses.has(status)) return false;
      if (signal.closed_at || signal.exit_price != null) return false;
      if (status === 'executed' && !signal.broker_order_id && !signal.broker_profile_id) return false;
      return true;
    })
    .map((signal, index) => mapSignalToFallbackPosition(signal, index));
}, [signals]);
```

- [ ] **Step 5: Run the frontend test and the existing app tests that cover the dashboard area**

Run: `cd frontend && npx vitest run src/components/dashboard/openPositionFallback.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/page.tsx frontend/src/components/dashboard/openPositionFallback.ts frontend/src/components/dashboard/openPositionFallback.test.ts
git commit -m "DEV-213: tighten dashboard live positions fallback"
```

### Task 5: Regression Verification

**Files:**
- Modify: `docs/worklog.md`
- Modify: `docs/bugs.md`
- Test: `tests/test_live_positions_aggregator.py`
- Test: `tests/test_sprint23_api_filters.py`
- Test: `frontend/src/components/dashboard/openPositionFallback.test.ts`

- [ ] **Step 1: Run the backend regression suite for this feature**

Run: `PYTHONPATH=. pytest tests/test_live_positions_aggregator.py tests/test_sprint23_api_filters.py -v`
Expected: PASS

- [ ] **Step 2: Run the frontend regression test for the fallback mapper**

Run: `cd frontend && npx vitest run src/components/dashboard/openPositionFallback.test.ts`
Expected: PASS

- [ ] **Step 3: Update worklog and bug notes**

```md
- [src/api_positions.py] Open positions and live account summary were tied to a single broker adapter, causing the dashboard to miss real live positions in multi-account mode [added multi-profile aggregation across MetaAPI and cTrader with partial-failure handling]
```

```md
- 2026-04-23 | `src/api_positions.py` | Dashboard live positions degraded to signal fallback because `/positions/active` depended on one primary adapter instead of aggregating all live-capable broker profiles | Added multi-account, multi-venue live position aggregation and corrected the dashboard fallback size mapping
```

- [ ] **Step 4: Commit the verification/docs pass**

```bash
git add docs/worklog.md docs/bugs.md
git commit -m "DEV-213: document multi-account live positions fix"
```
