# ARCHITECTURE.md — System Architecture

## Architectural Pattern

**Event-Driven Microservices with Guard Rail Pipeline**

The system follows a three-tier signal processing pipeline:
1. **Ingestion** — TradingView webhook → FastAPI validates → Redis queue
2. **Processing** — Worker consumes Redis queue → multi-layer AI/ML guardrails → broker execution
3. **Presentation** — Next.js dashboard subscribes to Supabase realtime for live updates

## Core Services

### 1. Backend API (`src/api.py` — 36KB)
- **Entry point**: FastAPI application
- **Role**: Webhook receiver + REST API for frontend
- **Port**: 8000
- **Key router modules** (each prefix-mounted):
  - `src/api_positions.py` — open positions management
  - `src/api_analytics.py` — PnL analytics, metrics
  - `src/api_risk.py` / `src/api_risk_monitor.py` — risk exposure
  - `src/api_portfolio.py` / `src/api_portfolio_control.py` (83KB) — portfolio management
  - `src/api_alerts.py` — alert configuration and history
  - `src/api_tickets.py` — Jira proxy + local ticket management
  - `src/api_copilot.py` — AI copilot / LLM queries
  - `src/api_ai_runs.py` — AI decision log
  - `src/api_backtests.py` — backtest execution
  - `src/api_execution.py` — manual order execution
  - `src/api_trades.py` — trade history

### 2. Worker (`src/worker.py` — 85KB)
- **Entry point**: `python -m src.worker`
- **Role**: Signal consumer + execution orchestrator
- **Pattern**: Blocking Redis pop (`BLPOP`) loop
- **Pipeline stages** (in order):
  1. Dequeue signal from Redis
  2. Validate with `ConsumerValidator`
  3. Apply Pine-matching pre-filters (`PineGuardian`)
  4. Staleness guard (reject stale signals)
  5. AI Guardian (LLM validation)
  6. ML Guardian (LightGBM win probability)
  7. Trinity Engine (position/drawdown limits)
  8. Market filter (news, session timing)
  9. Correlation + VaR guards
  10. Risk Engine (position sizing)
  11. Execute (MetaAPI / Paper / Shadow)
  12. Notify (Discord + Telegram)
  13. Persist to Supabase

### 3. Frontend (`frontend/` — Next.js 16)
- **Entry point**: `frontend/src/app/layout.tsx`
- **Port**: 3000
- **Pattern**: App Router (React Server + Client Components)
- **Pages**:
  - `/` — Main dashboard (signals feed, account summary)
  - `/positions` — Open positions
  - `/analytics` — PnL charts and metrics
  - `/risk` — Risk exposure
  - `/accounts` — Multi-account management
  - `/alerts` — Alert configuration
  - `/backtest` — Strategy backtesting UI
  - `/tickets` — Jira-like project board
  - `/strategies`, `/scanner`, `/journal`, etc.

## Data Flow

```
TradingView Pine Script
       │ POST /webhook
       ▼
FastAPI API (port 8000)
  ├── Validates payload
  ├── Checks WEBHOOK_SECRET
  └── LPUSH → Redis queue
              │
              ▼
        Worker (BLPOP)
  ├── ConsumerValidator
  ├── PineGuardian (pre-filter)
  ├── StalenessGuard
  ├── AI Guardian (LLM)
  ├── ML Guardian (LightGBM)
  ├── Trinity Engine (risk limits)
  ├── MarketFilter (news/session)
  ├── CorrelationGuard + VaR
  ├── RiskEngine (position sizing)
  ├── Execute → MetaAPI / Paper
  ├── Discord + Telegram notify
  └── Persist → Supabase
              │
              ▼
        Supabase (PostgreSQL)
              │ realtime
              ▼
     Next.js Frontend (port 3000)
```

## Key Abstractions

### Signal (`src/core/signal.py`)
Core data model passed through the entire pipeline. Contains: `symbol`, `side`, `entry`, `sl`, `tp`, `size`, plus Pine metadata (`zone_score`, `grade`, `entry_type`, `departure_strength`, etc.)

### Guard Rails (`src/core/guard_rails/`)
Each guard is an independent filter that returns APPROVE / REJECT / WARNING:
- `pine_guardian.py` — Pine Script rule mirroring (score, grade, tiering)
- `staleness_guard.py` — Rejects signals older than `staleness_max_age_seconds`
- `correlation.py` — Cross-position correlation matrix
- `market_filter.py` — News events, session hours, dead zone
- `portfolio_var_guard.py` — Portfolio Value-at-Risk limit
- `sector_guard.py` — Sector exposure limits
- `prop_guard.py` — Prop firm evaluation mode guardrails

### Observer Pattern (`src/core/observers/`)
Worker emits lifecycle events that observers handle (Discord alerts, Supabase persistence, watchdog updates).

### Account Router (`src/core/account_router.py`)
Routes signals to correct broker account in multi-account (Package A) mode using `BROKER_PROFILES_JSON`.

### Transport (`src/core/transport.py`)
Abstraction over signal queue: `redis` (production) or `memory` (unit tests). Controlled by `SIGNAL_TRANSPORT` env var.

## Background Services

| Service | File | Role |
|---|---|---|
| MTM Guardian | `src/services/mtm_guardian.py` | Real-time floating PnL monitoring |
| TradeWatchdog | `src/services/watchdog.py` | Detects late fills, stuck trades |
| BackgroundSyncWorker | `src/services/background_sync_worker.py` | MetaAPI account polling |
| BreakevenManager | `src/services/breakeven_manager.py` | Auto-BE on profit trigger |
| TrailingStopManager | `src/services/trailing_stop_manager.py` | Trailing stop enforcement |
| DailyResetScheduler | `src/services/daily_reset_scheduler.py` | EOD stat reset |
| AlertEngine | `src/services/alert_engine.py` | Configurable price/metric alerts |
| TCAAnalyzer | `src/services/tca_analyzer.py` | Transaction cost analysis |

## AI/ML Pipeline

```
Signal
  ├── AI Guardian (LLM) ─────────────────────────────→ APPROVE/REJECT/WARNING
  │     ├── Quick tier (llama-3.1-8b-instant)
  │     └── Deep tier (llama-3.3-70b-versatile) on escalation
  │
  ├── ML Guardian (LightGBM)──────────────────────────→ win probability score
  │     ├── Adaptive threshold (floor + margin over model base win-rate)
  │     └── Per-entry-type models (FLIP, BREAK_CANDLE, DIR_CLOSE)
  │
  ├── Trading Council (multi-agent debate) ──────────→ persisted to ai_runs
  │     ├── Bull agent
  │     ├── Bear agent
  │     ├── Risk agent
  │     └── Chair (synthesis)
  │
  └── RAG Engine (BM25 + LangChain) ─────────────────→ context for LLM calls
        └── Memory Service (reflection on closed trades)
```

## Deployment Architecture

- **API + Worker + Frontend** can run together via `./start.sh fullstack`
- **Railway** cloud deployment (separate services per `railway.json`)
- **Docker Compose** for local development
- Redis must be running before API starts (fail-fast check on `startup`)
- `PYTHONPATH=/workspace` required when running outside `start.sh`
