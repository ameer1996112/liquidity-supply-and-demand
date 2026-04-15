# Backend-Driven Per-Pair Risk Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Risk & Rules page to backend-owned per-symbol risk rules and make execution-time position sizing consume those rules dynamically.

**Architecture:** Extend the existing `symbol_risk_rules` contract in the backend, add centralized validation in `src/api_rules.py`, teach the risk engine to consume the expanded rule fields consistently, and refactor the frontend panel to call backend endpoints instead of Supabase directly. Keep the worker’s current symbol-rule lookup path intact, but make the rules it loads richer and validated.

**Tech Stack:** FastAPI, Pydantic, Supabase, Python risk engine, Next.js, React, Vitest, pytest

---

## File Structure

- Modify: `src/api_rules.py`
  - Add the new symbol rule fields, normalization helpers, validation, and backend-default response shaping.
- Modify: `src/core/risk_engine.py`
  - Make sizing consume `min_lot_size`, `lot_step`, and `stop_loss_buffer_pips` consistently and fail clearly on disabled or invalid rules.
- Modify: `frontend/src/components/rules/RiskRulesPanel.tsx`
  - Replace direct Supabase CRUD with backend API calls and surface the new fields in the editor.
- Modify: `frontend/src/types/rules.ts`
  - Align the frontend type with the backend DTO.
- Create or modify: `tests/test_api_rules.py`
  - Cover symbol rule CRUD validation and defaults.
- Create or modify: `tests/test_risk_engine.py`
  - Cover min lot rejection, lot-step rounding, stop-loss buffer, and disabled symbol behavior.
- Create or modify: `frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx`
  - Cover loading, editing, and saving backend-driven symbol rules.

### Task 1: Extend the backend symbol rule contract

**Files:**
- Modify: `src/api_rules.py`
- Test: `tests/test_api_rules.py`

- [ ] **Step 1: Write the failing API tests for defaults and validation**

```python
from fastapi.testclient import TestClient


def test_list_symbol_rules_applies_backend_defaults(client: TestClient, mock_supabase_rules_table) -> None:
    mock_supabase_rules_table.select_rows = [
        {
            "symbol": "EURUSD",
            "max_lot_size": 2.0,
            "risk_percent": 0.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "max_positions": 3,
            "enabled": True,
            "min_lot_size": None,
            "lot_step": None,
            "stop_loss_buffer_pips": None,
        }
    ]

    response = client.get("/api/rules/symbols")

    assert response.status_code == 200
    rule = response.json()["rules"][0]
    assert rule["min_lot_size"] == 0.01
    assert rule["lot_step"] == 0.01
    assert rule["stop_loss_buffer_pips"] == 1.0


def test_create_symbol_rule_rejects_min_lot_above_max(client: TestClient) -> None:
    response = client.post(
        "/api/rules/symbols",
        json={
            "symbol": "XAUUSD",
            "max_lot_size": 0.1,
            "min_lot_size": 0.2,
            "lot_step": 0.01,
            "risk_percent": 0.5,
            "pip_size": 0.01,
            "pip_value_per_lot": 100.0,
            "stop_loss_buffer_pips": 1.0,
            "max_positions": 1,
            "enabled": True,
        },
    )

    assert response.status_code == 422
    assert "min_lot_size" in response.text
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py -v`

Expected: FAIL because the current API models do not include `min_lot_size`, `lot_step`, `stop_loss_buffer_pips`, or the new validation/defaulting behavior.

- [ ] **Step 3: Implement the backend DTO, normalization, and validation**

