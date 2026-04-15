# Pass Evaluation Risk Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend-only pass-evaluation risk mode that dynamically adjusts effective per-trade risk using pair performance, same-day pair frequency, and account safety state before final lot sizing.

**Architecture:** Extend the risk engine with a deterministic evaluation-mode calculator, feed it backend-derived performance and frequency inputs from the worker, and preserve the current separation of concerns: Pine and guards decide whether a signal is valid, while the backend alone decides effective risk percent and final position size. Keep active `symbol_risk_rules` as the base source of risk and clamp the dynamic result with hard evaluation-mode caps.

**Tech Stack:** Python, FastAPI-adjacent backend modules, Supabase-backed reads, Redis-backed cache patterns, pytest

---

## File Structure

- Modify: `src/core/risk_engine.py`
  - Add pass-evaluation mode configuration, dynamic multiplier calculation, clamping, and explainable output.
- Modify: `src/worker.py`
  - Derive pair-frequency and recent-performance inputs and pass them into risk sizing.
- Modify: `src/api_risk_monitor.py` or related read surface if needed
  - Expose effective risk state for visibility if the implementation includes operator-facing diagnostics.
- Create or modify: `tests/test_risk_engine.py`
  - Cover effective risk calculation, clamps, and lockout behavior.
- Create or modify: `tests/test_pass_eval_risk.py`
  - Cover worker-fed dynamic input scenarios and regression against current static sizing.

### Task 1: Add evaluation-mode dynamic risk calculation to the risk engine

**Files:**
- Modify: `src/core/risk_engine.py`
- Test: `tests/test_risk_engine.py`

- [ ] **Step 1: Write the failing tests for effective evaluation risk**

```python
from src.core.risk_engine import calculate_effective_risk_percent


def test_pass_eval_reduces_risk_for_repeated_same_day_trades() -> None:
    effective = calculate_effective_risk_percent(
        base_risk_percent=0.5,
        mode="PASS_EVAL",
        pair_performance_state="neutral",
        same_day_trade_count=3,
        account_safety_state="normal",
    )

    assert effective < 0.5
    assert round(effective, 3) == 0.35


def test_pass_eval_caps_risk_inside_mode_bounds() -> None:
    effective = calculate_effective_risk_percent(
        base_risk_percent=1.0,
        mode="PASS_EVAL",
        pair_performance_state="strong",
        same_day_trade_count=0,
        account_safety_state="normal",
    )

    assert effective <= 0.75
```

- [ ] **Step 2: Run the risk-engine tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py -v`

Expected: FAIL because `calculate_effective_risk_percent` and evaluation-mode dynamic multipliers do not exist yet.

- [ ] **Step 3: Add evaluation-mode constants and a pure effective-risk helper**

```python
PASS_EVAL_MIN_RISK_PCT = 0.25
PASS_EVAL_MAX_RISK_PCT = 0.75

PAIR_PERFORMANCE_MULTIPLIERS = {
    "strong": 1.05,
    "neutral": 1.00,
    "weak": 0.75,
    "very_weak": 0.50,
}

ACCOUNT_SAFETY_MULTIPLIERS = {
    "normal": 1.00,
    "caution": 0.75,
    "defensive": 0.50,
    "survival": 0.25,
    "lockout": 0.00,
}

FREQUENCY_MULTIPLIERS = {
    0: 1.00,
    1: 0.85,
    2: 0.70,
    3: 0.50,
}


def calculate_effective_risk_percent(
    *,
    base_risk_percent: float,
    mode: str,
    pair_performance_state: str = "neutral",
    same_day_trade_count: int = 0,
    account_safety_state: str = "normal",
) -> float:
    if mode != "PASS_EVAL":
        return base_risk_percent

    performance_multiplier = PAIR_PERFORMANCE_MULTIPLIERS.get(pair_performance_state, 1.0)
    frequency_multiplier = FREQUENCY_MULTIPLIERS.get(same_day_trade_count, 0.25)
    safety_multiplier = ACCOUNT_SAFETY_MULTIPLIERS.get(account_safety_state, 1.0)

    effective = base_risk_percent * performance_multiplier * frequency_multiplier * safety_multiplier
    return max(PASS_EVAL_MIN_RISK_PCT, min(PASS_EVAL_MAX_RISK_PCT, effective))
```

- [ ] **Step 4: Thread effective risk into lot sizing without changing Pine validation**

```python
effective_risk_percent = calculate_effective_risk_percent(
    base_risk_percent=risk_percent,
    mode=str(payload.get("_risk_mode", "NORMAL")),
    pair_performance_state=str(payload.get("_pair_performance_state", "neutral")),
    same_day_trade_count=int(payload.get("_same_day_trade_count", 0)),
    account_safety_state=str(payload.get("_account_safety_state", "normal")),
)
max_risk_usd = account_balance * (effective_risk_percent / 100.0)
```

- [ ] **Step 5: Run the risk-engine tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py -v`

