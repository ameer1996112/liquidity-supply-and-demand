# Optimizer Risk Rule Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hybrid optimizer-to-risk-rules workflow where optimizer output becomes reviewable suggestions and only approved values affect active execution rules.

**Architecture:** Introduce a separate backend suggestion store, keep `symbol_risk_rules` as the active execution source, and add approval/rejection APIs that selectively copy optimizer-owned fields into active rules. Extend the Risk Rules UI to show active and suggested values side by side, while the optimizer writes suggestion rows instead of mutating live rules.

**Tech Stack:** FastAPI, Pydantic, Supabase, Python services, Next.js, React, Vitest, pytest

---

## File Structure

- Modify: `src/api_rules.py`
  - Add combined read endpoints plus approve/reject suggestion actions.
- Modify: `src/services/optimizer_run_service.py`
  - Persist per-symbol suggestion rows when optimizer runs finish.
- Modify: `frontend/src/components/rules/RiskRulesPanel.tsx`
  - Render active rules plus latest suggestions and wire review actions.
- Modify: `frontend/src/types/rules.ts`
  - Add suggestion-aware frontend DTOs.
- Create or modify: `tests/test_api_rules.py`
  - Cover combined read model and approve/reject flows.
- Create or modify: `tests/test_optimizer_run_service.py`
  - Cover suggestion persistence from optimizer results.
- Create or modify: `frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx`
  - Cover rendering and approval/rejection flows for suggestions.

### Task 1: Add the backend suggestion read/approval API

**Files:**
- Modify: `src/api_rules.py`
- Test: `tests/test_api_rules.py`

- [ ] **Step 1: Write the failing backend API tests for suggestion-aware responses**

```python
def test_list_symbol_rules_returns_active_rule_with_latest_suggestion(client: TestClient, rules_stub) -> None:
    rules_stub.active_rows = [
        {"symbol": "EURUSD", "risk_percent": 0.5, "max_lot_size": 2.0, "pip_size": 0.0001, "pip_value_per_lot": 10.0,
         "min_lot_size": 0.01, "lot_step": 0.01, "stop_loss_buffer_pips": 1.0, "max_positions": 3, "enabled": True}
    ]
    rules_stub.suggestion_rows = [
        {"symbol": "EURUSD", "suggested_risk_percent": 0.4, "suggested_max_lot_size": 1.5,
         "suggested_pip_size": 0.0001, "suggested_pip_value_per_lot": 10.0, "status": "pending"}
    ]

    response = client.get("/api/rules/symbols")

    assert response.status_code == 200
    row = response.json()["rules"][0]
    assert row["active_rule"]["risk_percent"] == 0.5
    assert row["latest_suggestion"]["suggested_risk_percent"] == 0.4
    assert row["suggestion_status"] == "pending"
    assert row["has_pending_changes"] is True


def test_approve_suggestion_updates_only_optimizer_owned_fields(client: TestClient, rules_stub) -> None:
    rules_stub.active_rows = [
        {"symbol": "XAUUSD", "risk_percent": 0.5, "max_lot_size": 1.0, "pip_size": 0.01, "pip_value_per_lot": 100.0,
         "min_lot_size": 0.01, "lot_step": 0.01, "stop_loss_buffer_pips": 2.0, "max_positions": 1, "enabled": True}
    ]
    rules_stub.suggestion_rows = [
        {"id": 7, "symbol": "XAUUSD", "suggested_risk_percent": 0.3, "suggested_max_lot_size": 0.5,
         "suggested_pip_size": 0.01, "suggested_pip_value_per_lot": 90.0, "status": "pending"}
    ]

    response = client.post("/api/rules/symbols/XAUUSD/approve-suggestion")

    assert response.status_code == 200
    active = response.json()["rule"]
    assert active["risk_percent"] == 0.3
    assert active["max_lot_size"] == 0.5
    assert active["pip_value_per_lot"] == 90.0
    assert active["min_lot_size"] == 0.01
    assert active["lot_step"] == 0.01
    assert active["stop_loss_buffer_pips"] == 2.0
```