```python
from pydantic import BaseModel, Field, model_validator


DEFAULT_MIN_LOT_SIZE = 0.01
DEFAULT_LOT_STEP = 0.01
DEFAULT_STOP_LOSS_BUFFER_PIPS = 1.0
MAX_SAFE_RISK_PERCENT = 2.0
MAX_SAFE_POSITIONS = 10


class SymbolRiskRuleBase(BaseModel):
    max_lot_size: float = Field(default=1.0, gt=0)
    min_lot_size: float = Field(default=DEFAULT_MIN_LOT_SIZE, gt=0)
    lot_step: float = Field(default=DEFAULT_LOT_STEP, gt=0)
    risk_percent: float = Field(default=1.0, gt=0, le=MAX_SAFE_RISK_PERCENT)
    pip_size: float = Field(default=0.0001, gt=0)
    pip_value_per_lot: float = Field(default=10.0, gt=0)
    stop_loss_buffer_pips: float = Field(default=DEFAULT_STOP_LOSS_BUFFER_PIPS, ge=0)
    max_positions: int = Field(default=3, ge=1, le=MAX_SAFE_POSITIONS)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_lot_bounds(self) -> "SymbolRiskRuleBase":
        if self.min_lot_size > self.max_lot_size:
            raise ValueError("min_lot_size cannot exceed max_lot_size")
        return self


class SymbolRiskRuleCreate(SymbolRiskRuleBase):
    symbol: str = Field(..., min_length=1)


class SymbolRiskRuleUpdate(BaseModel):
    max_lot_size: Optional[float] = Field(default=None, gt=0)
    min_lot_size: Optional[float] = Field(default=None, gt=0)
    lot_step: Optional[float] = Field(default=None, gt=0)
    risk_percent: Optional[float] = Field(default=None, gt=0, le=MAX_SAFE_RISK_PERCENT)
    pip_size: Optional[float] = Field(default=None, gt=0)
    pip_value_per_lot: Optional[float] = Field(default=None, gt=0)
    stop_loss_buffer_pips: Optional[float] = Field(default=None, ge=0)
    max_positions: Optional[int] = Field(default=None, ge=1, le=MAX_SAFE_POSITIONS)
    enabled: Optional[bool] = None


def _normalize_symbol_rule(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    normalized["symbol"] = str(row.get("symbol", "")).upper().strip()
    normalized["min_lot_size"] = float(row.get("min_lot_size") or DEFAULT_MIN_LOT_SIZE)
    normalized["lot_step"] = float(row.get("lot_step") or DEFAULT_LOT_STEP)
    normalized["stop_loss_buffer_pips"] = float(
        row.get("stop_loss_buffer_pips") or DEFAULT_STOP_LOSS_BUFFER_PIPS
    )
    return normalized


def _validate_symbol_rule_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    min_lot_size = float(payload.get("min_lot_size") or DEFAULT_MIN_LOT_SIZE)
    max_lot_size = float(payload["max_lot_size"])
    if min_lot_size > max_lot_size:
        raise HTTPException(status_code=422, detail="min_lot_size cannot exceed max_lot_size")
    return payload
```

- [ ] **Step 4: Wire the list/create/update handlers to use the normalized payload**

```python
@router.get("/symbols")
def list_symbol_rules():
    sb = _get_supabase()
    result = sb.table("symbol_risk_rules").select("*").order("symbol").execute()
    rules = [_normalize_symbol_rule(row) for row in (result.data or [])]
    return {"rules": rules, "count": len(rules)}


@router.post("/symbols", status_code=201)
def create_symbol_rule(body: SymbolRiskRuleCreate):
    sb = _get_supabase()
    data = _validate_symbol_rule_payload(body.model_dump())
    data["symbol"] = data["symbol"].upper().strip()
    result = sb.table("symbol_risk_rules").insert(data).execute()
    return {"rule": _normalize_symbol_rule(result.data[0] if result.data else data)}
```

- [ ] **Step 5: Run the API tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py -v`

Expected: PASS for the new defaults and validation coverage.

- [ ] **Step 6: Commit**

```bash
git add src/api_rules.py tests/test_api_rules.py
git commit -m "DEV-106: extend backend symbol risk rules"
```

### Task 2: Make the risk engine enforce the expanded rule fields

**Files:**
- Modify: `src/core/risk_engine.py`
- Test: `tests/test_risk_engine.py`

- [ ] **Step 1: Write the failing risk-engine tests**

```python
from src.core.risk_engine import calculate_max_position_size, calculate_position_size_with_spread


def test_calculate_max_position_size_rejects_disabled_symbol() -> None:
    payload = {"symbol": "EURUSD", "entry": 1.1000, "sl": 1.0980, "side": "buy"}
    result = calculate_position_size_with_spread(
        payload,
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={
            "enabled": False,
            "risk_percent": 0.5,
            "max_lot_size": 2.0,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 1.0,
        },
    )

    assert result["rejected"] is True
    assert result["rejection_reason"] == "symbol_disabled"