Expected: PASS for evaluation-mode dynamic risk behavior and clamp coverage.

- [ ] **Step 6: Commit**

```bash
git add src/core/risk_engine.py tests/test_risk_engine.py
git commit -m "DEV-107: add pass evaluation risk calculation"
```

### Task 2: Derive worker-side pair frequency and performance inputs

**Files:**
- Modify: `src/worker.py`
- Test: `tests/test_pass_eval_risk.py`

- [ ] **Step 1: Write the failing worker-side tests for dynamic input derivation**

```python
def test_same_day_trade_count_for_symbol_uses_recent_trade_rows(worker_store) -> None:
    worker_store.closed_trades_today = [
        {"symbol": "EURUSD"},
        {"symbol": "EURUSD"},
        {"symbol": "GBPUSD"},
    ]

    count = get_same_day_trade_count("EURUSD", worker_store)

    assert count == 2


def test_pair_performance_state_becomes_weak_after_recent_losses(worker_store) -> None:
    worker_store.recent_pair_results = [
        {"symbol": "EURUSD", "pnl_usd": -50},
        {"symbol": "EURUSD", "pnl_usd": -30},
        {"symbol": "EURUSD", "pnl_usd": 10},
    ]

    state = get_pair_performance_state("EURUSD", worker_store)

    assert state in {"weak", "very_weak"}
```

- [ ] **Step 2: Run the worker-side tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_pass_eval_risk.py -v`

Expected: FAIL because same-day trade count and pair performance derivation helpers do not exist yet.

- [ ] **Step 3: Add focused worker helpers for pair-frequency and performance state**

```python
def get_same_day_trade_count(symbol: str, sb: Any) -> int:
    rows = (
        sb.table("trading_signals")
        .select("symbol")
        .eq("symbol", symbol.upper())
        .gte("created_at", _today_start_utc())
        .in_("status", ["executed", "closed", "active"])
        .execute()
    ).data or []
    return len(rows)


def get_pair_performance_state(symbol: str, sb: Any) -> str:
    rows = (
        sb.table("trading_signals")
        .select("pnl_usd")
        .eq("symbol", symbol.upper())
        .in_("status", ["closed", "CLOSED"])
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    ).data or []
    pnl_values = [float(row.get("pnl_usd") or 0.0) for row in rows]
    if not pnl_values:
        return "neutral"
    if sum(pnl_values) < -100:
        return "very_weak"
    if sum(pnl_values) < 0:
        return "weak"
    if sum(pnl_values) > 100:
        return "strong"
    return "neutral"
```

- [ ] **Step 4: Pass derived inputs into the existing risk payload**

```python
payload["_risk_mode"] = "PASS_EVAL" if getattr(settings, "pass_eval_mode", False) else "NORMAL"
payload["_same_day_trade_count"] = get_same_day_trade_count(symbol, supabase)
payload["_pair_performance_state"] = get_pair_performance_state(symbol, supabase)
payload["_account_safety_state"] = get_account_safety_state(...)
```

- [ ] **Step 5: Run the worker-side tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_pass_eval_risk.py -v`

Expected: PASS for same-day frequency and recent pair performance derivation.

- [ ] **Step 6: Commit**

```bash
git add src/worker.py tests/test_pass_eval_risk.py
git commit -m "DEV-107: feed pass eval inputs into risk sizing"
```

### Task 3: Add account-safety state derivation and lockout behavior

**Files:**
- Modify: `src/core/risk_engine.py`
- Modify: `src/worker.py`
- Test: `tests/test_pass_eval_risk.py`

- [ ] **Step 1: Write the failing tests for account-safety reductions**

```python
from src.core.risk_engine import calculate_effective_risk_percent


def test_pass_eval_account_safety_defensive_state_halves_risk() -> None:
    effective = calculate_effective_risk_percent(
        base_risk_percent=0.5,
        mode="PASS_EVAL",
        pair_performance_state="neutral",
        same_day_trade_count=0,
        account_safety_state="defensive",
    )

    assert effective == 0.25


def test_pass_eval_lockout_forces_zero_risk_before_execution() -> None:
    effective = calculate_effective_risk_percent(
        base_risk_percent=0.5,
        mode="PASS_EVAL",
        pair_performance_state="strong",
        same_day_trade_count=0,
        account_safety_state="lockout",
    )

    assert effective == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py tests/test_pass_eval_risk.py -v`

Expected: FAIL because lockout behavior and account-safety state mapping are not fully implemented.

