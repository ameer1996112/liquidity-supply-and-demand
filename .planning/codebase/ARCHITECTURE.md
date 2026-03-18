# Architecture

## System Pattern

**Microservices with shared Python codebase.** Three main services communicate via Redis queue and shared Supabase database.

```
TradingView Alert
       │
       ▼
┌─────────────┐     Redis Queue     ┌─────────────┐
│  Backend API │ ─────────────────► │   Worker    │
│  (FastAPI)   │                     │  (Python)   │
│  Port 8000   │                     │             │
└──────┬───────┘                     └──────┬──────┘
       │                                    │
       │         ┌──────────┐               │
       └────────►│ Supabase │◄──────────────┘
                 │ (Postgres)│
                 └─────┬────┘
                       │
              ┌────────┴────────┐
              │   Frontend      │
              │   (Next.js)     │
              │   Port 3000     │
              └─────────────────┘
```

## Layers

### 1. API Layer (`src/api.py` + `src/api_*.py`)
- **Main entrypoint**: `src/api.py` (30KB) — FastAPI app, CORS, health check, webhook endpoint
- **Route modules**: 20+ `api_*.py` files — accounts, analytics, alerts, backtests, board, copilot, evaluation, execution, funding, market, portfolio, positions, prop-firm, risk, rules, strategies, traces, webhooks
- **Responsibility**: Validate incoming signals, push to Redis queue, serve REST API for frontend

### 2. Worker (`src/worker.py`)
- **Monolithic worker**: 82KB single file — the largest file in the codebase
- **Responsibility**: Consume signals from Redis → run guard rails → AI/ML validation → execute trades → sync accounts → notifications
- **Pattern**: Polling loop with APScheduler for background tasks (broker reconciliation, account sync, daily reset)

### 3. Core Layer (`src/core/`)
- **Signal model**: `src/core/signal.py` — trade signal data model
- **Guard rails**: `src/core/guard_rails/` — 7 pre-execution filters:
  - `correlation.py` — Portfolio correlation checks
  - `market_filter.py` — Session/time/spread filtering
  - `pine_guardian.py` — Pine Script rule mirroring
  - `portfolio_var_guard.py` — Value-at-Risk limits
  - `prop_guard.py` — Prop firm compliance
  - `sector_guard.py` — Sector exposure limits
  - `staleness_guard.py` — Signal freshness checks
- **Risk engine**: `src/core/risk_engine.py` (17KB) — Position sizing, drawdown protection
- **Circuit breaker**: `src/core/circuit_breaker.py` — Trading halt mechanism
- **Dynamic config**: `src/core/dynamic_config.py` (12KB) — Runtime config overrides
- **Account routing**: `src/core/account_router.py` — Multi-account signal routing

### 4. Services Layer (`src/services/`)
- **35+ service files** — business logic (largest layer)
- **Key services**:
  - `execution_engine.py` (13.5KB) — Trade execution orchestration
  - `account_orchestrator.py` (28KB) — Account lifecycle management
  - `account_sync_service.py` (23KB) — MetaAPI account synchronization
  - `broker_reconciliation.py` (12.5KB) — Position/trade reconciliation
  - `portfolio_analyzer.py` (22KB) — Portfolio analytics
  - `tca_analyzer.py` (17KB) — Transaction cost analysis
  - `prop_firm_tracker.py` (15KB) — Prop firm challenge tracking
  - `trailing_stop_manager.py` (15.7KB) — Dynamic stop management
  - `hedging_engine.py` (14.4KB) — Hedging strategies

### 5. AI/ML Layer (`src/ai/`)
- **Trading Council**: `trading_council.py` (38.6KB) — Multi-agent debate system (Bull/Bear/Risk/Chair)
- **Brain**: `brain.py` (59.4KB) — Ensemble AI decision engine (largest AI file)
- **AI Guardian**: `ai_guardian.py` (26.6KB) — LLM-based trade validation
- **ML Guardian**: `ml_guardian.py` (20.3KB) — ML model (Random Forest/LightGBM) predictions
- **Debate**: `debate.py` (11KB) — Bull vs Bear debate execution
- **RAG Engine**: `rag_engine.py` (7.8KB) — Retrieval-augmented generation for trade context
- **LLM Client**: `llm_client.py` (9.6KB) — Unified multi-provider LLM interface

### 6. Adapters Layer (`src/adapters/`)
- **Execution adapters**: MetaAPI, Paper, DryRun with router pattern
- **Data adapters**: Supabase, Redis, MarketData, Discord

### 7. Frontend (`frontend/src/`)
- **App Router**: 15 routes (dashboard, accounts, alerts, analytics, backtest, board, execution-quality, journal, positions, prop-firm, risk, rules, scanner, settings, strategies)
- **Components**: 22 component folders + shared UI primitives
- **Hooks**: 28 custom hooks — data fetching via TanStack Query
- **Lib**: API client (`api.ts` 24KB), Supabase client (`supabase.ts` 27KB), formatters, config
- **Providers**: React Query provider

## Data Flow

1. **Signal Ingestion**: TradingView webhook → `POST /webhook` → validate → Redis LPUSH
2. **Signal Processing**: Worker BRPOP → guard rails pipeline → AI/ML validation → execution decision
3. **Trade Execution**: Execution engine → MetaAPI adapter → broker → fill confirmation → Supabase persist
4. **Background Sync**: APScheduler tasks → MetaAPI polling → position/balance sync → Supabase update
5. **Frontend Data**: Next.js → TanStack Query → API endpoints / direct Supabase queries → React components

## Entry Points

- **Backend API**: `src/api.py` — `app = FastAPI()`
- **Worker**: `src/worker.py` — `python -m src.worker`
- **Frontend**: `frontend/src/app/layout.tsx` → `frontend/src/app/page.tsx`
- **Full stack**: `start.sh fullstack`