def test_calculate_max_position_size_rounds_to_lot_step() -> None:
    lots = calculate_max_position_size(
        {"symbol": "EURUSD", "entry": 1.1000, "sl": 1.0990, "side": "buy"},
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={
            "enabled": True,
            "risk_percent": 0.5,
            "max_lot_size": 10.0,
            "min_lot_size": 0.10,
            "lot_step": 0.10,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 1.0,
        },
    )

    assert lots % 0.10 == 0
    assert lots >= 0.10
```

- [ ] **Step 2: Run the risk-engine tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py -v`

Expected: FAIL because disabled-symbol rejection and consistent field consumption are not fully enforced yet.

- [ ] **Step 3: Implement normalized override handling in the risk engine**

```python
def _normalize_symbol_overrides(symbol_overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    overrides = dict(symbol_overrides or {})
    overrides["enabled"] = bool(overrides.get("enabled", True))
    overrides["min_lot_size"] = float(overrides.get("min_lot_size") or 0.01)
    overrides["lot_step"] = float(overrides.get("lot_step") or 0.01)
    overrides["stop_loss_buffer_pips"] = float(overrides.get("stop_loss_buffer_pips") or 1.0)
    return overrides


def calculate_position_size_with_spread(...):
    overrides = _normalize_symbol_overrides(symbol_overrides)
    if symbol_overrides is not None and not overrides["enabled"]:
        return {
            "lots": 0.0,
            "risk_usd": 0.0,
            "sl_pips": 0.0,
            "spread_pips": 0.0,
            "effective_sl_pips": 0.0,
            "pip_value_per_lot": 0.0,
            "rejected": True,
            "rejection_reason": "symbol_disabled",
        }
```

- [ ] **Step 4: Make the max-position-size path reuse the normalized fields**

```python
if symbol_overrides:
    overrides = _normalize_symbol_overrides(symbol_overrides)
    pip_size = float(overrides.get("pip_size", 0.0001))
    pip_value_per_lot = float(overrides.get("pip_value_per_lot", 10.0))
    risk_percent = float(overrides.get("risk_percent", risk_percent))
    max_lot_cap = float(overrides.get("max_lot_size", 10.0))
    min_lot_size = float(overrides.get("min_lot_size", 0.01))
    lot_step = float(overrides.get("lot_step", 0.01))
    sl_buffer_pips = float(overrides.get("stop_loss_buffer_pips", 1.0))
```

- [ ] **Step 5: Run the risk-engine tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py -v`

Expected: PASS for disabled-symbol rejection, min-lot enforcement, and lot-step rounding.

- [ ] **Step 6: Commit**

```bash
git add src/core/risk_engine.py tests/test_risk_engine.py
git commit -m "DEV-106: enforce dynamic symbol sizing rules"
```

### Task 3: Align frontend types and switch the panel to backend APIs

**Files:**
- Modify: `frontend/src/types/rules.ts`
- Modify: `frontend/src/components/rules/RiskRulesPanel.tsx`
- Test: `frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RiskRulesPanel } from '../RiskRulesPanel';


test('loads symbol rules from backend api', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        rules: [
          {
            symbol: 'EURUSD',
            max_lot_size: 2,
            min_lot_size: 0.01,
            lot_step: 0.01,
            risk_percent: 0.5,
            pip_size: 0.0001,
            pip_value_per_lot: 10,
            stop_loss_buffer_pips: 1,
            max_positions: 3,
            enabled: true,
          },
        ],
      }),
    })
  );

  render(<RiskRulesPanel />);

  expect(await screen.findByText('EURUSD')).toBeInTheDocument();
});


test('saves edited symbol rules to backend api', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ rules: [] }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ rule: { symbol: 'XAUUSD' } }),
    });

  vi.stubGlobal('fetch', fetchMock);
  render(<RiskRulesPanel />);

  await userEvent.click(screen.getByRole('button', { name: /add symbol/i }));
  await userEvent.type(screen.getByPlaceholderText('XAUUSD'), 'XAUUSD');
  await userEvent.click(screen.getByRole('button', { name: '' }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/rules/symbols',
      expect.objectContaining({ method: 'POST' })
    );
  });
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/RiskRulesPanel.test.tsx`

Expected: FAIL because the panel currently uses Supabase directly and the type does not include the new fields.

- [ ] **Step 3: Expand the frontend type to match the backend DTO**

```ts
export interface SymbolRiskRule {
  id?: string;
  symbol: string;
  max_lot_size: number;
  min_lot_size: number;
  lot_step: number;
  risk_percent: number;
  pip_size: number;
  pip_value_per_lot: number;
  stop_loss_buffer_pips: number;
  max_positions: number;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}
