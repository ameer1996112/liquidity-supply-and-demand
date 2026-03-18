# Concerns & Technical Debt

## Critical Concerns

### 1. Monolithic Worker (`src/worker.py` — 82KB)
- **Impact**: Extremely difficult to maintain, test, or modify safely
- **Risk**: Single file is the heart of trade execution — any bug has financial impact
- **Recommendation**: Break into smaller modules (signal consumer, guard rail pipeline, execution orchestrator, background tasks)

### 2. Large Single Files
- `src/ai/brain.py` (59KB) — AI ensemble decision engine
- `src/adapters/supabase.py` (41KB) — Database adapter
- `src/ai/trading_council.py` (39KB) — Multi-agent debate
- `src/logic.py` (37KB) — Shared business logic
- `src/api.py` (30KB) — Main API file
- `src/adapters/execution/meta_api_adapter.py` (29KB) — MetaAPI adapter
- `frontend/src/lib/supabase.ts` (27KB) — Frontend Supabase client
- `frontend/src/lib/api.ts` (24KB) — Frontend API client
- `frontend/src/app/page.tsx` (23KB) — Dashboard page
- **Impact**: Hard to navigate, review, and safely modify

### 3. Settings Cache (`@lru_cache`)
- Settings are cached forever after first load
- `.env` changes require full process restart
- Risk of stale config in long-running worker process
- Gotcha documented in AGENTS.md

## Architecture Concerns

### 4. Dual Data Access in Frontend
- Frontend accesses data through BOTH `lib/api.ts` (backend API) and `lib/supabase.ts` (direct Supabase)
- No clear boundary on which path to use
- Risk of data consistency issues

### 5. No Dependency Injection
- Services are manually constructed and passed around
- Makes testing harder and couples components
- Worker instantiates all services directly

### 6. Ad-hoc Test Scripts at Root
- 15+ `test_*.py` and `verify_*.py` scripts at project root
- Not part of formal test suite
- Clutters root directory: `test_age.py`, `test_api.py`, `test_api2.py`, `test_brain.py`, `test_db.py`, `test_db2.py`, `test_env_loading.py`, `test_history.py`, `test_rag.py`, `test_staleness_fix.py`, `test_supabase_adapter_live.py`, `test_supabase_keys.py`, `test_sync.py`, `test_sync2.py`, `check_ai.py`, `fix_routes.py`, `fix_routes_v2.py`, `fix_trade55.py`, `verify_auto_detect.py`, `verify_cache.py`

### 7. Legacy Planning Docs at Root
- Multiple markdown files at root level: `POSITIONS_NOT_SHOWING_SUMMARY.md`, `PROJECT_BOARD.md`, `PROP_FIRM_ANALYTICS_FIX_PLAN.md`, `PROP_FIRM_ANALYTICS_FIX_SUMMARY.md`, `QUICK_FIX.md`, `REAL_FIX_FRONTEND_MAPPING.md`, `TODO.md`
- Should be in `docs/` or cleaned up

## Performance Concerns

### 8. Synchronous MetaAPI Calls
- MetaAPI adapter makes HTTP calls synchronously in some paths
- Background sync worker polls MetaAPI accounts on interval
- Previous optimizations: cached balances, cached account names, reduced timeouts
- Still potential for MetaAPI timeout issues (documented in conversation history)

### 9. Worker Polling Loop
- Worker uses BRPOP on Redis (blocking pop) — efficient
- But background tasks (broker reconciliation, account sync) run on timers
- No backpressure mechanism if signal processing falls behind

## Security Concerns

### 10. API Key Management
- API keys stored in `.env` at project root
- `WEBHOOK_SECRET` is optional (not required)
- Supabase service role key gives full database access
- MetaAPI token provides broker access

## Testing Gaps

### 11. Frontend Test Coverage
- Only 2 test files for entire frontend
- 1 pre-existing test failure (`tradingMetrics.test.ts`)
- No integration tests for frontend ↔ backend

### 12. Missing CI/CD
- No visible GitHub Actions or CI configuration
- Tests must be run manually
- No automated deployment pipeline visible

## Lint Status

- **Backend**: Ruff — 98 pre-existing warnings
- **Frontend**: ESLint — pre-existing warnings/errors
- Both are functional but not clean
