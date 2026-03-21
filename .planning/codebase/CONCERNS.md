# CONCERNS.md — Technical Debt & Areas of Concern

## High Priority

### 1. Settings Cache — Restart Required for Config Changes
**File:** `config/settings.py`  
**Issue:** `@lru_cache` on `get_settings()` means any change to `.env` or Railway env vars requires a **full process restart** to take effect. No runtime reload.  
**Risk:** Operators may change env vars on Railway expecting immediate effect — changes appear silent.  
**Mitigation:** `AGENTS.md` documents this; `src/core/dynamic_config.py` provides a partial workaround for some rules.

### 2. Worker Complexity — Single 600+ Line File
**File:** `src/worker.py`  
**Issue:** The worker is monolithic — global guards, per-account loop, executor, observer wiring, all in one file. Hard to unit test individual stages.  
**Risk:** Adding new guard types or modifying execution flow requires deep understanding of the full file.  
**Affected phases:** Any work touching worker pipeline.

### 3. AI Filter Conditional Complexity
**Files:** `src/ai/brain.py`, `src/worker.py`  
**Issue:** `AI_FILTER_ENABLED`, `AI_SHADOW_MODE`, `ML_GUARDIAN_ENABLED`, `TRINITY_ENABLED` — 4 separate boolean flags that interact in non-obvious ways. Shadow mode vs disabled vs full on.  
**Risk:** Misconfiguration can silently disable filters or block all signals.

### 4. MetaAPI Adapter — External Dependency
**File:** `src/adapters/metaapi.py`  
**Issue:** MetaAPI is the single point of failure for trade execution. If MetaAPI is down, all live trades fail. No fallback except paper trading.  
**Risk:** Production outages not caught until a signal is actually ready to execute.

### 5. Supabase HTTP/2 Connection Staling
**File:** `src/adapters/supabase_api.py`  
**Issue:** API adapter recreates Supabase client every 90s to avoid `ConnectionTerminated` errors. This is a workaround for a fundamental HTTP/2 keep-alive issue.  
**Risk:** Brief windows where DB calls may fail during recreation (mitigated by timing).

## Medium Priority

### 6. Env Var Sprawl
**File:** `.env.example`  
**Issue:** 50+ environment variables, many with aliases (`SUPABASE_KEY` / `SUPABASE_ANON_KEY`). The alias resolution in `pydantic-settings` `AliasChoices` can be confusing. Some vars are "redundant" per the .env.example docs.  
**Risk:** Wrong env vars set, settings silently use defaults.

### 7. Makefile References Non-Existent docker-compose.test.yml
**File:** `Makefile`  
**Issue:** `docker-compose.test.yml` does not exist. Tests must use local Redis.  
**Risk:** CI setup may fail if relying on Makefile.

### 8. No Rate Limiting on All Endpoints
**File:** `src/api.py`  
**Issue:** Rate limiting (slowapi) is applied to `/webhook` but not all analytics/risk endpoints. With Supabase queries, repeated polling could cause rate limits on the Supabase side.  
**Risk:** DDoS-style DoS against analytics endpoints.

### 9. Trailing Stop & Breakeven Services — Limited Tests
**Files:** `src/services/trailing_stop_manager.py`, `src/services/breakeven_manager.py`  
**Issue:** These services manage live position modifications but have limited dedicated test coverage.  
**Risk:** Silent bugs in trailing stop logic could cause incorrect SL moves.

### 10. Correlation Guard State
**File:** `src/core/guard_rails/correlation.py`  
**Issue:** Correlation guard maintains in-memory state via `create_correlation_manager_from_settings()`. State is lost on worker restart.  
**Risk:** After restart, correlation limits reset — a burst of correlated positions could be taken before the guard rebuilds context.

## Low Priority / Frontend

### 11. Pre-existing ESLint Warnings
**Directory:** `frontend/`  
**Issue:** `npx eslint` has pre-existing warnings/errors. These don't block builds but indicate style debt.

### 12. One Pre-existing Vitest Failure
**File:** `frontend/src/lib/tradingMetrics.test.ts`  
**Issue:** 1 test fails in the frontend test suite. Not a regression but indicates unresolved test debt.

### 13. `NEXT_PUBLIC_*` Secret Boundary
**Files:** `frontend/.env`, `frontend/next.config.*`  
**Issue:** Multiple explicit warnings in `.env.example` about not exposing backend secrets to frontend. Must remain vigilant when adding new env vars — any `NEXT_PUBLIC_` var is embedded in client JS at build time.

## When Adding New Features — Watch Out For

1. **Always restart services after .env changes** (settings cache)
2. **Always set `PYTHONPATH=/workspace`** when running backend outside `start.sh`
3. **Never commit `.env`** with real credentials — `.env.example` only
4. **Guard rails must fail-open** (return `True` / allow) on infrastructure errors — don't block trades due to DB unavailability
5. **New API routers** must be mounted in `src/api.py` with `app.include_router()`
6. **Test transport** uses `SIGNAL_TRANSPORT=memory` — don't assume Redis in tests
