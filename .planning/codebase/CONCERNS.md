# CONCERNS.md — Technical Debt, Known Issues & Areas of Concern

## Critical / High Priority

### 1. God Files (Size & Complexity)
Several files have grown extremely large and are potential maintenance risks:
- `src/worker.py` — **85KB** — the entire pipeline orchestration is in one file; hard to test in isolation
- `src/api_portfolio_control.py` — **83KB** — largest file, monolithic portfolio control logic
- `src/ai/brain.py` — **59KB** — AI ensemble logic densely packed
- `src/adapters/supabase.py` — **41KB** — all DB operations in one class
- `src/logic.py` — **41KB** — unclear ownership; large utility dumping ground

**Risk**: Changes to these files risk unintended side effects. Adding features requires navigating massive files.

### 2. Missing CI Infrastructure
- `Makefile` references `docker-compose.test.yml` which **does not exist** in the repo
- No automated CI pipeline (no GitHub Actions workflows visible)
- Tests must be run locally with `redis-server --daemonize yes` beforehand
- **Risk**: No automated gate prevents broken tests from being merged

### 3. Redis Fail-Fast Without Graceful Degradation
- API startup **fails hard** if Redis is not reachable
- No fallback for offline-mode or reconnect logic
- Worker uses blocking `BLPOP` — a Redis restart kills the worker silently
- **Risk**: Service unavailability if Redis restarts (common in cloud environments)

### 4. Settings Cache Gotcha
- `get_settings()` uses `@lru_cache` — env var changes require process restarts
- No way to hot-reload config without restarting all services
- **Risk**: Operations team confusion when `.env` edits don't take effect

## Medium Priority

### 5. Incomplete Test Coverage
- 22 test files but many services are not directly unit-tested
- `test_pnl_broker_fetch.py` is trivially small (61 bytes — effectively empty)
- No tests for `src/adapters/discord.py` (27KB, complex notification logic)
- No tests for trailing stop / breakeven managers
- Frontend: 1 pre-existing failure in `tradingMetrics.test.ts` (unresolved)
- **Risk**: Regressions in critical paths go undetected

### 6. Multiple AI Pipeline Layers with Overlapping Concerns
- `AI Guardian` + `ML Guardian` + `Trading Council` + `EnsembleBrain` — unclear when each is active
- `AI_FILTER_ENABLED`, `ML_GUARDIAN_ENABLED`, `TRINITY_ENABLED`, `AI_ENABLED`, `ai_shadow_mode`, `run_shadow_mode` — too many overlapping boolean flags
- Shadow mode semantics differ between flags (`AI_SHADOW_MODE` vs `run_shadow_mode` vs `AI_MODE=shadow`)
- **Risk**: Misconfiguration silently disables guardrails

### 7. Duplicate/Legacy API Modules
- `src/api_prop_firm.py` and `src/api_prop_firm_v1.py` coexist — unclear which is canonical
- Jira integration split across `src/api_tickets.py` (backend proxy) and `jira/` (standalone Next.js app)
- **Risk**: Maintenance burden, confusion about which code is active

### 8. MetaAPI Rate Limiting / Excessive Polling
- `get_account_info` and `get_open_positions` called excessively (documented in recent bug work)
- Caching added in `src/services/redis_cache.py` but `account_cache_ttl_seconds=30s` default may still be too frequent
- Background sync worker polls on `account_sync_interval_seconds=60s`
- **Risk**: MetaAPI rate limit violations, extra latency costs

### 9. Inconsistent Async Patterns
- Mix of `async def`, synchronous threading, and APScheduler scheduled jobs
- `ASYNC_NOTIFICATIONS=False` by default — Discord/Telegram block signal pipeline
- `ASYNC_TRADING_COUNCIL=False` by default — Council blocks pipeline too
- **Risk**: Signal execution latency spikes when notifications are slow

### 10. LLM Cost / Latency Without Hard Budgets
- `AI_TIMEOUT_SECONDS=5.0` default — but Trading Council debate has no timeout
- No token budget enforcement per request
- Two-tier model (quick/deep) helps but escalation logic may hit deep model too frequently
- **Risk**: High LLM costs, latency spikes on debate calls

## Low Priority / Maintenance Debt

### 11. Migration File Gaps
- 57+ SQL migrations with some numbers skipped (jump from 050 → 057)
- No rollback scripts for any migration
- Migration runner (`RUN_MIGRATIONS.md`) is manual
- **Risk**: Schema drift between environments

### 12. Scattered Scripts Directory
- `scripts/` has 15+ one-off scripts (`fix_corrupted_dd.py`, `cleanup_stale_positions.py`, etc.)
- No clear distinction between "run once ever", "run periodically" and "emergency tooling"
- **Risk**: Accidental re-run of destructive scripts

### 13. Pine Script Coupling
- Backend has `pine_min_score`, `pine_min_grade`, `pine_min_departure_strength` Balanceprofile hardcoded to match Pine
- Any Pine Script update requires corresponding backend config update
- `pine_guardian.py` (26KB) mirrors Pine Script logic in Python — dual maintenance burden
- **Risk**: Config drift between strategy and backend filter

### 14. Frontend State Management
- No global state manager (Zustand/Redux) — relies on React Query + prop drilling
- Dashboard `page.tsx` at 25KB is likely a god component
- **Risk**: Difficult to share state between pages without prop drilling

### 15. Multi-Account Complexity
- `BROKER_PROFILES_JSON` is a raw JSON string in env var — error-prone to configure
- Account routing adds significant complexity to the worker pipeline
- **Risk**: Misconfiguration causes trades to go to wrong account

## Security Considerations

### 16. Webhook Authentication Optional
- `WEBHOOK_SECRET` is optional (`default=""`) — if not set, anyone can post signals
- No IP allowlist for webhook endpoint
- **Risk**: Unauthorized signals if secret is not configured in production

### 17. Service Role Key Exposure
- `SUPABASE_SERVICE_ROLE_KEY` bypasses Row Level Security
- Used in Python backend — never expose to frontend
- **Risk**: If env file is committed or leaked, full DB access bypassed

### 18. `.env` Not in .gitignore (Verify)
- `.env` exists at repo root with real credentials
- `.gitignore` should exclude it — verify this is correctly enforced
- **Risk**: Credential leak if accidentally committed

## Performance Hot Spots

### 19. Supabase Adapter (41KB)
- All DB reads go through one adapter class; no connection pooling visible
- Supabase Python SDK is synchronous — blocking async event loop
- **Risk**: DB queries block the FastAPI event loop under load

### 20. Signal Pipeline Latency Budget
- Each guard rail adds synchronous processing time
- TCA threshold for total latency is 30s (`TCA_LATENCY_THRESHOLD_MS=30000`)
- Bot processing threshold is 10s — guard rails must complete in <10s combined
- **Risk**: Slow LLM calls push execution past TCA alert thresholds
