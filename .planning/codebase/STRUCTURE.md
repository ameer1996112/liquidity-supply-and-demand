# Directory Layout & Structure

## Root Level
- `src/`: Root for the Python Backend (API & Worker).
- `frontend/`: Root for the Next.js Frontend Dashboard.
- `tests/`: Root for Python test suites.
- `config/`, `data/`, `docs/`, `migrations/`, `ml/`, `scripts/`: Various backend support directories.
- `plans/`, `.agent/`, `.planning/`: GSD and agent planning artifacts.
- `docker-compose.yml`, `Dockerfile.*`, `Makefile`: DevOps and orchestration files.

## Backend (`src/`)
- `api.py`: Main FastAPI application initialization.
- `api_*.py`: Feature-specific API routers (e.g., `api_analytics.py`, `api_webhook_read.py`). Breaking these down keeps `api.py` manageable.
- `worker.py`: Main entry point for the background processing worker.
- `logic.py`: Shared business logic.
- `core/`: Core trading domain logic.
  - `guard_rails/`: Circuit breakers, news filters, AI staleness guards.
  - `observers/`: Event listeners / telemetry.
  - `risk_engine.py`, `account_router.py`: Risk management and routing.
- `adapters/`: External system integrations (brokers, specific APIs).
- `agents/`: Dedicated AI agent wrappers or system prompt logic.
- `ai/`: ML models, LangChain implementations, or specialized LLM logic.
- `services/`: Specialized backend services (e.g., ticket proxy, database layer).

## Frontend (`frontend/src/`)
Uses the modern Next.js App Router pattern combined with Domain-Driven concepts.
- `app/`: Next.js file-system routing (pages, layouts).
- `components/`: Shared UI components (often Radix/Tailwind primitives).
- `domain/`: Business logic, custom hooks, and types separated by feature (e.g., tickets, analytics, health).
- `hooks/`: Shared React hooks (e.g., general react-query wrapping).
- `lib/`: Utility functions, API clients, `utils.ts` for Tailwind merge.
- `providers/`: React Context providers (QueryClient provider, Theme provider).
- `types/`: Global TypeScript definitions.

## Testing (`tests/`)
- tests are separated by scope, often named `test_*.py`. Contains unit, integration, and e2e testing suites.
