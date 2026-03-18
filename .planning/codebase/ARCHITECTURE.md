# Architecture

**Analysis Date:** 2026-03-18

## Pattern Overview

**Overall:** Event-sourced microservices with layered guards, observer pattern pipeline, and multi-account isolation.

**Key Characteristics:**
- **API-first WebHook receiver** (`api.py`) → **Redis queue** → **Worker executor** (`worker.py`) → **Logic engine** (`logic.py`)
- **Multi-layered guard rails** (global and per-account) that fail-safe on rejection
- **Observer pattern** for non-blocking observability (audit, metrics, risk tracking)
- **AI ensemble decision** (Random Forest + RAG + LLM Council) at execution time
- **Account routing** with per-account queue isolation (`signals:{account_id}`)
- **Adapter pattern** for execution (MetaAPI live, paper trader, DRY run), database (Supabase), and caching (Redis)

## Layers

**API Layer (HTTP/WebSocket):**
- Purpose: Receive trading signals from external webhooks (TradingView Pine Script), validate, enqueue
- Location: `src/api.py`, `src/api_*.py` (specialized routers)
- Contains: FastAPI app, CORS, rate limiting, request logging, route registration
- Depends on: Redis (queue), Supabase adapter (read/write operations)
- Used by: External webhooks, frontend UI, testing scripts
- Key routers:
  - `api_execution.py`: Order placement commands
  - `api_positions.py`: Position reconciliation and broker sync
  - `api_portfolio_control.py`: Portfolio management, MAS Council integration
  - `api_analytics.py`: Trade analytics and performance
  - `api_board.py`: Kanban ticket management for agents

**Consumer/Worker Layer (Background Task):**
- Purpose: Dequeue signals, apply global guards (risk, AI, kill-switch), route to accounts
- Location: `src/worker.py`
- Contains: Signal dequeuing, guard orchestration, thread pool executor for account isolation
- Depends on: Redis, config settings, core guards, AI brain, account router
- Used by: Main event loop (runs continuously)
- Guard execution sequence:
  1. **Global guards** (run once per signal):
     - Kill-switch (environment variable check)
     - Max lot size (cap position before sector guard)
     - Staleness guard (position freshness check)
     - AI ensemble decision (Fast-path bypass or full council debate)
  2. **Per-account guards** (inside account loop, parallel execution):
     - Kill-switch (Redis/MTM-based)
     - Circuit breaker (prevent cascading failures)
     - PropGuard (prop firm daily/drawdown limits)
     - Correlation guard (symbol exposure)
     - Portfolio VAR guard (Value-at-Risk)
     - Sector guard (market concentration)
     - Consistency analyzer (position count/spread)

**Logic/Execution Engine:**
- Purpose: Execute trade on broker/paper, save to database, notify
- Location: `src/logic.py`
- Contains: Broker adapter selection, balance caching, paper position simulation, alert/notification
- Depends on: Execution adapter (router), Supabase, Discord/Telegram notification
- Used by: Worker (after all guards pass)
- Responsibilities:
  - Get cached broker balance (30-second TTL to reduce latency)
  - Create/execute order via adapter
  - Save alert record to database with actual broker PnL (not TradingView simulation)
  - Send notifications (Discord, Telegram)
  - Log latency traces (signal to submit, submit to fill)

**Core Domain Layer (Pure Logic):**
- Purpose: Business logic without I/O dependencies
- Location: `src/core/`
- Contains:
  - `risk_engine.py`: Position sizing, pip calculations, dynamic JPY scaling, indices/crypto support
  - `signal.py`: Signal validation schemas and webhook payload types
  - `transport.py`: Message envelope (correlation ID, timestamp, metadata)
  - `consumer_validator.py`: Dequeued message structural validation
  - `broker_profiles.py`: Multi-broker configuration
  - `circuit_breaker.py`: Fail-fast pattern for cascading failures
  - `dynamic_config.py`: Runtime settings override from database
  - `account_router.py`: Signal → account routing rules
  - Guard rails (separate):
    - `guard_rails/sector_guard.py`: Market concentration limits
    - `guard_rails/correlation.py`: Symbol cross-correlation analysis
    - `guard_rails/portfolio_var_guard.py`: Portfolio-level Value-at-Risk
    - `guard_rails/prop_guard.py`: Prop firm capital preservation
    - `guard_rails/market_filter.py`: Market session/news filters
    - `guard_rails/pine_guardian.py`: TradingView Pine validation
    - `guard_rails/staleness_guard.py`: Position freshness
  - Observers (separate):
    - `observers/base.py`: TradeEvent dataclass, Observer ABC, WorkerSubject harness
    - `observers/auditor.py`: Trade audit logging to database
    - `observers/risk_observer.py`: Risk event tracking
    - `observers/executor.py`: Execution phase observability
    - `observers/metrics.py`: Prometheus/internal metrics collection
    - `observers/account_router_observer.py`: Account routing decisions

