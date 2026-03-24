# System Architecture

## High-Level Pattern
The system follows a typical **Event-Driven Microservices Architecture**, decoupled via a Redis message broker, alongside a **Domain-Driven** directory structure in both the backend and frontend.

## Components & Layers

### 1. Backend Web API (FastAPI)
- **Role**: Entry point for external signals and frontend requests.
- **Entry Point**: `src/api.py` and various `src/api_*.py` routing modules.
- **Data Flow**: Receives trading signals (e.g., from TradingView webhooks), validates them using Pydantic, and pushes them into a Redis queue. It also serves REST endpoints for the frontend dashboard (e.g., analytics, portfolio, tickets).

### 2. Trading Worker (Python Background Process)
- **Role**: The execution engine that processes signals asynchronously.
- **Entry Point**: `src/worker.py`.
- **Data Flow**: Consumes signals from Redis. Runs them through a pipeline of validations, risk checks (`src/core/risk_engine.py`), and AI guardrails (`src/core/guard_rails/`, `src/ai/`). If a signal passes all checks, the worker executes the trade via broker adapters (`src/adapters/`).

### 3. Frontend Web App (Next.js)
- **Role**: Real-time trading dashboard and admin interface.
- **Entry Point**: `frontend/src/app/` (Next.js App Router).
- **Architecture**: Domain-driven/Feature-based components, using `react-query` for state management and data fetching. It communicates with the Backend API for trading logic and directly with Supabase for some data/auth.

## Data Flow (Trading Signal Lifecycle)
1. **Ingestion**: Webhook hits FastAPI `POST /webhook` (`src/api_webhook_read.py`).
2. **Validation**: FastAPI validates payload (symbol, side, entry, sl, tp, size).
3. **Queuing**: Payload is pushed to a Redis List/Stream.
4. **Processing**: `worker.py` pops the signal from Redis.
5. **Enrichment & Guardrails**: The signal goes through ML models, LLM debates (Trading Council), and risk engines (circuit breakers).
6. **Execution**: The signal is routed to the appropriate broker profile (`src/core/account_router.py`) and executed via the broker API.
7. **Persistence & Telemetry**: Trade results and logs are stored in Supabase and pushed to external Discord/Telegram alerts.
