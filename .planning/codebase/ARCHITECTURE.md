# Architecture

The system follows a Domain-Driven Design (DDD) styled Event-Driven microservices architecture. It is split into three primary services: Backend API, Worker, and Frontend.

## 1. Backend API (FastAPI)
- Acts as the receiver for external signals, primarily TradingView webhooks.
- Performs initial payload validation using Pydantic.
- Enforces rate limiting (using `slowapi`) to prevent DDoS or runaway signal firing.
- Pushes validated trading signals into a Redis queue.

## 2. Worker (Python)
- Asynchronously consumes signals from the Redis queue.
- Executes AI/ML Guardrails: Evaluates the signal quality using `lightgbm` models and LLM-based filter agents (Trading Council).
- Executes trades on MetaTrader via the MetaApi cloud SDK.
- Updates trade state, portfolio metrics, and risk status in Supabase.

## 3. Frontend (Next.js)
- Provides a real-time trading dashboard for human oversight.
- Features signal feeds, risk monitoring, and analytics.
- Communicates directly with Supabase for data and optionally with the Backend API for direct controls.

## Data Flow
- `TradingView` -> `HTTP POST` -> `Backend API` -> `Redis` -> `Worker` -> `AI Filters` -> `MetaApi (Broker)` -> `Supabase (Logs/State)` -> `Next.js Dashboard`.

## Key Abstractions
- **Guardrails**: Pluggable modules (AI Filter, ML Guardian, Trinity) that can short-circuit a trade execution if market conditions are deemed unfavorable.
- **Paper Trading Mode**: Configurable via environment variables to test execution logic without real capital.
