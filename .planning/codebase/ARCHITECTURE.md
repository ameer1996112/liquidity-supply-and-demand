# System Architecture

**Analysis Date:** 2026-01-19

## Overview

**Pattern:** Event-Driven Domain-Driven Design (DDD) Algorithmic Trading Platform

**Key Characteristics:**
- Async/await throughout all I/O operations
- Pydantic validation at all system boundaries
- Redis-backed queue for signal durability
- Per-account risk isolation and circuit breakers
- Guard-rail pattern for trade vetoes
- Observer pattern for cross-cutting concerns
- Multi-account profile-based execution

## Architecture Layers

### 1. External Interface Layer (API)
- **Purpose:** Receive TradingView webhooks, validate payloads, queue signals
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/api.py`, `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/api_*.py` (35+ endpoint files)
- **Contains:** FastAPI routers, Pydantic schemas, rate limiting, webhook handlers
- **Depends on:** Redis, Pydantic settings
- **Used by:** TradingView external signals

**Entry Points:**
- `POST /webhook` - Primary signal ingress (symbol, side, entry, sl, tp, size)
- `POST /accounts/{account_id}/kill-switch` - Emergency halt (per-account)
- Webhook authentication via `WEBHOOK_SECRET` (when set)

### 2. Queue & Distribution Layer
- **Purpose:** Decouple signal receipt from execution; enable horizontal worker scaling
- **Location:** Redis instance (configured via `REDIS_URL`)
- **Contains:** Signal queue, rate limit tracking, kill-switch state
- **Depends on:** Redis server
- **Used by:** API layer (producer), Worker layer (consumer)

**Pattern:** Producer-consumer with Redis list LPUSH/BRPOP

### 3. Worker & Pipeline Layer
- **Purpose:** Consume signals, orchestrate guard-rails, execute trades
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/worker.py`, `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/pipeline/`
- **Contains:** Worker loop, pipeline orchestrator, profile executor, guard-rail invoker
- **Depends on:** Redis, Supabase, MetaApi, all guard-rail services
- **Used by:** N/A (top-level orchestrator)

**Pipeline Flow:**
1. Worker fetches signal from Redis
2. Load broker profiles for multi-account execution
3. Apply guard-rails (can veto trade)
4. Calculate position sizing via Risk Engine
5. Execute via MetaApi adapter (with retry/circuit breaker)
6. Persist results to Supabase
7. Emit events to observers

### 4. Guard-Rails Layer
- **Purpose:** Pluggable trade vetoes based on market conditions, account state, risk limits
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/core/guard_rails/`
- **Contains:** 9+ guard implementations
- **Depends on:** Market data, account state, configuration
- **Used by:** Pipeline executor

**Guard Implementations:**
- `staleness.py` - Reject stale signals (>30s delay)
- `pine_guardian.py` - Validate signal against TradingView Pine script logic
- `prop_guard.py` - Prop firm capital preservation rules
- `sector.py` - Sector exposure limits
- `holiday.py` - Market holiday detection
- `market_filter.py` - Volatility regime filtering
- `correlation.py` - Correlation-based position limits
- `portfolio_var.py` - Portfolio Value-at-Risk guard

**Pattern:** Chain-of-responsibility with early-exit veto capability

### 5. Risk Engine Layer
- **Purpose:** Position sizing, risk calculations, prop firm compliance
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/core/risk_engine.py`
- **Contains:** Risk calculations, position sizing formulas, drawdown tracking
- **Depends on:** Symbol metadata, account metrics, market data
- **Used by:** Pipeline executor, profile executor

**Key Capabilities:**
- Dynamic position sizing by symbol type (forex, JPY pairs, indices, crypto, gold)
- Spread compensation and SL buffer calculations
- Per-symbol risk overrides from `symbol_risk_rules` table
- Half-risk enforcement for 2nd daily trade
- Kill switch triggers (daily loss limit 4%, max drawdown 8%)

