# Pipeline Architecture Registry
> Last updated: DEV-98 (Surgical Safety Refactor)

## Overview

The trade pipeline follows a strict layered guard architecture.
Every layer must **pass** before the trade reaches the next layer.
LIVE accounts use **fail-closed** semantics: when data is missing or a
dependency is unreachable, the trade is **rejected**, not allowed through.

---

## Layer 1 — Global Guards (`src/core/safety.py`)

Runs once per signal, before any per-account work.

```
process_trade(payload)
    │
    │─ [STEP 1] check_env_kill_switch(s)        ← BUG-05 fix: first line, zero I/O
    │─ [STEP 2] run_global_guards(payload, s)
    │              ├── check_size_guard()        ← with diagnostic breakdown
    │              ├── check_max_lot_guard()
    │              └── check_futures_entry_model()
    │                      └── check_flip_timing()  ← BUG-02 fix: fail-closed on LIVE
    │                                               ← BUG-03 fix: missing model → reject
    │─ Symbol Whitelist
    │─ Staleness Guard   (LIVE only)
    │─ Holiday Guard
    │─ Pine Filters      (_validate_pine_filters)
    │─ AI Supervisor     (RF fast-path or full ensemble)
    │
    └── [per-account loop] _execute_for_profile()
```

### Functions in `src/core/safety.py`

| Function | Guard | Fail Mode |
|----------|-------|-----------|
| `check_env_kill_switch(s)` | ENV `TRADING_KILL_SWITCH` | Immediate return — no audit write needed (already logged at startup) |
| `check_size_guard(payload, s, symbol)` | Size ≤ 0 | Fail-closed — diagnostic reason logged |
| `check_max_lot_guard(payload, s)` | Size > `max_lot_size` | Fail-closed |
| `check_flip_timing(payload)` | FLIP on non-5m bar | **Fail-closed on LIVE** (BUG-02 fix) — PAPER: warn-only |
| `check_futures_entry_model(payload)` | Futures without `entry_model` | **Fail-closed on LIVE** (BUG-03 fix) — PAPER: warn-only |
| `run_global_guards(payload, s)` | Orchestrator — runs all above in order | Returns first rejection reason, or `None` if all pass |

> **FAIL-CLOSED POLICY**  
> On LIVE accounts: if `bar_time` is missing for a FLIP entry → **rejected**.  
> On LIVE accounts: if `entry_model` is absent for a Futures symbol → **rejected**.  
> On PAPER/DRY_RUN: both are warn-only and allowed through.

---

## Layer 2 — Per-Account Guards (`src/worker._run_account_guards`)

Runs once **per broker profile** inside `_execute_for_profile`.

```
_run_account_guards(payload, profile, s, equity)
    │
    │─ Redis Kill-Switch  trading:kill_switch:{account_name}
    │       └── BUG-06 fix: Redis down on LIVE → BLOCKED (fail-closed)
    │─ MTM Guardian       (per-account Mark-to-Market loss limit)
    │       └── Redis down on LIVE → BLOCKED
    │─ Circuit Breaker    is_metaapi_circuit_open(account_name)
    │       └── Exception on LIVE → BLOCKED
    │─ Adaptive Daily Limit  (PineGuardian)
    │       └── Exception on LIVE → BLOCKED
    │─ PropGuard          check_safety(equity, balance, daily_pnl)
    │─ Correlation Guard  correlation_manager.check()
    └── Consistency Analyzer  (evaluation mode only)
```

### Fail-Closed Rules (BUG-06)

| Guard | LIVE behaviour when dependency fails |
|-------|--------------------------------------|
| Redis kill-switch | `RedisError` → trade **BLOCKED** |
| MTM Guardian | `Exception` → trade **BLOCKED** |
| Circuit Breaker | `Exception` → trade **BLOCKED** |
| Adaptive Trade Limit | `Exception` → trade **BLOCKED** |

PAPER mode: all of the above log a warning and **allow** through.

---

## Layer 3 — Execution (`src/logic.py`)

Called by `_execute_for_profile` after all guards pass.

```
logic.process_trade(payload, dry_run, ai_result, profile)
    │
    │─ Position sizing   (risk_engine.calculate_position_size_with_spread)
    │─ Broker execution  (adapters/execution/router.get_adapter)
    │─ Supabase write    (save_alert / update_alert_status)
    └── Notifications    (NotificationService → Discord / Telegram)
```

---

## Module Map

```
src/
  core/
    safety.py              ← Global guards (NEW — DEV-98)
    risk_engine.py         ← Position sizing (no I/O)
    guard_rails/
      correlation.py       ← Correlation manager
      prop_guard.py        ← PropGuard / drawdown rules
      staleness_guard.py   ← Signal age + price deviation
      holiday_guard.py     ← Exchange holiday calendar
      pine_guardian.py     ← Adaptive daily trade limit
      circuit_breaker.py   ← MetaAPI circuit breaker
  worker.py                ← Orchestrator (queue loop + guard calls)
  logic.py                 ← Execution engine (broker + DB)
  agents/
    supervisor.py          ← AI Supervisor (RF + LLM ensemble)
  ai/
    trading_council.py     ← 9-stage multi-agent debate (shadow mode)
```

---

## Guard Execution Order in `process_trade`

```
1. check_env_kill_switch     ← first, cheapest, zero I/O
2. run_global_guards
   2a. check_size_guard
   2b. check_max_lot_guard
   2c. check_futures_entry_model
       └── check_flip_timing (if FLIP)
3. symbol_whitelist
4. staleness_guard           ← LIVE only
5. holiday_guard
6. _validate_pine_filters
7. AI Supervisor (RF fast-path or full ensemble)
8. [per-account] _run_account_guards
   8a. Redis kill-switch
   8b. MTM Guardian
   8c. Circuit Breaker
   8d. Adaptive daily limit
   8e. PropGuard
   8f. Correlation
   8g. Consistency
9. _execute_for_profile → logic.process_trade
```

**Every step above returns immediately on rejection** — no subsequent guards run.

---

## Adding a New Guard

1. Add your function to `src/core/safety.py` (if global) or inline in `_run_account_guards` (if per-account).
2. Follow the signature: `def my_guard(payload) -> Optional[str]` — return `None` on pass, rejection string on block.
3. Apply fail-closed: if data is missing on LIVE, **reject**. If PAPER, warn-only.
4. Wire it into `run_global_guards()` (global) or `_run_account_guards()` (per-account).
5. Update this file.