**Services Layer (Business Operations):**
- Purpose: Complex multi-step operations, state management, calculations
- Location: `src/services/`
- Contains:
  - `account_orchestrator.py`: Multi-account lifecycle, balance fetching, MTM monitoring
  - `account_sync_service.py`: Broker ↔ Database position reconciliation
  - `execution_engine.py`: Latency analysis, TCA (Transaction Cost Analysis), alert generation
  - `trading_engine.py`: Trade state machine (entry, exit, management)
  - `trail_stop_manager.py`: Trailing stop order management
  - `breakeven_manager.py`: Breakeven stop management
  - `watchdog.py`: Position monitoring, timeout detection, auto-close stale positions
  - `position_optimizer.py`: Notional value calculation, sector assignment
  - `portfolio_analyzer.py`: Exposure analysis, correlation computation
  - `mtm_guardian.py`: Mark-to-market monitoring for account health
  - `prop_firm_tracker.py`: Prop firm rules tracking (daily loss, drawdown)
  - `consistency_analyzer.py`: Trade state consistency vs. broker
  - `backtest_engine.py`: Historical performance calculation
  - `alert_engine.py`: Alert lifecycle and state transitions
  - `tca_analyzer.py`: Transaction cost analysis (slippage, commission, latency)

**AI/ML Layer:**
- Purpose: Intelligent trade approval/rejection with ensemble voting
- Location: `src/ai/`
- Contains:
  - `brain.py`: Ensemble orchestrator (RF + RAG + LLM Council)
    - Fast-path bypass for high-confidence setups (RF confidence > 0.8)
    - Full debate if confidence 0.6–0.8 or enabled via settings
  - `ml_guardian.py`: Random Forest confidence scoring
  - `trading_council.py`: LLM-based ensemble debate (Anthropic, OpenAI, Gemini)
  - `ai_guardian.py`: AI decision validation and logging
  - `debate.py`: Council member voting and consensus
  - `rag_engine.py`: Retrieval-Augmented Generation from historical trades
  - `llm_client.py`: Unified LLM provider client (anthropic, openai, gemini, local)
  - `features.py`: Feature engineering for ML prediction
  - `council_memory.py`: LLM context and prior decisions

**Adapters/Integration Layer:**
- Purpose: External dependencies and technology integration
- Location: `src/adapters/`
- Contains:
  - `execution/router.py`: Route to MetaAPI, paper trader, or DRY run based on `run_mode`
  - `execution/metaapi.py`: MetaAPI live broker integration
  - `execution/paper.py`: Paper trading simulator
  - `supabase.py`: Supabase REST API client (alerts, positions, rules, orders)
  - `discord.py`: Discord webhook notifications (async + sync)
  - `paper_trader.py`: In-memory position simulator
  - `market_data.py`: Market data fetch (Yahoo Finance, news feeds)
  - `redis_queue.py`: Redis connection and queue operations

**Data/Configuration Layer:**
- Purpose: Configuration, environment variables, schema definitions
- Location: `config/`, `migrations/`
- Contains:
  - `config/settings.py`: Pydantic BaseSettings (load from .env, fail-fast on missing SUPABASE_URL/REDIS_URL)
  - `config/logging_config.py`: Structured logging setup
  - `migrations/`: SQL schema (51 migrations, latest: board tables for agent UI)

## Data Flow

**Entry Flow (Signal Arrival):**

1. **Webhook Ingestion** (`api.py:webhook_post`)
   - TradingView Pine Script sends signal to `/api/v1/webhook/entry` or `/exit`
   - Payload validation (EntryWebhookPayload schema)
   - Account routing: stamp `_account_id` via AccountRouter (default if unspecified)
   - Push to Redis: `signals:{account_id}` (e.g., `signals:default`)
   - Return 200 immediately

2. **Signal Dequeue** (`worker.py:main_loop`)
   - Pop message from `signals:{account_id}` queue
   - Consumer validation (structure, fields, timestamps)
   - Emit `SIGNAL_RECEIVED` event (observers notified)