```

- [ ] **Step 4: Replace Supabase CRUD with fetch helpers in the panel**

```tsx
async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || 'Request failed');
  }
  return payload as T;
}


const fetchRules = useCallback(async () => {
  setLoading(true);
  setError('');
  try {
    const payload = await requestJson<{ rules: SymbolRiskRule[] }>('/api/rules/symbols');
    setRules(payload.rules || []);
  } catch (e: unknown) {
    setError(e instanceof Error ? e.message : 'Failed to load rules');
  } finally {
    setLoading(false);
  }
}, []);
```

- [ ] **Step 5: Add the new editable fields and backend-owned copy**

```tsx
const EMPTY_ROW: EditingRow = {
  symbol: '',
  max_lot_size: 1.0,
  min_lot_size: 0.01,
  lot_step: 0.01,
  risk_percent: 1.0,
  pip_size: 0.0001,
  pip_value_per_lot: 10.0,
  stop_loss_buffer_pips: 1.0,
  max_positions: 3,
  enabled: true,
};

<p className="text-[11px] text-[var(--to-text-dim)]">
  Backend calculates final position size at execution time from these rules.
</p>
```

- [ ] **Step 6: Run the frontend tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/RiskRulesPanel.test.tsx`

Expected: PASS for backend loading and save behavior.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/rules.ts frontend/src/components/rules/RiskRulesPanel.tsx frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx
git commit -m "DEV-106: move risk rules panel to backend api"
```

### Task 4: Verify integration paths and guard compatibility

**Files:**
- Modify: `src/api_rules.py`
- Modify: `src/core/risk_engine.py`
- Modify: `frontend/src/components/rules/RiskRulesPanel.tsx`
- Modify: `tests/test_api_rules.py`
- Modify: `tests/test_risk_engine.py`

- [ ] **Step 1: Add a regression test that existing rows without new DB fields still work**

```python
def test_existing_symbol_rule_rows_without_new_columns_use_defaults(client: TestClient, mock_supabase_rules_table) -> None:
    mock_supabase_rules_table.select_rows = [
        {
            "symbol": "GBPUSD",
            "max_lot_size": 1.0,
            "risk_percent": 0.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "max_positions": 2,
            "enabled": True,
        }
    ]

    response = client.get("/api/rules/symbols")
    rule = response.json()["rules"][0]
    assert rule["min_lot_size"] == 0.01
    assert rule["lot_step"] == 0.01
    assert rule["stop_loss_buffer_pips"] == 1.0
```

- [ ] **Step 2: Run the focused regression suites**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py tests/test_risk_engine.py -v`

Expected: PASS across API defaults, validation, and risk-engine sizing behavior.

- [ ] **Step 3: Run the frontend test suite for the panel**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/RiskRulesPanel.test.tsx`

Expected: PASS for the backend-driven panel flow.

- [ ] **Step 4: Run the project verification commands that are relevant to the touched areas**

Run: `ruff check src/api_rules.py src/core/risk_engine.py tests/test_api_rules.py tests/test_risk_engine.py`

Expected: PASS with no new lint issues in the touched backend files.

Run: `cd frontend && npm run build`

Expected: PASS if the Risk Rules type and component changes integrate cleanly. If the pre-existing known `tradingMetrics.test.ts` failure is unrelated, ignore that test file and focus on build success.

- [ ] **Step 5: Commit the verification-safe final integration**

```bash
git add src/api_rules.py src/core/risk_engine.py frontend/src/components/rules/RiskRulesPanel.tsx frontend/src/types/rules.ts tests/test_api_rules.py tests/test_risk_engine.py frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx
git commit -m "DEV-106: finalize backend-driven risk rules"
```

## Self-Review

### Spec coverage
- Backend rule fields and validation: Task 1
- Risk engine execution-time sizing behavior: Task 2
- Frontend backend-owned editing flow: Task 3
- Compatibility and verification: Task 4

### Placeholder scan
- No `TBD`, `TODO`, or deferred implementation markers remain.
- Each task includes concrete files, code, commands, and expected results.

### Type consistency
- Shared field names are consistent across the plan:
  - `min_lot_size`
  - `lot_step`
  - `stop_loss_buffer_pips`
  - `max_lot_size`
  - `risk_percent`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-backend-driven-risk-rules.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
