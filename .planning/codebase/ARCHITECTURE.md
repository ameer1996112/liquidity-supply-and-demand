# ARCHITECTURE.md — System Architecture

## Overview

Three decoupled services communicating via Redis and Supabase:

```
TradingView ──webhook──▶ API (FastAPI :8000)
                              │
                         Redis Queue
                              │
                         Worker (Python)
                              │ ├─ AI Ensemble
                              │ ├─ Guard Rails
                              │ └─ Account Router
                              │
                    ┌─────────┴─────────┐
                MetaAPI               Supabase
              (broker/MT4)           (persistence)
                              ▲
                         Frontend (Next.js :3000)
                              │
                        Supabase Realtime
```

## Service Details

### 1. Backend API (`src/api.py`, port 8000)
- **FastAPI** with multiple routers mounted from separate `src/api_*.py` modules
- **Responsibilities:**
  - Receive TradingView webhooks (`POST /webhook`)
  - Validate payload (Pydantic `EntryWebhookPayload` in `src/core/signal.py`)
  - Write signal to `trading_signals` with status `"RECEIVED"`
  - Push to Redis queue via `src/core/transport.py`
  - Serve all REST endpoints for the frontend

### 2. Worker (`src/worker.py`)
- **Single Python process** consuming from Redis queue in a loop
- **Two-phase guard structure:**
  - **Global guards** (run once per signal):
    - Kill switch (env `TRADING_KILL_SWITCH`)
    - Staleness guard (`src/core/guard_rails/staleness_guard.py`) 
    - AI Ensemble / Trinity council (`src/ai/`)
  - **Per-account guards** (run inside `ThreadPoolExecutor` per account):
    - Circuit breaker (`src/core/circuit_breaker.py`)
    - PropGuard (`src/core/guard_rails/prop_guard.py`)
    - Correlation guard (`src/core/guard_rails/correlation.py`)
    - VaR guard (`src/core/guard_rails/portfolio_var_guard.py`)
    - Sector guard (`src/core/guard_rails/sector_guard.py`)
- **Observer pattern** (`src/core/observers/`): Auditor, Risk, Executor, Metrics, AccountRouter observers
- **Account Router** (`src/core/account_router.py`): maps signals to MetaAPI accounts
- **Execution:** `src/logic.py` → `src/adapters/metaapi.py`

### 3. Frontend (`frontend/`, port 3000)
- **Next.js 16 App Router** — pages in `frontend/src/app/`
- **Data pattern:** React hooks in `frontend/src/hooks/` wrapping react-query + fetch
- **Realtime:** Supabase JS client for live signal feed updates
- **No server-side logic** — pure client-side data fetching

## Signal Data Flow

```
1. TradingView fires alert
2. POST /webhook → EntryWebhookPayload validated
3. Signal written to Supabase (status=RECEIVED)
4. Signal pushed to Redis queue
5. Worker dequeues signal
6. Global guards run (staleness, kill-switch, AI)
7. Account Router resolves accounts for this signal
8. Per-account: circuit breaker + prop guards run
9. Risk engine calculates lot size
10. MetaAPI executes trade
11. Signal updated in Supabase (status=EXECUTED)
12. Frontend polls / receives realtime update
```

## Key Abstractions

| Abstraction | Location | Purpose |
|-------------|----------|---------|
| `EntryWebhookPayload` | `src/core/signal.py` | Webhook schema |
| `Settings` | `config/settings.py` | All env config, cached via `@lru_cache` |
| `get_transport()` | `src/core/transport.py` | Redis vs memory queue abstraction |
| Guard rails | `src/core/guard_rails/` | Plugin-style risk checks |
| Observer pattern | `src/core/observers/` | Side effects (audit, metrics, routing) |
| `AccountRouter` | `src/core/account_router.py` | Maps signals to broker accounts |
| `calculate_max_position_size` | `src/core/risk_engine.py` | Lot size from account balance + risk% |

## API Router Structure

```
src/api.py               — Main app, /webhook, /webhook/test, /health
src/api_analytics.py     — /analytics/* (equity curve, drawdown, strategy)
src/api_risk.py          — /risk/*
src/api_positions.py     — /positions/*
src/api_funding.py       — /funding/*
src/api_evaluation.py    — /evaluation/*
src/api_execution.py     — /execution/*
src/api_rules.py         — /rules/* (dynamic config)
src/api_backtests.py     — /backtests/*
src/api_strategies.py    — /strategies/*
src/api_board.py         — /board/*
src/api_portfolio_control.py — /portfolio/*
src/api_copilot.py       — /copilot/*
src/api_traces.py        — /traces/*
```
