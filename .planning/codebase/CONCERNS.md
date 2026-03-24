# CONCERNS.md — Technical Debt & Known Issues

## Critical / High Risk

### 1. Massive File Sizes — god files
Several files are dangerously large and hard to maintain:

| File | Size | Concern |
|------|------|---------|
| `src/worker.py` | 87KB | Entire worker logic — god object |
| `src/ai/brain.py` | 59KB | All AI orchestration in one file |
| `src/api_portfolio_control.py` | 83KB | Should be split by domain |
| `src/ai/trading_council.py` | 38KB | Could be split by agent role |
| `src/adapters/supabase.py` | 41KB | All DB operations in one file |
| `src/api_tickets.py` | 39KB | Jira proxy + local DB layer mixed |
| `src/api.py` | 37KB | Router registration + inline logic |

**Impact**: High merge conflict risk, hard to unit test individual behaviors, long LLM context windows needed for modifications.

---

### 2. Settings Cache (`@lru_cache`) — Silent Failures
`config/settings.py::get_settings()` is cached via `@lru_cache`. Changes to `.env` require full process restart. This is documented in `AGENTS.md` but is a gotcha that causes silent dev confusion.

**Risk**: Dev mismatches, stale config in long-running workers.

---

### 3. Missing Makefile Target
`Makefile` references `docker-compose.test.yml` which does not exist. Docker-based test runs silently fail.

**Workaround**: Use local Redis directly. Documented in AGENTS.md.

---

### 4. `test_pnl_broker_fetch.py` — Empty Test File
Only 61 bytes. Broker PnL fetching has no automated test coverage.

---

### 5. Frontend Pre-existing Test Failure
`tradingMetrics.test.ts` has 1 persistent failure. Known but unresolved.

---

## Medium Risk

### 6. Pine Script Logic Duplication
`src/core/guard_rails/pine_guardian.py` (43KB) mirrors Pine Script rules from `SND_Strategy.pine`. Two implementations must be kept in sync manually. Any Pine Script update requires a corresponding Python update.

**Risk**: Divergence between Pine and Python guard rail logic leads to unexpected trade rejections or approvals.

---

### 7. MetaAPI Polling Frequency — Recently Fixed
`get_account_info` and `get_open_positions` were previously polled excessively. Redis TTL caching (30s) was added to fix this. But the underlying polling architecture is fragile — tight coupling between sync intervals and MetaAPI rate limits.

---

### 8. AI/ML Guardian in Shadow Mode by Default
`AI_MODE=shadow` means LLM never blocks a trade. ML guardian defaults to `ML_WARNING_ONLY_MODE=true`. The system can degrade to "no AI filtering" without any observable error — just warning logs.

**Risk**: Invisible quality gate degradation.

---

### 9. Supabase Adapter Coupling
`src/adapters/supabase.py` (41KB) is a massive module-level singleton. Many services import it directly:
```python
from src.adapters.supabase import supabase
```
This tightly couples all service code to Supabase and makes unit testing hard without full supabase mock setup.

---

### 10. Strategy Config Validation at Startup
`validate_active_strategies_startup()` runs during API startup and can crash the API. This is intentional fail-fast behavior, but any bad data in the `strategy_configs` table will take down the API.

---

### 11. Ruff Pre-existing Warnings
98 pre-existing ruff warnings in `src/`, `config/`, `tests/`. No CI enforcement prevents this number from growing.

---

## Low Risk / Housekeeping

### 12. `venv/` Committed to Repo Structure
A `venv/` directory exists at project root alongside `.venv` at `/workspace/.venv`. This may cause confusion about which Python environment to use.

### 13. Discord Adapter Complexity
`src/adapters/discord.py` (27KB) contains complex embed formatting. The `'sl'` KeyError bug (Discord error on LATE FILL events) was recently fixed but discord formatting remains fragile for edge case trade data shapes.

### 14. Multi-Account Complexity
`BROKER_PROFILES_JSON` supports multiple broker accounts. Account routing logic in `src/core/account_router.py` and `src/services/account_orchestrator.py` (28KB) adds significant complexity to the worker pipeline. Edge cases in multi-account routing may exist.

### 15. `api_prop_firm.py` + `api_prop_firm_v1.py` — Split Versioning
Two prop firm API files exist. The v1 file suggests a prior version was not removed. May cause confusion about which endpoints are canonical.

### 16. Frontend Build Issues
`cd frontend && npm run build` should be run to verify no TypeScript or build errors before deploys. Pre-existing ESLint warnings (`cd frontend && npx eslint`) exist.

### 17. `plans/` Directory (Legacy)
`plans/` contains legacy planning docs outside the GSD `.planning/` system. May contain outdated information.

### 18. `data/` and `ml/` Directories
`data/` and `ml/` contain files gitignored by default (datasets, model artifacts). ML model training is done offline — no automated retraining pipeline is present in the codebase.

---

## Security Observations

### Webhook Secret Optional
`WEBHOOK_SECRET` is optional — if not set, the `/webhook` endpoint accepts any payload. This is fine for local dev but must be set in production.

### CORS Configuration
Production CORS allows `https://.*\.up\.railway\.app` by regex. If Railway subdomain naming is predictable, this could allow unexpected origins. Consider explicit origin allowlist in production.

### Supabase Service Role Key in Backend
`SUPABASE_SERVICE_ROLE_KEY` grants full bypass of RLS. Used correctly (server-side only) but must not leak to frontend.
