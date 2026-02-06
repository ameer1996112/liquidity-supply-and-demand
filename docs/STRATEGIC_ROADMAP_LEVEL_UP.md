# Strategic Roadmap: From MVP to Professional Hedge Fund Infrastructure

This document is a **Level Up Proposal** based on a codebase audit of the trading bot. It categorizes upgrades into three pillars and three concrete "Upgrade Packages" with file-level changes and complexity estimates.

---

## Phase 1: Discovery Summary

### Current Architecture (Actual Paths)

| Role | Location | Notes |
|------|----------|--------|
| **Entry & API** | `src/api.py` | FastAPI app, webhook validation, Redis push, CORS, routers |
| **Core loop** | `src/worker.py` | BLPOP consumer, guards (kill-switch, idempotency, risk, correlation, ML), then `logic.process_trade` |
| **Execution engine** | `src/logic.py` | Save to Supabase, Discord/Telegram, paper/live adapter routing, exit handling |
| **Broker (LIVE)** | `src/adapters/execution/meta_api_adapter.py` | MetaApi REST (orders, positions, history) |
| **Watchdog** | `src/services/watchdog.py` | Polls Supabase + MetaApi to detect silent exits, syncs PnL |
| **Schema** | `scripts/sql/supabase_schema.sql` | `trading_signals` and related tables |
| **Signal ingress** | `src/api.py` (webhook routes) | Validate → push to Redis; no DB or execution in API |

### Strengths

- Clear separation: API (validate + queue) vs Worker (consume + guards + logic).
- DDD-style layout: `core/`, `adapters/`, `ai/`, `services/`.
- Kill switch (Redis + env), idempotency by `trade_key`, risk/correlation/ML guards.
- Run mode (LIVE/PAPER/DRY_RUN) and execution router already in place for one account.

---

## Pillar 1: Architecture & Scalability — "Funded Fleet" Upgrade

### Current Limitation

- One config (env): one MetaApi account, one `ACCOUNT_BALANCE`, one risk profile.
- Signal is tied to a single execution path; no notion of "one signal → N accounts with different risk."

### Target: Multi-Account Support

1. **Decouple signal from execution**
   - Keep webhook → one canonical "signal" (e.g. in a `signals` or `trade_events` table or still Redis).
   - Introduce an **Execution Plan**: for each signal, determine *which accounts* to run (e.g. Funded, Eval, Personal) and with what risk settings (lot size, risk %, max positions).

2. **Database**
   - **Option A:** Add `broker_account_id` (or `account_profile_id`) to `trading_signals` and allow multiple rows per logical signal (one per account).
   - **Option B:** New table `signal_executions(signal_id, account_id, status, broker_order_id, ...)` and keep `trading_signals` as one row per logical signal.
   - Add an **accounts** (or **broker_profiles**) table: id, name, meta_api_account_id, meta_api_token (or ref to vault), risk_pct, max_positions, run_mode (LIVE/PAPER), is_active.

3. **Logic / Worker**
   - After guards pass for the *signal*, worker:
     - Looks up active accounts that should receive this signal (e.g. by run_mode or tag).
     - For each account: resolve risk (size, max position), call execution adapter for that account, write result to DB (per-account row or `signal_executions`).
   - `logic.process_trade` becomes "process this signal for this account" or is called N times per signal (once per account).

4. **Execution adapters**
   - `get_adapter(run_mode, settings)` today; extend to `get_adapter(account_id)` or `get_adapter(account_profile)` that carries token, account_id, and risk settings. MetaApi adapter already takes (token, account_id); factory just needs to supply per-account credentials.

### Files to Touch (Pillar 1)

| File / Area | Change | Complexity |
|-------------|--------|------------|
| `scripts/sql/` (new migration) | Add `broker_profiles` or `signal_executions` (and maybe extend `trading_signals`) | Medium |
| `config/settings.py` | Optional: list of account profiles from env or DB | Low–Medium |
| `src/logic.py` | Loop over accounts; per-account save/execute; optional fan-out from one signal | High |
| `src/worker.py` | After guards: resolve account list; call logic per account or pass account into logic | Medium |
| `src/adapters/execution/router.py` | Factory by account_id / profile instead of only run_mode | Medium |
| `src/adapters/supabase.py` | Save/update by account; idempotency per (trade_key, account_id) if needed | Medium |
| `src/services/watchdog.py` | Iterate over LIVE accounts; one MetaApi client per account | Medium |

