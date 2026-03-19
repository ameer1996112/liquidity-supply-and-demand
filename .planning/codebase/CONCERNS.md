# CONCERNS.md — Technical Debt, Known Issues & Fragile Areas

## Tech Debt

### 🔴 Critical: Monolithic Files
- **`src/worker.py` (82KB)** — Entire signal processing pipeline in a single file. Hard to navigate, test, and modify safely. Should be decomposed into a proper pipeline module.
- **`src/api_portfolio_control.py` (83KB)** — Largest file in the codebase. Suggests a missing service/domain layer for portfolio operations.
- **`src/logic.py` (37KB)** — Unclear scope ("logic" is not a useful name). Business logic spread across `logic.py`, `worker.py`, and `core/` without clear boundary.
- **`src/adapters/supabase.py` (41KB)** — All database operations in one file. No repository pattern, no query builder abstraction.

### 🟡 Medium: API Sub-Router Pattern
- ~20 `api_*.py` files all living flat in `src/` instead of a `src/api/` package. As API grows, this becomes unwieldy.
- Two overlapping prop firm router files: `api_prop_firm.py` (8KB) and `api_prop_firm_v1.py` (4KB) suggest a versioning migration that was never cleaned up.

### 🟡 Medium: Hardcoded Values
- Profitable symbols list hardcoded in `src/worker.py` — should be database-driven or configurable
- CORS origins hardcoded in `src/api.py` — should only use `FRONTEND_URL` env var (partially fixed but still fragile)

### 🟡 Medium: Mixed PnL Field Names
- `pnl` vs `pnl_usd` field naming inconsistency across signals/trades — causes mapping confusion in frontend and analytics

### 🟡 Medium: Empty Test File
- `tests/test_pnl_broker_fetch.py` (61 bytes) — stub with no actual tests. PnL broker truth mismatch is a known bug category with zero test coverage.

---

## Known Bugs

### 🔴 PnL Broker Truth Mismatch
- **Description:** Discrepancy between locally tracked PnL and broker-reported PnL for closed positions
- **Status:** Listed as TODO in `TODO.md`
- **Impact:** Analytics may show incorrect P&L; broker reconciliation doesn't perfectly sync

### 🔴 Council Column Empty on Dashboard
- **Description:** The "Council" column appears empty in the main dashboard signal feed
- **Status:** Visual bug — AI Trading Council reasoning not displayed
- **Impact:** Users can't see AI debate rationale inline

### 🟡 tradingMetrics.test.ts Failure
- **Description:** 1 pre-existing test failure in `frontend/src/domain/metrics/tradingMetrics.test.ts`
- **Status:** Documented as baseline in AGENTS.md
- **Impact:** Metric calculation accuracy uncertain

### 🟡 yfinance HTTP 404 Errors
- **Description:** Some symbols (e.g., `GBPJPY`) return HTTP 404 from yfinance
- **Status:** Symbol mapping between TradingView and Yahoo Finance formats incomplete
- **File:** `src/adapters/market_data.py`
- **Impact:** ML Guardian may not evaluate some currency pairs

---

## Security Concerns

### 🔴 Frontend Secret Boundary
- `.env.example` has explicit warnings about never exposing service role key, Redis URL, MetaAPI token to frontend
- Risk: accidental `NEXT_PUBLIC_` prefix on a backend secret would bake it into the browser bundle
- Mitigation: documented in `.env.example`, but no automated check

### 🟡 CORS Configuration
- CORS policy was previously hardcoded, partially fixed to use `FRONTEND_URL`
- Misconfiguration could allow unintended cross-origin access to the API
- **File:** `src/api.py`

### 🟡 Webhook Secret Optional
- `WEBHOOK_SECRET` is optional — if not set, any caller can post signals
- In local dev this is fine; in production with no secret, attacker could inject fake signals

---

## Performance Concerns

### 🟡 AI Guardrail Latency
- AI/LLM calls add significant latency to the signal execution path
- Two-tier model (quick → deep escalation) introduced in Sprint 3.1 to mitigate
- AI timeout: `AI_TIMEOUT_SECONDS=5` — may still block fast market moves
- **Guards fail open** on timeout (intentionally) — latency doesn't block trades

### 🟡 MetaAPI Connection Management
- `meta_api_adapter.py` manages connection lifecycle; intermittent "Read timed out" errors in background reconciliation (fixed with separate timeout settings)
- Background timeout: longer (~60s); Trade execution: shorter (5s fast path)

### 🟡 Supabase Adapter Size
- `src/adapters/supabase.py` (41KB) doing all DB operations in one place creates a bottleneck and makes caching/optimization harder to implement

---

## Fragile Areas

### 🔴 API Fail-Fast on Startup
- API checks Redis on startup and refuses to start if unavailable
- **Risk:** Redis downtime prevents API deployment/restart
- **Mitigation:** healthcheck passes only when Redis is up; can cause Railway restarts

### 🟡 `@lru_cache` on Settings
- `config/settings.py` caches settings at module load time
- **Risk:** Changing `.env` values has no effect until process restart
- **Pitfall:** Developers often change env vars and expect immediate effect

### 🟡 Worker "Fail-Open" Guards
- AI/ML guards are explicitly designed to fail open to prevent blocking trades
- **Risk:** If all guards fail simultaneously (e.g., API outage), trades execute with zero filtering
- Trade-off: liveness over correctness in error states

### 🟡 `RUN_MODE` Resolution
- `run_mode` field has known versioning/resolution fragility from TradingView strategy updates
- Workaround in place but brittle to strategy changes

### 🟡 Account Sync Feature Flags
- Several account-related features disabled via flags:
  ```
  ACCOUNT_SYNC_ENABLED=false
  ACCOUNT_RECONCILIATION_ENABLED=false
  ACCOUNT_JOURNAL_ENABLED=false
  METAAPI_POSITIONS_FETCH_ENABLED=false
  ```
- Partially implemented features with feature flags can create confusing half-states

---

## Makefile Warning

The `Makefile` references `docker-compose.test.yml` which **does not exist** in the repo.  
Running `make test` (or similar) may fail. Use local Redis + pytest directly instead.
