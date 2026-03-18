# Codebase Concerns

**Analysis Date:** 2026-03-18

## Tech Debt

**Silent Exception Handling Patterns:**
- Issue: Widespread bare `except Exception` clauses that log but don't propagate. Examples: services like `trailing_stop_manager.py`, `breakeven_manager.py`, `prop_firm_tracker.py` swallow exceptions silently.
- Files: `src/services/trailing_stop_manager.py:293-294`, `src/services/trailing_stop_manager.py:402-403`, `src/services/breakeven_manager.py:183-184`, `src/services/alert_engine.py:268-269`, `src/services/prop_firm_tracker.py:78,126,183,202,261,290,314`
- Impact: Failed operations (position cleanup, margin checks, alert creation) silently fail without alerting operator, causing stale data and silent losses
- Fix approach: Replace bare `except Exception` with specific exception types, log at ERROR level with context, optionally create board tickets for critical failures

**Unimplemented TODO Logic:**
- Issue: Core business logic marked TODO but shipped to production
- Files:
  - `src/services/prop_firm_tracker.py:255` - "trades_today" always 0, not calculated from database
  - `src/services/account_orchestrator.py:298` - max_drawdown always 0, not calculated from equity curve
  - `src/services/position_optimizer.py:239` - quadratic programming optimization stubbed out
  - `src/services/position_optimizer.py:263` - rebalancing logic commented as TODO
  - `src/api_portfolio.py:137` - live equity hardcoded to settings instead of fetched
- Impact: Prop firm metrics incorrect, portfolio analysis incomplete, position sizing suboptimal
- Fix approach: Implement missing calculations or remove from API responses with explicit "Not yet implemented" messages

**Global Mutable State (Balance Cache):**
- Issue: `src/logic.py:39-66` uses global `_balance_cache` dict without locking in multi-threaded worker environment
- Files: `src/logic.py:39-66`
- Impact: Race condition in concurrent trade execution — ThreadPoolExecutor processes multiple accounts simultaneously, all updating shared cache
- Fix approach: Replace with account-keyed cache dict + thread-safe access, or use Redis for distributed cache

**Type Coercion Without Validation:**
- Issue: Unsafe float/int casts on user inputs without bounds checking
- Files: `src/worker.py:218,221-222,308-316`, `src/logic.py:89-96`, throughout risk_engine calculations
- Impact: Unconstrained floats could cause: negative position sizes, 0-division in R:R, numeric overflow in aggregations
- Fix approach: Add Pydantic validators for all incoming payload fields, enforce bounds (size ≥ 0.01, ≤ max_lot_size; balance ≥ 0)

**Status Case Inconsistency (Partially Fixed):**
- Issue: BUG-006 was partially fixed. Some queries use `.in_("status", ["CLOSED", "closed"])` but:
  - `src/worker.py:642` uses `.in_("status", ["active", "executed", "closed"])` — lowercase only (will miss uppercase ACTIVE/EXECUTED)
  - Database stores uppercase but some code still writes lowercase
- Files: `src/worker.py:642,697`, `src/logic.py:154-156`
- Impact: Risk guards like monthly loss limit silently return 0 results when DB upgraded to uppercase-only writes
- Fix approach: Define canonical status enum (uppercase PENDING/ACTIVE/CLOSED/REJECTED) in config, use throughout; add migration to normalize all historical records

---

## Known Bugs

**Concurrent Alert Processing Race:**
- Symptom: Duplicate exits processed simultaneously when TradingView retries webhook. Both write broker PnL, last-write wins, could overwrite accurate value with stale one.
- Files: `src/logic.py:120-220`, `src/adapters/supabase.py:261-276`
- Trigger: TradingView sends exit webhook twice within 5 seconds (network retry)
- Workaround: BUG-009 added idempotency check in `update_alert_exit()`, but no distributed lock — still vulnerable in high-concurrency scenarios (2+ workers consuming same queue)
- Fix: Add optimistic locking (version field) or distributed mutex via Redis

**Migration 026 Incomplete for Some JPY Pairs:**
- Symptom: Certain JPY pairs (CADJPY, CHFJPY) use static pip values that diverge from dynamic calculation at scale
- Files: `src/core/risk_engine.py:95-117` (dynamic calc), `migrations/026_add_missing_jpy_pairs.sql` (static seed)
- Impact: Position sizes for low-liquidity JPY pairs may be off by 5-15% vs. dynamic formula
- Workaround: Risk engine applies caps (`max_lot_size`), limits exposure
- Fix: Replace static values in symbol_risk_rules with formulas or dynamic fetch on first trade