- [ ] **Step 3: Implement account-safety state derivation in the worker**

```python
def get_account_safety_state(*, daily_loss_utilization: float, drawdown_utilization: float, losing_streak: int) -> str:
    if daily_loss_utilization >= 0.9 or drawdown_utilization >= 0.9:
        return "lockout"
    if daily_loss_utilization >= 0.7 or drawdown_utilization >= 0.7:
        return "survival"
    if daily_loss_utilization >= 0.5 or drawdown_utilization >= 0.5 or losing_streak >= 3:
        return "defensive"
    if daily_loss_utilization >= 0.3 or drawdown_utilization >= 0.3:
        return "caution"
    return "normal"
```

- [ ] **Step 4: Make lockout stop risk allocation before lot sizing**

```python
if mode == "PASS_EVAL" and account_safety_state == "lockout":
    return 0.0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py tests/test_pass_eval_risk.py -v`

Expected: PASS for defensive reductions and lockout behavior.

- [ ] **Step 6: Commit**

```bash
git add src/core/risk_engine.py src/worker.py tests/test_risk_engine.py tests/test_pass_eval_risk.py
git commit -m "DEV-107: add account safety controls to pass eval mode"
```

### Task 4: Add operator visibility for effective risk state

**Files:**
- Modify: `src/api_risk_monitor.py`
- Test: `tests/test_api_risk_monitor.py`

- [ ] **Step 1: Write the failing API tests for pass-eval visibility fields**

```python
def test_risk_monitor_includes_pass_eval_state(client: TestClient) -> None:
    response = client.get("/risk-monitor/status")
    body = response.json()

    assert "risk_mode" in body
    assert "effective_risk_pct" in body
    assert "base_risk_pct" in body
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_api_risk_monitor.py -v`

Expected: FAIL if the response does not yet include evaluation-mode-specific visibility.

- [ ] **Step 3: Expose effective risk metadata in the risk monitor read model**

```python
return {
    ...,
    "risk_mode": current_mode,
    "base_risk_pct": base_risk_pct,
    "effective_risk_pct": effective_risk_pct,
    "risk_label": safety_state,
}
```

- [ ] **Step 4: Run the API tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_api_risk_monitor.py -v`

Expected: PASS for added operator-visibility fields.

- [ ] **Step 5: Commit**

```bash
git add src/api_risk_monitor.py tests/test_api_risk_monitor.py
git commit -m "DEV-107: expose pass eval risk state"
```

### Task 5: Full verification and integration

**Files:**
- Modify: `tests/test_risk_engine.py`
- Modify: `tests/test_pass_eval_risk.py`
- Modify: `tests/test_api_risk_monitor.py`

- [ ] **Step 1: Run the backend verification suite for touched areas**

Run: `PYTHONPATH=. pytest tests/test_risk_engine.py tests/test_pass_eval_risk.py tests/test_api_risk_monitor.py -v`

Expected: PASS for evaluation-mode risk math, worker-derived inputs, and risk visibility.

- [ ] **Step 2: Run the existing risk-rule and optimizer suggestion suites to guard regressions**

Run: `PYTHONPATH=. pytest tests/test_api_rules.py tests/test_optimizer_run_service.py -v`

Expected: PASS so the new evaluation mode does not break the approved per-pair rule and suggestion flows.

- [ ] **Step 3: Run project lint or note environment limitation**

Run: `source ./venv/bin/activate && ruff check src/core/risk_engine.py src/worker.py tests/test_risk_engine.py tests/test_pass_eval_risk.py tests/test_api_risk_monitor.py`

Expected: PASS if `ruff` is available in the environment. If it is not installed, record that as an environment limitation.

- [ ] **Step 4: Commit the verified final integration**

```bash
git add src/core/risk_engine.py src/worker.py src/api_risk_monitor.py tests/test_risk_engine.py tests/test_pass_eval_risk.py tests/test_api_risk_monitor.py
git commit -m "DEV-107: finalize pass evaluation risk mode"
```

## Self-Review

### Spec coverage
- dynamic effective-risk formula: Task 1
- pair-frequency and performance inputs: Task 2
- account-safety reductions and lockout: Task 3
- operator visibility into current risk state: Task 4
- regression protection: Task 5

### Placeholder scan
- No `TBD`, `TODO`, or deferred implementation markers remain.
- Each task contains concrete file paths, code, commands, and expected outputs.

### Type consistency
- Shared names stay consistent across the plan:
  - `calculate_effective_risk_percent`
  - `pair_performance_state`
  - `same_day_trade_count`
  - `account_safety_state`
  - `PASS_EVAL`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-pass-evaluation-risk-mode.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