---

## Pillar 2: Reliability & Safety — Bulletproof Code

### Potential Failure Points

1. **Worker**
   - **Redis disconnect:** BLPOP blocks; if Redis dies, worker may hang or crash. No automatic reconnection loop around the main loop.
   - **Supabase/DB down:** `_exists_trade_key`, `save_alert`, `update_alert_exit` can fail; some paths may not retry or dead-letter consistently.
   - **Full crash mid-trade:** No distributed lock per `trade_key`; two workers could theoretically process the same key if idempotency check and insert are not atomic (e.g. unique constraint on `trade_key` + insert-or-ignore).

2. **Watchdog**
   - **MetaApi rate limits:** No backoff or rate limiting; burst of requests could hit 429.
   - **Connection drops:** No retry with backoff on HTTP calls; single failure skips that sync cycle.
   - **No circuit breaker:** Repeated MetaApi failures don’t temporarily disable the watchdog or back off.

3. **MetaApi adapter**
   - **Timeouts:** Uses fixed timeouts (e.g. 5–10s); no retry on timeout.
   - **429 / 5xx:** Not explicitly handled; no exponential backoff or "pause trading" for this account.

### Recommendations

1. **Circuit breakers**
   - **Kill switch** (already present): Keep; ensure all execution paths respect Redis + env.
   - **Per-account or global "pause"**: After N consecutive MetaApi failures (or 429), set a Redis key (e.g. `trading:circuit_breaker:metaapi`) and skip LIVE execution until TTL or manual reset; worker and watchdog check before calling MetaApi.

2. **Worker resilience**
   - Wrap the main BLPOP loop in a try/except; on Redis connection error, log and sleep(5) then reconnect.
   - Ensure one process per queue (or use Redis lock so only one consumer runs) to avoid duplicate processing.
   - Consider unique constraint on `trade_key` in DB and "insert or ignore" so idempotency is enforced at DB level.

3. **Watchdog**
   - Add retries with exponential backoff for MetaApi GETs.
   - On repeated failures (e.g. 5 in a row), log and increase interval or set circuit breaker.
   - Optional: cap number of "silent exit" resolutions per run to avoid burst of API calls.

4. **MetaApi adapter**
   - Retry once or twice on timeout/5xx with short backoff.
   - On 429: back off (e.g. 60s) and optionally set circuit breaker for that account.

### Files to Touch (Pillar 2)

| File / Area | Change | Complexity |
|-------------|--------|------------|
| `src/worker.py` | Reconnect loop around BLPOP; optional Redis lock for single consumer | Medium |
| `src/adapters/redis_queue.py` | Optional: health check / reconnect helper | Low |
| `src/services/watchdog.py` | Retry + backoff for HTTP; circuit breaker check; optional rate limit | Medium |
| `src/adapters/execution/meta_api_adapter.py` | Retry on timeout/5xx; 429 handling + circuit breaker | Medium |
| `scripts/sql/` (migration) | Unique constraint on `trading_signals.trade_key` if not present | Low |
| New: `src/core/circuit_breaker.py` or in config | Check/set Redis key for MetaApi/account pause | Low–Medium |

---

## Pillar 3: Data & Alpha — Next-Level Intelligence

### Backtesting Engine

- **Idea:** Use existing `trading_signals` (and optional `run_mode='BACKTEST'`, `run_id`) to replay historical signals with configurable risk/sizing and compute equity curve, drawdown, win rate.
- **Approach:**
  - **Option A (in-process):** In `src/services/backtest_engine.py` (or new module), load signals from DB filtered by `run_mode='BACKTEST'` and `run_id`; for each signal, apply sizing (e.g. fixed lot or % risk), apply simple fill model (e.g. entry = signal entry, exit = TP/SL or close_price); aggregate PnL and metrics.
  - **Option B (reuse worker path):** Replay payloads through the same pipeline with a "backtest" execution adapter that only records virtual fills and updates a backtest ledger (e.g. same table with `run_mode='BACKTEST'`). Heavier but consistent with live path.