**Frontend Backend Contract Violation - API Path Mismatch:**
- Symptom: Frontend may still expect `/api/v1/funding/*` routes but backend migrated to `/api/v1/funding/` (with trailing slash requirements)
- Files: `src/api_funding.py`, `frontend/src/*` (check exact paths in network tab)
- Impact: 404 errors on prop firm page if frontend caching old endpoints
- Workaround: Both `/api/v1/funding` and `/api/v1/funding/` routes work in FastAPI
- Fix: Ensure frontend service calls match backend router registration exactly

---

## Security Considerations

**No Rate Limiting on Signal Ingestion:**
- Risk: Webhook endpoint `/api/v1/webhook` can be flooded with TradingView alerts, filling queue/Redis, DoS
- Files: `src/api.py:500+` (webhook handler), `src/adapters/redis_queue.py` (enqueue)
- Current mitigation: slowapi decorator present on some endpoints but not webhook POST
- Recommendations:
  - Add rate limiter to `/api/v1/webhook` (e.g., 100 req/min per source IP)
  - Add queue size monitoring, discard old signals if backlog > threshold
  - Validate webhook origin (IP whitelist for TradingView's static IPs)

**Broker Credentials in Environment (No Rotation):**
- Risk: META_API_TOKEN stored in Railway env vars, no automated rotation, leaked token gives full account access
- Files: `.env` (not read due to security), `config/settings.py` reads META_API_TOKEN
- Current mitigation: Token expires naturally but no revocation mechanism
- Recommendations:
  - Implement token refresh cycle (quarterly rotation)
  - Use Railway secrets with audit logging
  - Monitor for token exposure in logs (grep META_API_TOKEN in debug output)

**Supabase Service Role Key Over-Privileged:**
- Risk: SUPABASE_SERVICE_ROLE_KEY grants full database access without row-level security
- Files: `src/adapters/supabase.py:41`, `src/adapters/supabase_api.py`
- Impact: Any code compromise = full data access
- Recommendations:
  - Use SUPABASE_ANON_KEY for frontend, service role only for backend workers
  - Enable RLS policies on all tables, test before deploying
  - Add Supabase audit logging, review access patterns monthly

**No Input Validation on TradingView Webhook Payload:**
- Risk: Arbitrary JSON accepted, no schema validation. Malformed entry/sl/tp could inject SQL-like strings or overflow calculations
- Files: `src/api.py:webhook handler`, `src/logic.py:should_forward_alert` (minimal checks)
- Impact: Corrupted position data, analytics calculations fail
- Fix: Add Pydantic schema validation with strict field types and bounds

---

## Performance Bottlenecks

**Synchronous Supabase Queries in Hot Path:**
- Problem: Every trade signal calls `supabase.table().select().execute()` synchronously in worker loop
- Files: `src/worker.py:625-656` (daily limit check), `src/worker.py:690-699` (monthly limit check), `src/logic.py:164-178` (alert lookup)
- Cause: No connection pooling, each query opens new HTTP connection to Supabase
- Improvement:
  - Cache limit checks in Redis (already partially done in daily limit at line 630-651)
  - Batch multi-account queries into single Supabase call
  - Use async/await pattern for I/O-bound lookups (requires refactor to async worker)
  - Current: ~500-1000ms per trade on cold cache, 50-100ms on warm cache

**No Database Indexing on Hot Queries:**
- Problem: Queries like `eq("status", "CLOSED")` on 100k+ signal rows without index
- Files: All `api_*.py` files that query `trading_signals` by status, symbol, account_name
- Impact: Analytics/evaluation pages slow (2-5 sec load) when traffic heavy
- Fix: Check migrations for INDEX statements; add compound indexes: `(status, created_at, account_name)`, `(symbol, status)`, `(trade_key)`

**Large JSON Parsing Without Streaming:**
- Problem: `filter_reason_json`, `ai_reasoning` stored as JSON blobs, parsed on every query for all trades
- Files: `src/adapters/supabase.py` queries with `.select("*")` instead of selective `.select("id,status,pnl_usd")`
- Impact: Network bandwidth wasted, slow paginated API calls
- Fix: Use `.select()` to fetch only needed columns; defer JSON parsing to client if possible

**Quadratic Correlation Guard (O(n²) positions):**
- Problem: `src/core/guard_rails/correlation.py` likely iterates all pairs of open positions
- Files: `src/core/guard_rails/correlation.py:697` (get_active_positions_from_db)
- Impact: With 10+ open positions, correlation check takes 100-200ms; scales badly
- Fix: Pre-compute correlation matrix in Redis on position open/close; on each signal, fetch precomputed matrix + lookup (O(n) instead of O(n²))

---

## Fragile Areas

**Multi-Account State Orchestration:**
- Files: `src/worker.py:100-200` (ThreadPoolExecutor account loop), `src/services/account_orchestrator.py`
- Why fragile: Each account has own adapter, own risk state, own broker connection, but shared Redis queue + shared database. Failures in one account's exit processing can block other accounts' queue processing.
- Safe modification: Add circuit breaker per account; if account fails 5× in a row, skip that account for 60s. Use try/except around each account's block in ThreadPoolExecutor.
- Test coverage: No explicit tests for account isolation or one-account-fails scenarios

**Guard Rail Order Dependency:**
- Files: `src/worker.py:500-700` (guard sequence)
- Why fragile: Kill switch → max lot → staleness → AI ensemble → per-account guards. If AI guard runs before correlation guard, correlation might see rejected position. If order changes, semantics change.
- Safe modification: Document guard order as immutable contract; never move guards without regression test suite. Consider dependency injection pattern to make order explicit.
- Test coverage: Tests may exist but not all guard combinations tested

**TradingView Entry/Exit Webhook Synchronization:**
- Files: `src/logic.py:120-220`, worker signal dequeue
- Why fragile: Entry webhook saves with `zone_id`, exit webhook looks up by `zone_id`. If entry never writes zone_id (malformed payload), exit silently skips. If TradingView retransmits entry while exit is being processed, race condition.
- Safe modification: Use distributed lock (Redis SET with EX) keyed by trade_key/zone_id for 30 seconds after entry webhook processed. Require both entry + exit to complete atomically.
- Test coverage: No test for concurrent entry/exit on same zone_id

**Position Reconciliation Stale Data Window:**
- Files: `src/api_positions.py` (positions endpoint), `scripts/cleanup_stale_positions.py`
- Why fragile: Reconciliation compares DB positions with broker positions, but reconciliation itself is not atomic. Between DB query and broker API call, broker could close position, causing false "stale" detection.
- Safe modification: Add timestamp to each DB fetch; revalidate broker position before marking stale if DB query is >5 seconds old. Or use broker as source of truth, fetch live from API, then compare to DB.
- Test coverage: Test suite doesn't exercise race between DB and broker state

---

## Scaling Limits

**Redis Queue Unbounded Growth:**
- Current capacity: Redis default 512MB memory (Railway default)
- Limit: If webhook floods (100 signals/sec for 10 min) = 60k queued signals ~300MB, Redis capacity warning at 90%
- Scaling: Switch to AWS SQS or increase Redis plan; add monitoring for queue depth
- Monitor: `MEMORY USAGE` Redis command; set up alert at >400MB

**Supabase Connection Pooling:**
- Current: Each request opens new HTTP connection to Supabase (no persistent connections)
- Limit: ~100 concurrent requests saturate connection limit; subsequent requests timeout
- Scaling: Implement connection pooling at adapter level; or move to Supabase Postgres direct connection (not JSON API)

**ThreadPoolExecutor Workers:**
- Current: `ThreadPoolExecutor(max_workers=4)` in worker.py for multi-account
- Limit: Python GIL limits true parallelism; with 4 workers + main thread, context switching overhead rises
- Scaling: Switch to `ProcessPoolExecutor` for CPU-heavy operations (AI ensemble), keep ThreadPoolExecutor for I/O (broker API calls)

**Backtest Data Volume:**
- Files: `src/services/historical_returns.py` fetches daily OHLC from yfinance
- Limit: yfinance has rate limits (2-3 symbols per request); 50+ symbols = 10+ API calls, 2-5 sec latency
- Scaling: Cache historical data locally, update incrementally; or use bulk data provider (IQFeed, Bloomberg)

---

## Dependencies at Risk

**yfinance API Deprecation:**
- Risk: yfinance is unofficial wrapper around Yahoo Finance; Yahoo can change API anytime
- Current: `src/services/historical_returns.py:98` removed deprecated `show_errors` parameter (was breaking in v0.2.x)
- Impact: Price data fetch could break unexpectedly mid-strategy
- Migration: Switch to `yfinance>=0.2.36` + fallback to alternative (e.g., Alpha Vantage, IQFeed, or local CSV)

**Anthropic API (Claude) Dependency:**
- Risk: Cost-sensitive; if prompt complexity rises, bill could spike. API rate limits (100 req/min on free tier)
- Files: `src/ai/brain.py` uses anthropic>=0.18.0 for AI Council ensemble
- Impact: AI filtering disabled if Anthropic API down
- Migration: Use local LLM (Ollama) as fallback; cache embeddings to reduce API calls

**Supabase v2.10.0 (Pinned Version):**
- Risk: Very specific version, no automatic updates. Security patches missed if version falls behind.
- Files: `requirements.txt:28` specifies `supabase==2.10.0`
- Impact: SQL injection or auth bypass in old version
- Fix: Update to `supabase>=2.10.0` (allow patch updates), pin only major version

**scikit-learn, lightgbm Pinned Versions:**
- Risk: `scikit-learn==1.7.2`, `lightgbm>=4.0.0` — if 1.7.2 has bug, must manually update
- Impact: Model training fails, position sizing broken
- Fix: Allow minor version updates: `scikit-learn>=1.7.0,<2.0`, test monthly

---

## Missing Critical Features

**No Alert Deduplication on Webhook Retries:**
- Problem: TradingView may send same signal 2-3x if webhook times out (>30 sec). Current code writes duplicate rows to DB.
- Blocks: Clean audit trail, accurate trade count, avoiding double-execution
- Impact: Dashboard shows 50 closed trades when only 30 unique entries executed
- Fix: Hash entry (symbol+entry+sl+tp+bar_time) and check for duplicate within 2-minute window before insert

**No Circuit Breaker for Broker Connection Failures:**
- Problem: If MetaAPI is down, worker keeps trying to open positions, all fail silently with "execution_failed" status. No automated pause or escalation.
- Blocks: Graceful degradation when broker unavailable
- Impact: User unaware that strategy paused; misses entire session worth of trades
- Fix: After 5 consecutive broker failures, auto-pause trading and send critical alert to operator

**No Account Balance Sync on Worker Start:**
- Problem: Worker loads balance from cache, which may be stale (last sync could be hours ago)
- Blocks: Accurate position sizing on first trade of session
- Fix: Call `adapter.get_account_information()` and cache fresh balance on worker startup

**No Automated Report Generation:**
- Problem: No daily/weekly email summary of performance, risks, alerts
- Blocks: Passive monitoring; user must log in to check dashboard
- Fix: Add cron job (APScheduler) to generate and email summary every 7 days

---

## Test Coverage Gaps

**No Tests for Concurrent Signal Processing:**
- What's not tested: Two signals queued simultaneously for same account; both pass guards; execution order matters (2nd might use stale balance)
- Files: `src/worker.py` ThreadPoolExecutor loop
- Risk: Race condition with account balance, margin checks in high-frequency scenarios (200+ signals/day)
- Priority: High (affects real money)

**No Tests for Failed Broker Reconnection:**
- What's not tested: Adapter connection drops mid-trade; worker doesn't detect; partial execution on broker, but status marked as rejected
- Files: `src/adapters/execution/meta_api_adapter.py:open_position`, `src/logic.py:execution path`
- Risk: Position opened on broker but DB says rejected; operator manually reconciles hours later
- Priority: High

**No Tests for Database Query Timeout:**
- What's not tested: Supabase timeouts; query hangs for >30 sec; worker blocking
- Files: All `src/api_*.py` Supabase table queries
- Risk: Single slow query blocks all account processing in ThreadPoolExecutor
- Priority: Medium

**No Integration Tests for Multi-Account Scenarios:**
- What's not tested: 3+ accounts on same worker; one account has broker connection failure; others continue normally
- Files: `src/worker.py` account orchestration
- Risk: Silent failures affecting only some accounts (others continue, so issue goes unnoticed for hours)
- Priority: Medium

**No End-to-End Tests for Entry→Exit Lifecycle:**
- What's not tested: Signal enters queue → passes guards → executes on broker → webhook confirms entry → exit webhook fires → position closes → PnL verified
- Files: `src/worker.py`, `src/logic.py`, `src/adapters/supabase.py`
- Risk: Hidden bugs in state transitions; e.g., position marked PENDING forever if exit webhook malformed
- Priority: High

---

## Database Consistency Risks

**No Transactions for Multi-Step Updates:**
- Problem: Saving signal + creating broker order + recording telemetry as separate unrelated `execute()` calls. If middle one fails, first succeeded and third skipped — inconsistent state.
- Files: `src/logic.py:120-220`, `src/adapters/supabase.py:save_alert`
- Impact: Position opened on broker but not recorded in DB; or recorded but no order ID (can't close later)
- Fix: Supabase transactions (if supported in v2.10.0) or add `transaction_id` field to atomically group related records

**No Constraints on Stale Position Cleanup:**
- Problem: `scripts/cleanup_stale_positions.py` auto-closes positions marked stale, but no undo. If stale detection was wrong (broker API transient error), position incorrectly marked CLOSED.
- Files: `src/api_positions.py:cleanup-stale`, `scripts/cleanup_stale_positions.py`
- Impact: Live position prematurely closed on DB, broker still open, hedge/exit logic broken
- Fix: Add audit log for cleanup; require manual confirmation for positions held >24 hours; backup before cleanup

**Orphaned Records After Failed Entry:**
- Problem: Entry rejected by guard; signal saved with status "guard_rejected"; but if exit webhook later arrives, it tries to look up this signal and finds it. Could update "rejected" record with PnL (wrong).
- Files: `src/logic.py:180-199` has check, but only for specific statuses
- Risk: Rejected entries might have stale PnL from different positions
- Fix: Add explicit column `entry_executed_on_broker` (bool), only update PnL if true

---

## Production Readiness Issues

**Insufficient Logging in Hot Path:**
- Problem: Worker loop has minimal logging between queue dequeue and signal save. If signal fails midway, no trace of which step failed.
- Files: `src/worker.py:100-400` (main loop), `src/logic.py:107-350` (process_trade)
- Fix: Add structured logging (log every guard pass/fail, every DB operation, every exception) using contextvars for request tracing

**No Metrics / Prometheus Export:**
- Problem: No visibility into queue depth, processing latency, error rates in production
- Files: Entire worker loop and API endpoints
- Impact: Operator blind to degradation until users complain
- Fix: Add prometheus_client, expose metrics endpoint (`/metrics`), integrate with monitoring (Datadog, New Relic)

**No Health Check Endpoints:**
- Problem: Orchestrator can't tell if worker is alive or hanging
- Fix: Add `/health` endpoint that checks: Redis connectivity, Supabase connectivity, last signal processed time. Return 503 if any critical service down.

**Hardcoded Defaults vs. Config:**
- Problem: Constants like `BALANCE_CACHE_TTL`, `MAX_OPEN_POSITIONS`, `ML_MIN_CONFIDENCE` hardcoded in source
- Files: `src/logic.py:38`, `src/worker.py:56-59`
- Impact: Can't tune without code deploy
- Fix: Move all to `config/settings.py` as configurable via env vars

---

## Known Workarounds (Temporary Fixes)

**1. Symbol Whitelist Override:**
- Issue: SYMBOL_WHITELIST_ENABLED (src/worker.py:71) is global kill switch for some symbols. If disabled, low-EV symbols can trade.
- Workaround: Keep enabled by default, disable only for backtesting
- Permanent fix: Implement per-symbol profitability scoring at signal time, use dynamic whitelist

**2. Balance Cache TTL:**
- Issue: 30-second stale balance can cause oversizing in volatile markets
- Workaround: Set BALANCE_CACHE_TTL=5 for more frequent fetches (costs 20ms latency per signal)
- Permanent fix: Implement Redis distributed cache keyed by account_name, invalidate on every position close

**3. Pine Initial Capital Mismatch:**
- Issue: TradingView uses $10M initial_capital, backend has $50k account (position sizing 200× off without cap)
- Workaround: MAX_LOT_SIZE=10 guard caps exposure; sector limit provides portfolio-level protection
- Permanent fix: Update Pine script to read actual account balance input from user

**4. JPY Pair Dynamic Sizing Lag:**
- Issue: NZDJPY/CADJPY use static pip_value until first trade, then switch to dynamic
- Workaround: First trade may size incorrectly; subsequent trades correct
- Permanent fix: Pre-compute dynamic pip_value in migration, seed symbol_risk_rules with accurate formulas

---

## Recommendations (Priority Order)

1. **CRITICAL:** Add transaction support or distributed locks for entry/exit webhook processing (race condition)
2. **CRITICAL:** Implement circuit breaker for broker connection failures (graceful degradation)
3. **HIGH:** Add comprehensive logging/metrics to worker loop (production visibility)
4. **HIGH:** Fix status case consistency (normalize to uppercase everywhere)
5. **MEDIUM:** Implement concurrent signal test suite (catch race conditions)
6. **MEDIUM:** Cache limit checks in Redis (performance)
7. **MEDIUM:** Add database indexes on hot queries (analytics latency)
8. **LOW:** Move hardcoded constants to config (operational flexibility)

---

*Concerns audit: 2026-03-18*