### 6. Execution Adapter Layer
- **Purpose:** Broker abstraction with resilience patterns
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/adapters/execution/meta_api_adapter.py`
- **Contains:** MetaApi client, retry logic, circuit breakers, connection management
- **Depends on:** MetaApi cloud SDK, broker profiles
- **Used by:** Pipeline executor

**Resilience Patterns:**
- Exponential backoff retry (5 attempts, starting at 1s)
- Per-account circuit breaker (5min cooldown after 3 consecutive errors)
- 504 detection with weekend market close handling
- Token refresh on authentication failures
- Pending order tracking with duplicate detection

### 7. Multi-Account Profile Layer
- **Purpose:** Support multiple trading accounts with independent risk settings
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/core/broker_profiles.py`
- **Contains:** Profile loader, account routing, per-account configuration
- **Depends on:** Supabase `broker_profiles` table, environment variables
- **Used by:** Worker, pipeline executor, MetaApi adapter

**Configuration Sources (priority order):**
1. `broker_profiles` table in Supabase (runtime configurable)
2. Environment variables (`META_API_ACCOUNT_1_ID`, `META_API_ACCOUNT_1_TOKEN`, etc.)

### 8. Observer / Event Layer
- **Purpose:** Cross-cutting concerns without polluting business logic
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/core/observers/`
- **Contains:** Auditor, risk observer, metrics, account router
- **Depends on:** Event bus (async queue)
- **Used by:** Pipeline (emits), observers (consume)

**Event Types:**
- `SignalReceived`
- `GuardRailPassed` / `GuardRailVetoed`
- `TradeExecuted` / `TradeFailed`
- `AccountDrawdownAlert`

### 9. AI/ML Council Layer
- **Purpose:** Multi-agent LLM debate for signal quality assessment
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/ai/`
- **Contains:** Trading council, debate engine, LLM client, RAG engine
- **Depends on:** OpenAI/Anthropic APIs, Pinecone (vector store)
- **Used by:** Guard-rails (optional), manual review workflow

**Agents:**
- Supervisor Agent - Orchestrates debate
- Risk Agent - Argues against trade
- Quant Agent - Argues for trade
- Consensus requires 2-of-3 agreement

### 10. Data Persistence Layer
- **Purpose:** State storage, audit trail, dashboard data
- **Location:** Supabase (PostgreSQL + realtime)
- **Contains:** Signals, trades, account metrics, risk events, audit logs
- **Depends on:** Supabase service
- **Used by:** API, worker, frontend dashboard

**Key Tables:**
- `signals` - Inbound webhook data
- `trades` - Execution results
- `account_metrics` - Real-time balance, equity, margin
- `broker_profiles` - Multi-account configuration
- `symbol_risk_rules` - Per-symbol overrides
- `risk_events` - Kill switches, limit breaches

### 11. Frontend Layer
- **Purpose:** Real-time dashboard, risk monitoring, manual controls
- **Location:** `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend/`
- **Contains:** Next.js 15 + React 19 + TypeScript, server/client components
- **Depends on:** Supabase JS client (realtime subscriptions)
- **Used by:** Traders, risk managers

**Architecture Pattern:**
- Server Components for data fetching (Supabase)
- Client Components for interactivity (kill switches, charts)
- Realtime subscriptions preferred over polling

## Data Flow

### Primary Signal Flow (TradingView → Broker)

```
TradingView Webhook
    ↓
[api.py] POST /webhook
    ↓
Pydantic validation (Signal schema)
    ↓
Rate limit check (slowapi)
    ↓
Redis LPUSH (signal queue)
    ← 200 OK to TradingView (immediate)
    ↓
[worker.py] BRPOP from queue
    ↓
Load broker profiles (multi-account)
    ↓
For each account profile:
    ↓
Pipeline.execute()
    ↓
Guard-rails.check() → veto? skip account
    ↓
RiskEngine.calculate_position_size()
    ↓
MetaApiAdapter.place_order()
    ↓
    ├─ Retry logic (5 attempts, exp backoff)
    ├─ Circuit breaker check
    ├─ Token refresh on 401
    └─ 504 detection (weekend check)
    ↓
Supabase.insert(trade record)
    ↓
Observer.emit(TradeExecuted)
    ↓
Discord/Telegram notification
```

