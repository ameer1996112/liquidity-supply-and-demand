# Technology Stack

## Languages & Runtimes

| Layer | Language | Runtime |
|-------|----------|---------|
| Backend API | Python 3 | uvicorn (ASGI) |
| Worker | Python 3 | Standalone process |
| Frontend | TypeScript | Node.js >=20.9 (Next.js) |

## Backend Dependencies

### Core Framework
- **FastAPI** >=0.109.0 — ASGI web framework, async support
- **uvicorn[standard]** >=0.27.0 — ASGI server
- **pydantic-settings** >=2.0.0 — Type-safe config via `config/settings.py`
- **python-dotenv** >=1.0.0 — `.env` file loading

### Data & Queue
- **redis** >=5.0.0 — Signal queue + caching (Redis 7 Alpine in Docker)
- **supabase** ==2.10.0 — PostgreSQL database (hosted Supabase)
- **apscheduler** >=3.10.0 — Background task scheduling
- **slowapi** >=0.1.9 — Rate limiting

### AI/ML Layer
- **scikit-learn** ==1.7.2 — ML models (Random Forest classifiers)
- **lightgbm** >=4.0.0 — Gradient boosting (memory-efficient)
- **numpy** >=1.24.0, **pandas** >=2.0.0, **pyarrow** >=14.0.0 — Data processing
- **numba** >=0.58.0 — JIT compilation for backtesting
- **openai** >=1.0.0, **anthropic** >=0.18.0 — LLM providers
- **langchain** >=0.2.0 + community + openai — RAG pipeline
- **tiktoken** >=0.7.0 — Token counting
- **rank-bm25** >=0.2 — Trading Council BM25 retrieval
- **yfinance** >=0.2.36 — Market data fetching

### Backtesting & Visualization
- **backtesting** >=0.3.3 — Strategy backtesting framework
- **plotly** >=5.18.0 — Analytics visualizations
- **optuna** >=3.5.0 — Bayesian hyperparameter optimization
- **lightweight-charts** >=2.0.0 — TradingView-style charts (Python)

### Notifications
- **requests** >=2.28.0 — HTTP client (Discord webhooks, external APIs)

## Frontend Dependencies

### Core
- **Next.js** 16.1.6 — React framework (App Router)
- **React** 19.2.3 — UI library
- **TypeScript** ^5 — Type safety

### Styling
- **TailwindCSS** ^4 — Utility-first CSS
- **tw-animate-css** ^1.4.0 — Animation utilities

### UI Components
- **@radix-ui** — Headless primitives (dialog, popover, scroll-area, separator, slot, tabs, tooltip)
- **lucide-react** ^0.563.0 — Icon library
- **class-variance-authority** ^0.7.1 — Variant management
- **clsx** ^2.1.1 + **tailwind-merge** ^3.4.0 — Class merging

### Data
- **@tanstack/react-query** ^5.90.20 — Server state management
- **@tanstack/react-table** ^8.21.3 — Data tables
- **@supabase/supabase-js** ^2.93.3 — Direct Supabase client
- **lightweight-charts** ^5.1.0 — TradingView charts (JS)
- **recharts** ^3.7.0 — React charting
- **date-fns** ^4.1.0 — Date utilities

### Testing
- **vitest** ^3.2.4 — Test runner
- **jsdom** ^27.0.1 — DOM environment for tests

## Configuration

- **Settings**: `config/settings.py` — Pydantic BaseSettings (431 lines, 100+ config fields)
- **Environment**: `.env` at project root, loaded via `pydantic-settings`
- **Caching**: `@lru_cache` on `get_settings()` — requires process restart for changes
- **Logging**: `config/logging_config.py` — Structured logging configuration

## Deployment

- **Platform**: Railway (nixpacks-based)
- **Containers**: Docker Compose with 4 services (redis, backend, worker, frontend)
- **Dockerfiles**: `Dockerfile.api`, `Dockerfile.worker`, `frontend/Dockerfile`
- **Nixpacks configs**: `nixpacks.toml` (API), `nixpacks.worker.toml` (Worker)
