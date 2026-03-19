# Concerns

## Critical / High Risk

### 1. DB Status Case Inconsistency (recurring pattern)
`logic.py` writes uppercase `"CLOSED"`, `"OPEN"` etc. to Supabase, but multiple files historically queried lowercase `"closed"`. This was a critical bug (BUG-006) that disabled circuit breakers for an extended period — **the fix exists but the pattern is fragile and could re-emerge in new code.**

- **Risk:** Any new query using `.eq("status", "closed")` will silently return 0 rows
- **Files to watch:** Any new `api_*.py` that queries trade status
- **Mitigation:** Always use `.in_("status", ["CLOSED", "closed"])` or add a DB-level constraint

### 2. TradingView ↔ Backend Account Size Mismatch
TradingView Pine Script uses `initial_capital = $10M` for backtesting but the live account is `$50k`. This causes Pine to send 200× oversized lot sizes.

- **Risk:** Position sizing disasters if `MAX_LOT_SIZE` guard in `worker.py` is ever removed
- **Current mitigation:** `MAX_LOT_SIZE` cap at 10 lots + sector guard (40% limit)
- **Proper fix:** Update Pine's `account_size_usd` input to match live balance

### 3. Balance Cache TTL in Hot Path
`logic.py` caches broker balance for 30 seconds (`_BALANCE_CACHE_TTL = 30`). During high-frequency signal periods, position sizing uses stale balance.

- **Risk:** Incorrect lot size calculations during rapid sequential signals
- **Location:** `src/logic.py` — `_balance_cache`

### 4. MetaAPI Token Misconfiguration Risk
`meta_api_token_env_key` in DB should contain the **name** of the env var (e.g., `META_API_TOKEN`), not the JWT token itself. This is non-obvious and could cause silent auth failures.

- **Risk:** Broker connection failures if misconfigured
- **Documentation:** Only in memory/comments, not in code guards

## Medium Risk / Tech Debt

### 5. Incomplete Position Optimizer
`src/services/position_optimizer.py` has two `TODO` stubs:
- Line 238: `# TODO: Implement quadratic programming optimization`
- Line 262: `# TODO: Implement rebalancing logic`

The optimizer uses simplified heuristics instead of proper portfolio optimization.

### 6. Max Drawdown Not Calculated
`src/services/account_orchestrator.py:298`: `max_drawdown_pct = 0.0  # TODO: Calculate from equity curve`

This means max drawdown is always reported as 0% in account summary — a significant gap for a prop firm trading bot.

### 7. Daily Reset Scheduler: Single-Account Assumption
`src/services/daily_reset_scheduler.py:63`: `# TODO: If multi-account, fetch from broker_profiles table`

The daily reset logic has a hardcoded single-account assumption that will break silently in multi-account setups.

### 8. Frontend Test Coverage Gap
Only one frontend test file confirmed (`SignalInspector.test.tsx`). The entire React application (~40+ components, ~25 hooks) has minimal test coverage.

### 9. Sprint-Driven Test Naming
Tests are named `test_sprint<N>_*` (e.g., `test_sprint23_api_filters.py`, `test_sprint55_reliability.py`), indicating tests were written to cover sprints rather than as persistent regression protection. Tests may become misleading over time as code evolves.

### 10. Duplicate Migration Files
`migrations/` contains duplicate/variant filenames:
- `026_add_missing_jpy_pairs.sql`
- `026_clean_state_model.sql`
- `026_clean_state_model_safe.sql`

Three files with the same prefix suggests migration management is not strictly controlled. Risk of running migrations out of order or skipping one.

## Performance Concerns

### 11. ThreadPoolExecutor Per-Signal
`worker.py` creates a new `ThreadPoolExecutor` per signal for parallel account execution. Under high signal volume, this could exhaust thread pools.

### 12. Supabase HTTP on Every DB Call
No connection pooling visible — each Supabase operation creates HTTP calls. Under high signal frequency, latency accumulates.

### 13. AI Ensemble on Hot Path
RF prediction + RAG retrieval + LLM debate council runs synchronously per signal. The LLM debate (OpenAI API call) is the dominant latency contributor (~seconds).

## Security Concerns

### 14. Hardcoded CORS Origins
`src/api.py` hardcodes `https://frontend-production-a7cf.up.railway.app` as a CORS origin. Any frontend URL change requires code change.

### 15. Webhook Authentication
Webhook endpoint validation relies on `src/core/signal.py` validation. No webhook secret/HMAC verification visible for TradingView webhooks — any source could POST to `/webhook`.

## Known Historical Bugs (Fixed, But Fragile Areas)

- **PnL mismatch** (`logic.py`): TradingView simulated PnL was being stored instead of broker actual PnL. Fixed but requires broker deal fetch after close.
- **Stale positions**: Positions closed on broker but open in DB. Auto-cleanup endpoint exists but relies on MetaAPI reconciliation.
- **JPY pair pip value**: NZDJPY was 94× undersized due to missing dynamic pip calculation. Fixed in `risk_engine.py` but other exotic pairs may still be missing.
- **XAUUSD instrument type ordering**: Metals were misclassified as forex due to `if "USD" in symbol` check order. Fixed but similar ordering bugs could appear for new instruments.