### Account Synchronization Flow

```
MetaApi (MT4/MT5)
    ↓
Realtime event stream (account metrics)
    ↓
MetaApiAdapter.handle_stream_event()
    ↓
Supabase.update(account_metrics)
    ↓
[frontend] Supabase realtime subscription
    ↓
Dashboard auto-updates (no polling)
```

### Kill Switch Flow

```
Trader clicks Kill Switch (frontend)
    ↓
POST /accounts/{id}/kill-switch
    ↓
Redis SET kill-switch:{account_id} = true (TTL 24h)
    ↓
Worker pipeline checks Redis before execution
    ↓
If kill-switch active → abort with log entry
    ↓
Notification sent to Discord
```

## Key Abstractions

### Signal
- **Schema:** `symbol`, `side` (buy/sell), `entry` (float), `sl` (float), `tp` (float), `size` (optional), `timestamp`
- **Validation:** Price levels must be valid for side (e.g., SL < entry for buy)
- **Idempotency:** Duplicate detection via `signal_id` hash

### BrokerProfile
- **Fields:** `account_id`, `meta_api_token`, `risk_multiplier`, `max_positions`, `paper_trading`
- **Source:** Supabase table or env vars
- **Scope:** Isolated per-account risk settings

### GuardRail
- **Interface:** `check(signal, context) → Pass | Veto(reason)`
- **Pattern:** Immutable context inspection, no side effects
- **Ordering:** Staleness → Pine → Market → Sector → Correlation → VaR → Prop

### PositionSizeResult
- **Fields:** `units`, `risk_percent`, `max_loss_amount`, `leverage_used`
- **Calculation:** Based on symbol type, account equity, SL distance
- **Override:** `symbol_risk_rules` table can customize per-symbol

### CircuitBreaker
- **State:** `CLOSED` (normal), `OPEN` (failing), `HALF_OPEN` (testing)
- **Trigger:** 3 consecutive errors
- **Cooldown:** 5 minutes
- **Per-Account:** Independent state per `account_id`

## Error Handling Strategy

**API Layer:**
- Validation errors → 422 with Pydantic detail
- Rate limit → 429 with retry-after
- Unexpected → 500 + Discord alert

**Worker Layer:**
- Guard veto → Logged + skip (not error)
- MetaApi retryable → Exponential backoff, circuit breaker
- MetaApi fatal → Circuit breaker + alert
- Unexpected → Log + continue (don't kill worker)

**Adapter Layer:**
- 401 Unauthorized → Refresh token, retry once
- 504 Gateway Timeout → Check weekend, retry with longer backoff
- Connection lost → Reconnect with jitter

## Infrastructure

**Docker Services (docker-compose.yml):**
- `redis` - Queue + state cache
- `backend` - FastAPI (port 8000)
- `worker` - Python async worker
- `frontend` - Next.js dev server (port 3000)

**Production Deployment:**
- Railway (nixpacks-based)
- Separate worker dyno for scalability
- Redis via Railway add-on

**Environment Variables:**
- `REDIS_URL` - Queue connection
- `SUPABASE_URL`, `SUPABASE_KEY` - Database
- `META_API_ACCOUNT_*_ID`, `META_API_ACCOUNT_*_TOKEN` - Broker accounts
- `WEBHOOK_SECRET` - Optional webhook auth
- `PAPER_TRADING` - Global paper mode override
- `AI_FILTER_ENABLED`, `ML_GUARDIAN_ENABLED` - Guard toggles

---

*Architecture analysis: 2026-01-19*
