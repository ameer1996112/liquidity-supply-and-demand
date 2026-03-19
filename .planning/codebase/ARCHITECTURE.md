# Architecture

## Pattern

**Event-driven, multi-process pipeline with observer pattern.**

Two independent services communicate via Redis queue:
1. **API Service** (`src/api.py`) — FastAPI HTTP server that validates webhooks and enqueues signals
2. **Worker Service** (`src/worker.py`) — Consumer that dequeues signals, runs guard chain, executes trades

Frontend is a Next.js application that talks to the API via REST. Real-time updates via WebSocket from the API.

## Layers

### Backend

```
TradingView Webhook
       ↓
[API Service] — validate → enqueue to Redis
       ↓
[Redis Queue] — message bus
       ↓
[Worker/Consumer] — dequeue → guard chain → execute
       ↓
[Supabase DB] — persistence
       ↓
[MetaAPI] — broker execution (MT5)
```

### Frontend

```
Next.js App (App Router)
├── /app pages (route handlers)
├── /components (feature-organized)
├── /hooks (data fetching: useX.ts)
├── /domain (business types/models)
├── /lib (utilities)
└── /providers (context providers)
```

## Guard Chain (Worker)

Signals flow through a sequential guard chain before execution:

**Global guards (once per signal):**
1. Kill-switch (env)
2. Max lot size cap
3. Staleness guard
4. AI ensemble (RF model + RAG + LLM debate council)

**Per-account guards (parallel accounts via ThreadPoolExecutor):**
1. Kill-switch (Redis/MTM)
2. Circuit breaker
3. PropGuard (prop firm rules)
4. Correlation guard
5. VaR guard
6. Sector guard
7. Consistency analyzer

**Execution:**
- `logic.process_trade()` → ExecutionEngine → adapter → MetaAPI

## Observer Pattern

`WorkerSubject` in `src/core/observers/` broadcasts events to:
- `AuditorObserver` — logs trade events
- `RiskObserver` — risk checks
- `ExecutorObserver` — execution
- `MetricsObserver` — metrics tracking
- `AccountRouterObserver` — multi-account routing

## AI Ensemble (`src/ai/`)

Three-layer AI decision system:
- **ML Guardian** — Random Forest model (scikit-learn) on 20 engineered features
- **RAG Engine** — retrieves historical trade context
- **Debate Council** — LLM-based multi-agent deliberation (OpenAI)
- **Brain** — Ensemble v9.1: aggregates RF + RAG + LLM votes

## Data Flow

1. TradingView sends webhook → `POST /webhook` on API
2. API validates payload via `src/core/signal.py`, pushes to Redis
3. Worker pops from Redis, runs through guard chain
4. On pass: `logic.process_trade()` calls `ExecutionEngine` → MetaAPI
5. Trade saved to Supabase with full TCA metrics
6. Frontend polls REST APIs / WebSocket for live updates

## Entry Points

- **API:** `src/api.py` — FastAPI app, registered routers for every domain
- **Worker:** `src/worker.py` — Long-running consumer loop
- **Frontend:** `frontend/src/app/layout.tsx` → `frontend/src/app/page.tsx`

## Key Abstractions

- `src/core/transport.py` — signal transport abstraction (Redis/memory/HTTP)
- `src/adapters/execution/router.py` — execution adapter router (live/paper)
- `src/adapters/supabase.py` — database adapter
- `src/adapters/metaapi.py` — broker adapter
- `src/core/risk_engine.py` — pure risk domain (no I/O)
- `src/services/execution_engine.py` — TCA-wrapped execution