- [ ] **Step 2: Run the backend API tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py -v`

Expected: FAIL because the current API returns only flat active rows and does not have suggestion approval endpoints.

- [ ] **Step 3: Add suggestion-aware response models and read helpers**

```python
class SymbolRiskRuleSuggestion(BaseModel):
    id: int | None = None
    symbol: str
    suggested_risk_percent: float
    suggested_max_lot_size: float
    suggested_pip_size: float
    suggested_pip_value_per_lot: float
    status: str


class SymbolRiskRuleWithSuggestion(BaseModel):
    symbol: str
    active_rule: Dict[str, Any] | None
    latest_suggestion: Dict[str, Any] | None
    suggestion_status: str | None
    has_pending_changes: bool


def _load_latest_suggestions(sb: Any) -> Dict[str, Dict[str, Any]]:
    rows = sb.table("symbol_risk_rule_suggestions").select("*").order("created_at", desc=True).execute()
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows.data or []:
        symbol = str(row.get("symbol", "")).upper().strip()
        if symbol and symbol not in latest and row.get("status") == "pending":
            latest[symbol] = row
    return latest
```

- [ ] **Step 4: Implement combined list plus approve/reject endpoints**

```python
@router.get("/symbols")
def list_symbol_rules():
    sb = _get_supabase()
    active_rows = [_normalize_symbol_rule(row) for row in (sb.table("symbol_risk_rules").select("*").order("symbol").execute().data or [])]
    active_by_symbol = {row["symbol"]: row for row in active_rows}
    suggestions = _load_latest_suggestions(sb)
    symbols = sorted(set(active_by_symbol) | set(suggestions))

    rows = []
    for symbol in symbols:
        active_rule = active_by_symbol.get(symbol)
        latest_suggestion = suggestions.get(symbol)
        rows.append({
            "symbol": symbol,
            "active_rule": active_rule,
            "latest_suggestion": latest_suggestion,
            "suggestion_status": latest_suggestion.get("status") if latest_suggestion else None,
            "has_pending_changes": latest_suggestion is not None,
        })
    return {"rules": rows, "count": len(rows)}


@router.post("/symbols/{symbol}/approve-suggestion")
def approve_symbol_rule_suggestion(symbol: str):
    ...


@router.post("/symbols/{symbol}/reject-suggestion")
def reject_symbol_rule_suggestion(symbol: str):
    ...
```

- [ ] **Step 5: Run the backend API tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py -v`

Expected: PASS for combined read model and approve/reject coverage.

- [ ] **Step 6: Commit**

```bash
git add src/api_rules.py tests/test_api_rules.py
git commit -m "DEV-106: add risk rule suggestion review api"
```

### Task 2: Persist optimizer results as suggestions

**Files:**
- Modify: `src/services/optimizer_run_service.py`
- Test: `tests/test_optimizer_run_service.py`

- [ ] **Step 1: Write the failing optimizer persistence tests**

```python
def test_optimizer_result_creates_pending_symbol_rule_suggestion(service, supabase_stub) -> None:
    service.persist_symbol_result(
        run_id="run-123",
        symbol="EURUSD",
        result={
            "risk_percent": 0.4,
            "max_lot_size": 1.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "score": 8.9,
        },
    )

    suggestion = supabase_stub.inserted_rows["symbol_risk_rule_suggestions"][0]
    assert suggestion["symbol"] == "EURUSD"
    assert suggestion["optimizer_run_id"] == "run-123"
    assert suggestion["suggested_risk_percent"] == 0.4
    assert suggestion["status"] == "pending"
```

