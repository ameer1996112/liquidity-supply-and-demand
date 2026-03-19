# ARCHITECTURE.md — System Architecture

## Overview

Event-driven, producer-consumer trading system. TradingView webhooks trigger signals that flow through a multi-layered AI/ML guardrail pipeline before being executed on live broker accounts.

## Pattern: Decoupled Producer-Consumer

```
TradingView
    │
    ▼ POST /webhook
┌──────────────┐
│  FastAPI     │  ← Signal receiver, REST API
│  (API)       │  → Supabase (persist raw signal)
│  port 8000   │  → Redis (enqueue for processing)
└──────────────┘
        │
        │ Redis Queue
        ▼
┌──────────────┐
│  Worker      │  ← Signal consumer, Guardrail pipeline
│  (Worker)    │  → Execution adapters (MetaAPI / Paper)
│  Python      │  → Supabase (persist results, traces)
└──────────────┘
        │
        ├─ MetaAPI (live broker)
        ├─ PaperTrader (simulation)
        └─ Discord/Telegram (notifications)
```

## Core Layers

### 1. API Layer (`src/api.py` + `src/api_*.py`)
- Single monolithic `api.py` entry point (30KB) that mounts sub-routers
- ~20 sub-router modules: `api_accounts.py`, `api_analytics.py`, `api_risk.py`, `api_positions.py`, etc.
- Webhook acceptance → validation → Supabase persist → Redis enqueue
- REST endpoints for frontend dashboard (accounts, analytics, risk, positions, traces, etc.)
- Rate limiting via slowapi; CORS configured via `FRONTEND_URL`

### 2. Worker / Pipeline (`src/worker.py`)
Massive single-file worker (82KB) that runs the full signal processing pipeline:

```
Signal dequeued from Redis
    │
    ▼
[Global Guards]
    ├─ Staleness Guard (signal age check, price deviation)
    ├─ Kill Switch check
    └─ Market filter (news/session)
    │
    ▼
[Account Routing] → src/core/account_router.py
    │ (per account)
    ▼
[AI Ensemble]
    ├─ AI Guardian (quick LLM check, confidence score)
    ├─ ML Guardian (LightGBM win probability)
    ├─ Trinity Risk Engine (drawdown/daily loss limits)
    ├─ Portfolio VaR Guard
    ├─ Sector Guard
    ├─ Correlation Guard
    └─ Prop Guard (FTMO challenge limits)
    │
    ▼
[Execution Adapter]
    ├─ MetaAPI Adapter → MetaTrader 5 (live)
    └─ Paper Trader → In-memory (simulation)
    │
    ▼
[Observers / Post-processing]
    ├─ TCA (Transaction Cost Analysis)
    ├─ Trace recording
    └─ Notification dispatch
```

### 3. AI/ML Layer (`src/ai/`)

| File | Purpose |
|------|---------|
| `brain.py` (59KB) | Orchestrates entire AI ensemble |
| `trading_council.py` (38KB) | Multi-agent LLM debate ("Bull" vs "Bear" vs "Neutral") |
| `ai_guardian.py` (26KB) | Single-pass LLM confidence scoring |
| `ml_guardian.py` (20KB) | LightGBM technical analysis scoring |
| `debate.py` | Council debate logic |
| `rag_engine.py` | BM25 retrieval for trade memory context |
| `council_memory.py` | Stores/retrieves past similar trade situations |
| `llm_client.py` | Unified LLM client (OpenAI/Anthropic/Groq) |
| `features.py` | Feature engineering for ML |

### 4. Core Domain (`src/core/`)

| File | Purpose |
|------|---------|
| `risk_engine.py` (17KB) | Position sizing (Kelly, fixed %), R:R validation |
| `transport.py` (10KB) | Signal queue abstraction (Redis or in-memory) |
| `dynamic_config.py` (12KB) | Runtime configurable settings |
| `guard_rails/` | Individual guard modules |
| `signal.py` | Signal domain model |
| `account_router.py` | Routes signals to correct broker accounts |
| `broker_profiles.py` | Symbol mapping per broker |
| `consumer_validator.py` | Validates incoming webhook payload |

### 5. Adapters Layer (`src/adapters/`)

| Adapter | Purpose |
|---------|---------|
| `execution/meta_api_adapter.py` | MetaTrader 5 via MetaAPI cloud |
| `paper_trader.py` (11KB) | Simulated execution |
| `supabase.py` (41KB) | All database operations |
| `discord.py` (12KB) | Discord notifications |
| `market_data.py` (9KB) | yfinance market data |
| `redis_queue.py` (3KB) | Redis queue operations |

### 6. Frontend (`frontend/src/`)

Next.js 15 App Router, domain-driven structure:

```
frontend/src/
├── app/              # Page routes (App Router)
│   ├── page.tsx      # Main dashboard (22KB)
│   ├── accounts/     # Account management
│   ├── analytics/    # Analytics dashboard
│   ├── execution-quality/  # TCA + trace viewer
│   ├── positions/    # Open positions
│   ├── risk/         # Risk monitoring
│   ├── prop-firm/    # Prop firm tracking
│   ├── backtest/     # ML backtesting
│   ├── board/        # Kanban board
│   └── settings/     # Configuration
├── components/       # Shared UI components
│   ├── dashboard/    # Dashboard panels (SignalInspector, RecentSignals, etc.)
│   └── execution/    # Trade trace components (TraceTable, etc.)
├── domain/           # Core domain models (TypeScript)
│   └── metrics/      # Trading metrics calculations
├── hooks/            # Custom React hooks
├── lib/              # Utilities (Supabase client, API client)
├── providers/        # Context providers (Auth, QueryClient, WebSocket)
└── types/            # TypeScript type definitions
```

## Data Flow: Signal Lifecycle

1. **TradingView** fires webhook → `POST /webhook`
2. **API** validates, persists to Supabase (`signals` table), enqueues to Redis
3. **Worker** pops signal, runs global guards
4. Per account: AI ensemble evaluates signal → result: APPROVE/REJECT
5. If approved: execution adapter places order at broker
6. Post-execution: TCA analysis, trace recorded, notification sent
7. **Frontend** sees updates via Supabase Realtime + React Query polling

## Key Design Decisions

- **Fail-open by default:** AI/ML guards are designed to fail open (allow trade) on error, preventing AI timeouts from blocking execution
- **Fast-path bypass:** High-confidence signals can bypass some guards for speed
- **Single worker file:** All pipeline logic in `worker.py` (82KB) — functional, but growing unwieldy
- **Multi-broker routing:** Symbol type determines which broker account to use (Forex → Vantage, Metals/Indices → FXCM/IC Markets)