- **Data:** Already have `trading_signals` with entry, sl, tp, size, close_price, pnl_usd, etc. Backtest can read closed signals or dedicated backtest runs.

### AI Brain & RAG

- **Logging the "why":** For each decision (e.g. ML reject, risk reject), log to a table or structured log: signal_id, guard name, inputs (features, risk_usd), output (pass/reject), and optional free-text reason. That supports future fine-tuning and auditing.
- **RAG:** If `rag_engine` is used for context (e.g. news, rules), ensure queries and retrieved snippets are logged (e.g. prompt hash, top-k doc ids, decision). Helps tune retrieval and prompts.

### Files to Touch (Pillar 3)

| File / Area | Change | Complexity |
|-------------|--------|------------|
| `src/services/backtest_engine.py` | Extend or add: load signals by run_id, apply sizing/fill model, compute stats and equity curve | Medium–High |
| `src/ai/brain.py` | Log prediction + key inputs (e.g. to `trade_events` or `guard_decisions` table) | Low |
| `src/core/guard_rails/*` | Log guard name, input summary, result (pass/reject) for each check | Low–Medium |
| New table / migration | Optional: `guard_decisions(signal_id, guard, result, reason, created_at)` | Low |
| `src/ai/rag_engine.py` (if used) | Log query and top-k references for audits | Low |

---

## Deliverable: Three Upgrade Packages

### Package A: Multi-Account Support ("Funded Fleet")

- **Goal:** One signal can trigger multiple broker accounts with different risk settings.
- **Files:** New migration (accounts + optional signal_executions), `config/settings.py`, `src/logic.py`, `src/worker.py`, `src/adapters/execution/router.py`, `src/adapters/supabase.py`, `src/services/watchdog.py`.
- **Complexity:** **High** (design of account model, idempotency per account, testing with multiple profiles).

### Package B: Safety Core (Circuit Breakers & Resilience)

- **Goal:** Robustness to Redis/DB/MetaApi failures; no duplicate processing; backoff and circuit breakers for MetaApi.
- **Files:** `src/worker.py`, `src/adapters/redis_queue.py`, `src/services/watchdog.py`, `src/adapters/execution/meta_api_adapter.py`, optional `src/core/circuit_breaker.py`, migration for `trade_key` uniqueness.
- **Complexity:** **Medium** (well-scoped retries and one Redis key for circuit breaker).

### Package C: Analytics & Alpha (Backtest + Decision Logging)

- **Goal:** Backtest engine on existing signals; structured logging of guard/AI decisions for tuning and audit.
- **Files:** `src/services/backtest_engine.py`, `src/ai/brain.py`, `src/core/guard_rails/*`, optional new table and `rag_engine`.
- **Complexity:** **Medium** (backtest) + **Low** (decision logging).

---

## Suggested Order

1. **Package B** first: improves reliability without changing the execution model.
2. **Package C** next: adds analytics and audit trail with minimal risk to live execution.
3. **Package A** last: largest architectural change; do after the system is stable and observable.

---

## Summary Table

| Package | Focus | Key files | Complexity |
|---------|--------|-----------|------------|
| **A** | Multi-account (Funded Fleet) | logic, worker, router, supabase, watchdog, migrations | High |
| **B** | Safety (circuit breakers, retries, idempotency) | worker, redis_queue, watchdog, meta_api_adapter, circuit_breaker, migrations | Medium |
| **C** | Backtest + decision logging | backtest_engine, brain, guard_rails, optional guard_decisions table | Medium + Low |

This roadmap should be enough to prioritize and scope each upgrade package and to align implementation with a path from "Functional MVP" to "Professional Hedge Fund Infrastructure."