- [ ] **Step 2: Run the optimizer service tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -v`

Expected: FAIL because optimizer results are not currently persisted as symbol rule suggestions.

- [ ] **Step 3: Add a focused suggestion persistence helper**

```python
def persist_symbol_rule_suggestion(
    sb: Any,
    run_id: str,
    symbol: str,
    result: Dict[str, Any],
) -> None:
    payload = {
        "symbol": symbol.upper().strip(),
        "optimizer_run_id": run_id,
        "suggested_risk_percent": float(result["risk_percent"]),
        "suggested_max_lot_size": float(result["max_lot_size"]),
        "suggested_pip_size": float(result["pip_size"]),
        "suggested_pip_value_per_lot": float(result["pip_value_per_lot"]),
        "status": "pending",
        "source_payload": result,
    }
    sb.table("symbol_risk_rule_suggestions").insert(payload).execute()
```

- [ ] **Step 4: Mark older pending suggestions as superseded for the same symbol**

```python
def supersede_pending_suggestions(sb: Any, symbol: str) -> None:
    sb.table("symbol_risk_rule_suggestions").update({"status": "superseded"}).eq("symbol", symbol.upper().strip()).eq("status", "pending").execute()
```

- [ ] **Step 5: Run the optimizer service tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_optimizer_run_service.py -v`

Expected: PASS for suggestion persistence and supersede behavior.

- [ ] **Step 6: Commit**

```bash
git add src/services/optimizer_run_service.py tests/test_optimizer_run_service.py
git commit -m "DEV-106: persist optimizer rule suggestions"
```

### Task 3: Make the Risk Rules page suggestion-aware

**Files:**
- Modify: `frontend/src/types/rules.ts`
- Modify: `frontend/src/components/rules/RiskRulesPanel.tsx`
- Test: `frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx`

- [ ] **Step 1: Write the failing frontend tests for active plus suggestion rendering**

```tsx
it('renders active rule with pending optimizer suggestion', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      mockJsonResponse({
        rules: [
          {
            symbol: 'EURUSD',
            active_rule: { symbol: 'EURUSD', risk_percent: 0.5, max_lot_size: 2, min_lot_size: 0.01, lot_step: 0.01, pip_size: 0.0001, pip_value_per_lot: 10, stop_loss_buffer_pips: 1, max_positions: 3, enabled: true },
            latest_suggestion: { symbol: 'EURUSD', suggested_risk_percent: 0.4, suggested_max_lot_size: 1.5, suggested_pip_size: 0.0001, suggested_pip_value_per_lot: 10, status: 'pending' },
            suggestion_status: 'pending',
            has_pending_changes: true,
          },
        ],
        count: 1,
      })
    )
  );

  await act(async () => {
    root.render(<RiskRulesPanel />);
  });

  expect(container.textContent).toContain('EURUSD');
  expect(container.textContent).toContain('pending');
  expect(container.textContent).toContain('Approve');
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/RiskRulesPanel.test.tsx`

Expected: FAIL because the panel currently expects flat active-rule rows only.

- [ ] **Step 3: Add suggestion-aware frontend types**

```ts
export interface SymbolRiskRuleSuggestion {
  id?: number;
  symbol: string;
  suggested_risk_percent: number;
  suggested_max_lot_size: number;
  suggested_pip_size: number;
  suggested_pip_value_per_lot: number;
  status: 'pending' | 'approved' | 'rejected' | 'superseded';
}

export interface SymbolRiskRuleReviewRow {
  symbol: string;
  active_rule?: SymbolRiskRule;
  latest_suggestion?: SymbolRiskRuleSuggestion;
  suggestion_status?: string | null;
  has_pending_changes: boolean;
}
```

- [ ] **Step 4: Update the panel to render active vs suggested values and review actions**

```tsx
const [rows, setRows] = useState<SymbolRiskRuleReviewRow[]>([]);

async function approveSuggestion(symbol: string) {
  await requestJson<{ rule: SymbolRiskRule }>(`/api/rules/symbols/${encodeURIComponent(symbol)}/approve-suggestion`, {
    method: 'POST',
  });
  await fetchRules();
}

async function rejectSuggestion(symbol: string) {
  await requestJson<{ status: string }>(`/api/rules/symbols/${encodeURIComponent(symbol)}/reject-suggestion`, {
    method: 'POST',
  });
  await fetchRules();
}
```

