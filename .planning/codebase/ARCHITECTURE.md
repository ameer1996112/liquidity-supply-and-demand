# Codebase Architecture

## High-Level Pattern
The system follows an **Event-Driven Microservices-Lite** architecture. It is designed for institutional-grade reliability, utilizing a decoupled ingest-execution pipeline to handle high-frequency signals with multi-layered safety guardrails.

## Service Boundaries
- **Backend API (FastAPI)**: Serves as the high-availability ingestion layer. Its primary responsibility is to receive, validate, and queue signals from TradingView or other external providers.
- **Worker (Python)**: The core execution engine. It operates as a consumer, processing signals from the queue, applying complex AI/ML filters, enforcing risk guardrails, and managing trade lifecycles across multiple accounts.
- **Frontend (Next.js)**: A real-time dashboard for monitoring signal flow, account health, risk metrics, and manual overrides.
- **Infrastructure (Redis & Supabase)**:
    - **Redis**: Acts as the low-latency message broker between the API and Worker.
    - **Supabase**: Serves as the primary persistence layer for state, historical signals, audit logs, and dynamic configuration.

## Data Flow: Webhook to MetaTrader
1. **Signal Ingestion**: TradingView sends a `POST` request to the API's `/webhook` endpoint.
2. **Validation & Initial Persistence**: `src/api.py` validates the payload against a Pydantic schema and persists the raw signal to the `trading_signals` table in Supabase for immediate visibility.
3. **Queuing**: The signal is enqueued into a Redis list (managed via `src/adapters/redis_queue.py`).
4. **Processing**: The Worker (`src/worker.py`) pops signals from Redis.
5. **Guard Rails**: The Worker runs a series of global and account-specific guards (RiskEngine, NewsFilter, StalenessCheck, etc.).
6. **AI/ML Ensemble**: The signal is passed through the `Supervisor` and `Trading Council` (multi-agent system) to determine if it meets the confidence threshold for execution.
7. **Execution**: If cleared, `src/logic.py` uses the appropriate adapter (e.g., `MetaApiAdapter` or `PaperTrader`) to submit the order to the broker.
8. **Audit & Feedback**: The trade status is updated in Supabase, and notifications are sent via Discord/Slack.

## Key Abstractions & Design Patterns
- **Adapter Pattern**: Used extensively in `src/adapters/` to abstract communication with external services like MetaApi, Supabase, and Discord.
- **Guard Rail Strategy**: Risk and validation logic are implemented as pluggable "Guards" that can be enabled/disabled via configuration.
- **Observer Pattern**: Utilized in `src/core/observers/` for decoupled event auditing and metrics tracking.
- **ThreadPool Orchestration**: The Worker uses a `ThreadPoolExecutor` to process trades across multiple accounts in parallel without blocking the main signal loop.

## Entry Points
- **API**: `src/api.py` (FastAPI app)
- **Worker**: `src/worker.py` (Continuous loop consumer)
- **Frontend**: `frontend/src/app/` (Next.js App Router)

## Component Interaction Diagram
```text
[TradingView] --(JSON Webhook)--> [FastAPI (src/api.py)]
                                        |
                   (1) Write Signal     | (2) Push to Queue
                          v             v
                   [Supabase DB] <--- [Redis Queue]
                          |             |
                   (4) Read State       | (3) Pop Signal
                          |             v
                   [Next.js UI] <--- [Worker (src/worker.py)]
                                        |
                                 (5) Run Guard Rails
                                        |
                                 (6) AI Decisioning
                                        |
                                 (7) Execute Order
                                        v
                                 [MetaApi / MT5]
```