3. **Global Guards** (worker.py, before account loop):
   - **Kill-switch**: Check `TRADING_KILL_SWITCH=true` env var → block all
   - **Max lot size**: Cap at `MAX_LOT_SIZE=10` lots
   - **Staleness guard**: Position age > 24h → warn/reject
   - **AI Ensemble** (`brain.py`):
     - Random Forest confidence score
     - If RF > 0.8 (high confidence): Fast-path bypass, execute immediately
     - If RF 0.6–0.8: Full debate mode (AI Council vote)
     - If RF < 0.6: Reject (in warning mode, allow with flag)

4. **Per-Account Execution** (worker.py account loop, parallel via ThreadPoolExecutor):
   - **Circuit Breaker**: Account had 3+ failures → open circuit, reject
   - **PropGuard**: Remaining daily loss budget, max drawdown check
   - **Correlation Guard**: Symbol cross-correlation matrix analysis
   - **Portfolio VAR Guard**: Conditional Value-at-Risk calculation
   - **Sector Guard**: Market concentration (forex majors, indices, JPY, etc.)
   - **Consistency Analyzer**: DB position count vs. broker positions
   - If all guards pass: Emit `SIGNAL_VALIDATED` event → call `logic.process_trade`

5. **Execution** (`logic.py:process_trade`):
   - Get cached broker balance (30-second cache)
   - Calculate max position size via `risk_engine.calculate_max_position_size()`
     - Symbol-aware pip calculation (forex 0.0001, indices 1.0, JPY dynamic, metals 0.01)
     - Position sizing: `(equity * risk_pct) / (pips_risk * pip_value)`
   - Call execution adapter (live/paper/dry-run)
   - Save alert to Supabase with real broker PnL (not TradingView backtest PnL)
   - Emit `ORDER_SUBMITTED` event
   - Send notifications (Discord, Telegram)
   - Log TCA trace (signal→submit→fill latency)

6. **Post-Execution Monitoring**:
   - **Watchdog** monitors open positions for stale/stuck trades
   - **Trailing Stop Manager** adjusts stop-loss orders based on price movement
   - **Breakeven Manager** moves stops to cost after favorable price move
   - **Account Sync** reconciles DB positions vs. broker via MetaAPI every 30 seconds
   - **MTM Guardian** calculates mark-to-market equity and triggers alerts if needed

**Exit Flow (Position Closure):**

1. TradingView sends exit signal with `exit_type` (TP/SL/manual)
2. Worker processes exit through same guard pipeline (same risk checks apply)
3. `logic.close_trade()` calls adapter to close position on broker
4. Fetch actual deal from MetaAPI: real `profit`, `commission`, `swap`
5. Update database alert record with actual PnL (not simulated)
6. Emit `POSITION_UPDATED` event
7. Notify user via Discord/Telegram

**State Management:**

- **In-Memory State**:
  - Open positions cached in `account_orchestrator.py` (refreshed every 30s)
  - Balance cache in `logic.py` (30-second TTL)
  - Settings cache in `dynamic_config.py` (config can change at runtime from DB)
  - RF model cache in `ml_guardian.py` (pickle serialized model)

- **Persistent State**:
  - All trades in Supabase `alerts` table (entry, exit, PnL, commission, swap)
  - Account balance in Supabase `account_strategies` table
  - Positions in Supabase `positions` table (live + archived)
  - Rules in `symbol_risk_rules`, `guard_rails_config` tables
  - Board tickets in `board_tickets`, `board_changes` tables (for agent UI)

## Key Abstractions

**TradeEvent (Observer Pattern):**
- Purpose: Immutable event record for pipeline observability
- Examples: `src/core/observers/base.py`
- Pattern: Event-sourced, fired at SIGNAL_RECEIVED/VALIDATED/ERROR
- Non-blocking: Observers never affect control flow

**Guard Rail (Middleware Chain):**
- Purpose: Fail-safe rejection before execution
- Examples: `src/core/guard_rails/sector_guard.py`, `prop_guard.py`, `portfolio_var_guard.py`
- Pattern: Each guard returns `(passes: bool, reason: str)`
- All must pass; first failure → block trade and log reason

**Adapter (Strategy Pattern):**
- Purpose: Swap implementation details (MetaAPI vs. paper trader vs. DRY run)
- Examples: `src/adapters/execution/router.py`
- Pattern: `get_adapter(run_mode)` returns protocol-compatible interface
- Interface: `submit_order(OrderRequest) → OrderResponse`, `close_position(CloseRequest) → CloseResponse`

**Account Router (Routing):**
- Purpose: Route signal to correct account queue and isolation context
- Examples: `src/core/account_router.py`
- Pattern: Resolve `payload['_account_id']` or fall back to `"default"`
- Queue partitioning: `signals:{account_id}` allows per-account parallelism