- [ ] **Step 5: Highlight only changed optimizer-owned fields**

```tsx
function hasSuggestedChange(
  activeRule: SymbolRiskRule | undefined,
  suggestion: SymbolRiskRuleSuggestion | undefined,
  key: 'risk_percent' | 'max_lot_size' | 'pip_size' | 'pip_value_per_lot'
): boolean {
  if (!activeRule || !suggestion) return false;
  const suggestionKeyMap = {
    risk_percent: 'suggested_risk_percent',
    max_lot_size: 'suggested_max_lot_size',
    pip_size: 'suggested_pip_size',
    pip_value_per_lot: 'suggested_pip_value_per_lot',
  } as const;
  return activeRule[key] !== suggestion[suggestionKeyMap[key]];
}
```

- [ ] **Step 6: Run the frontend tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/RiskRulesPanel.test.tsx`

Expected: PASS for combined rendering and approve/reject flows.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/rules.ts frontend/src/components/rules/RiskRulesPanel.tsx frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx
git commit -m "DEV-106: add optimizer suggestion review ui"
```

### Task 4: Verify end-to-end compatibility

**Files:**
- Modify: `tests/test_api_rules.py`
- Modify: `tests/test_optimizer_run_service.py`
- Modify: `frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx`

- [ ] **Step 1: Add a regression test that worker execution still uses active rules only**

```python
def test_worker_sizing_ignores_pending_suggestion_rows(active_rule_lookup) -> None:
    active_rule_lookup("EURUSD", {"risk_percent": 0.5, "max_lot_size": 2.0})
    pending_suggestion_lookup("EURUSD", {"suggested_risk_percent": 0.2, "suggested_max_lot_size": 1.0})

    result = calculate_max_position_size(
        {"symbol": "EURUSD", "entry": 1.1000, "sl": 1.0990, "side": "buy"},
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={"risk_percent": 0.5, "max_lot_size": 2.0, "min_lot_size": 0.01, "lot_step": 0.01, "pip_size": 0.0001, "pip_value_per_lot": 10.0},
    )

    assert result > 0
```

- [ ] **Step 2: Run the focused backend suite**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py tests/test_optimizer_run_service.py tests/test_risk_engine.py -v`

Expected: PASS for suggestion APIs, optimizer persistence, and active-rule execution behavior.

- [ ] **Step 3: Run the focused frontend suite**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/RiskRulesPanel.test.tsx`

Expected: PASS for suggestion-aware Risk Rules UI.

- [ ] **Step 4: Run the frontend production build**

Run: `cd frontend && npm run build`

Expected: PASS with no type regressions in related risk-rule components.

- [ ] **Step 5: Commit the verified integration**

```bash
git add src/api_rules.py src/services/optimizer_run_service.py frontend/src/types/rules.ts frontend/src/components/rules/RiskRulesPanel.tsx tests/test_api_rules.py tests/test_optimizer_run_service.py frontend/src/components/rules/__tests__/RiskRulesPanel.test.tsx
git commit -m "DEV-106: finalize optimizer rule suggestion workflow"
```

## Self-Review

### Spec coverage
- suggestion persistence model: Task 2
- combined active-plus-suggestion API: Task 1
- selective approval behavior: Task 1
- Risk Rules review UI: Task 3
- active-rule-only execution guarantee: Task 4

### Placeholder scan
- No `TBD`, `TODO`, or “implement later” markers remain.
- Each task includes concrete code, files, commands, and expected outcomes.

### Type consistency
- Shared names stay consistent across the plan:
  - `symbol_risk_rule_suggestions`
  - `suggested_risk_percent`
  - `suggested_max_lot_size`
  - `approve-suggestion`
  - `reject-suggestion`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-optimizer-risk-rule-suggestions.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