**Risk Engine (Domain Model):**
- Purpose: Pure domain logic for position sizing and risk metrics
- Examples: `src/core/risk_engine.py`
- Pattern: No I/O, no DB calls; pure functions
- Responsibilities:
  - Dynamic pip calculation (JPY pairs scale by entry price)
  - Position sizing: `(equity * risk%) / (pips * pip_value)`
  - Max lot caps per symbol

**Ensemble Brain (AI Decision):**
- Purpose: Three-tier voting (RF fast-path → LLM debate → consensus)
- Examples: `src/ai/brain.py`, `ml_guardian.py`, `trading_council.py`
- Pattern: Short-circuit on high confidence; escalate to debate if uncertain
- Voting: RF confidence, LLM members (Analyst, Skeptic, Risk Manager), veto rules

## Entry Points

**API Entry Point:**
- Location: `src/api.py`
- Triggers: HTTP POST to `/api/v1/webhook/entry` or `/api/v1/webhook/exit`
- Responsibilities:
  - Validate webhook payload schema
  - Stamp `_account_id` via AccountRouter
  - Push to Redis queue `signals:{account_id}`
  - Return 200 (fire-and-forget)

**Worker Entry Point:**
- Location: `src/worker.py:main()`
- Triggers: Process started (continuous event loop)
- Responsibilities:
  - Initialize connections (Redis, Supabase, ML models, adapters)
  - Pop signals from queues (partitioned by account)
  - Orchestrate guard pipeline and account routing
  - Invoke `logic.process_trade()` for each valid signal

**Frontend Entry Points:**
- Location: `frontend/src/app/page.tsx` (dashboard), specific pages
- Triggers: User navigation, WebSocket connections, API polling
- Responsibilities:
  - Display real-time positions, PnL, alerts
  - Allow manual controls (cancel, modify, close)
  - Show board tickets (Kanban for agents)
  - Render analytics, risk metrics, execution quality

## Error Handling

**Strategy:** Fail-safe rejection; never execute if guards fail.

**Patterns:**

1. **Guard Failure** (all guards):
   - Guard returns `(False, reason_str)`
   - Worker logs rejection reason with correlation ID
   - Emit `ERROR` event (observers notified)
   - Observer (AuditorObserver) logs rejection to database
   - No execution happens

2. **Adapter Error** (broker API, network):
   - Execution adapter raises exception
   - `logic.process_trade()` catches, logs error with stack trace
   - Emit `ERROR` event with exception metadata
   - Observer logs error, retries scheduled via circuit breaker
   - Alert record NOT saved to database (failed order)

3. **Database Error** (Supabase):
   - `supabase_adapter.save_alert()` fails
   - Logged with trade details (fallback to stderr)
   - Does not block execution (order already placed on broker)
   - Alert may be missing from UI, but broker has position

4. **Notification Error** (Discord, Telegram):
   - `send_discord()` fails
   - Logged as warning, does not affect trade
   - Order already on broker, database already updated

5. **AI Error** (timeout, API failure):
   - LLM call fails or timeouts (5-second default)
   - Fall back to RF confidence alone
   - If RF > 0.6: Allow (in warning-only mode)
   - If RF < 0.6: Reject and log AI failure + RF low

## Cross-Cutting Concerns

**Logging:**
- Framework: Python logging with `config/logging_config.py`
- Levels: DEBUG (latency traces), INFO (decisions), WARNING (rejections), ERROR (failures)
- Correlation ID: All events for one signal share UUID (linked in logs)
- Trade context: `trade_context.set()` adds trade metadata to all log lines
- Sample log lines:
  ```
  [trinity.worker] SIGNAL_RECEIVED | signal_id=abc123 | symbol=EURUSD | side=buy
  [trinity.logic] RF confidence: 0.75 (DEBATE MODE) | signal_id=abc123
  [trinity.worker] 🔍 Sector Guard | symbol=EURUSD | notional=$50k | limit=40% → PASS
  [trinity.worker] ✅ ORDER_SUBMITTED | symbol=EURUSD | lots=0.5 | pnl=$+250 | latency=2.3s
  ```

**Validation:**
- Pydantic schemas: `EntryWebhookPayload`, `ExitWebhookPayload`, `TradeRiskParams`
- Schema validation at API layer (schema mismatch → 400)
- Runtime validation in consumer validator (structure, field types)
- Business rule validation in guards (risk limits, exposure limits)

**Authentication:**
- API: WEBHOOK_SECRET env var; webhook caller must send `webhook_secret` header
- Database: Supabase RLS (Row-Level Security) via service role key
- External LLM APIs: API keys in `config/settings.py` (Anthropic, OpenAI, Gemini)

---

*Architecture analysis: 2026-03-18*
