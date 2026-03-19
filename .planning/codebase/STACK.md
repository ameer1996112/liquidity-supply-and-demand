# STACK.md — Technology Stack

## Languages & Runtime

| Layer | Language | Runtime |
|-------|----------|---------|
| Backend API | Python 3.10+ | CPython |
| Worker | Python 3.10+ | CPython |
| Frontend | TypeScript 5 | Node 20+ / Browser |
| ML | Python 3.10+ | CPython + Numba JIT |

## Backend (Python)

### Core Framework
- **FastAPI** ≥0.109.0 — REST API, webhook receiver
- **Uvicorn** ≥0.27.0 (with standard extras) — ASGI server
- **Pydantic** / **pydantic-settings** ≥2.0.0 — config and data validation
- **APScheduler** ≥3.10.0 — background job scheduling (e.g., broker reconciliation)
- **slowapi** ≥0.1.9 — rate limiting middleware (wraps `limits`)

### Data & Storage
- **redis** ≥5.0.0 — signal queue (API→Worker) + caching
- **supabase** ==2.10.0 — PostgreSQL database + Realtime + Auth
- **pandas** ≥2.0.0 — data manipulation
- **pyarrow** ≥14.0.0 — efficient data serialization

### Machine Learning
- **scikit-learn** ==1.7.2 — ML Guardian (classification models)
- **lightgbm** ≥4.0.0 — gradient boosting (memory-efficient, replaces RandomForest)
- **numpy** ≥1.24.0 — numerical operations
- **numba** ≥0.58.0 — JIT compilation for backtesting performance
- **optuna** ≥3.5.0 — Bayesian hyperparameter optimization
- **backtesting** ≥0.3.3 — Python backtesting framework

### AI / LLM
- **openai** ≥1.0.0 — OpenAI + Groq API client (openai-compatible)
- **anthropic** ≥0.18.0 — Claude API client
- **langchain** ≥0.2.0 — LLM orchestration
- **langchain-community** ≥0.2.0
- **langchain-openai** ≥0.1.0
- **tiktoken** ≥0.7.0 — token counting
- **rank-bm25** ≥0.2 — BM25 retrieval for Trading Council memory

### Market Data
- **yfinance** ≥0.2.36 — historical market data (technical analysis for ML)
- **MetaApi cloud SDK** — live broker price feed + order execution

### Scraping / Analysis
- **beautifulsoup4** + **lxml** — HTML parsing
- **youtube-transcript-api** + **scrapetube** — strategy research scraping

### Utilities
- **requests** ≥2.28.0 — HTTP client
- **python-dotenv** ≥1.0.0 — `.env` loading
- **pytz** ≥2023.3 — timezone handling
- **plotly** ≥5.18.0 — analytics charts
- **streamlit** ≥1.28.0 — internal ML dashboards

## Frontend (Next.js)

### Core Framework
- **Next.js 15** (App Router) — React SSR/SSG framework
- **React 19** — UI library
- **TypeScript 5** — type safety

### UI & Styling
- **Tailwind CSS** — utility-first styling
- **Radix UI** — accessible headless component primitives
- **shadcn/ui** — component library built on Radix
- **lightweight-charts** — TradingView-style candlestick charts
- **recharts** — general charting (analytics, heatmaps)

### Data Fetching & State
- **TanStack React Query** (@tanstack/react-query) — server state, caching, polling
- **Supabase JS client** (@supabase/supabase-js) — auth + Realtime subscriptions

### Testing
- **Vitest** — unit/integration test runner
- **@testing-library/react** — component testing utilities

### Linting
- **ESLint** with `eslint-config-next` — configured in `frontend/eslint.config.mjs`

## Infrastructure / Deployment

### Local
- Python venv at `venv/` (also referenced as `/workspace/.venv` in CI/Docker)
- Redis running on `localhost:6379`
- `start.sh` orchestrates API + Worker + Frontend

### Docker
- `Dockerfile` (combined), `Dockerfile.api`, `Dockerfile.worker`
- `docker-compose.yml` — full-stack local compose

### Cloud (Railway)
- `railway.json` — Railway deployment config
- `nixpacks.toml` / `nixpacks.worker.toml` — Nixpacks build specs

## Configuration System

- Root `.env` — backend + worker config (loaded by `config/settings.py`)
- `frontend/.env` — frontend NEXT_PUBLIC_* vars (baked at build time)
- `config/settings.py` — Pydantic Settings model with `@lru_cache`
- `.env.example` — full reference with 264 lines documenting all variables

## Key Environment Variable Categories
| Category | Key Vars |
|---------|---------|
| Required | `SUPABASE_URL`, `REDIS_URL` |
| Auth | `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `WEBHOOK_SECRET` |
| AI/LLM | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AI_MODEL`, `AI_FILTER_ENABLED` |
| ML | `ML_GUARDIAN_ENABLED`, `ML_MIN_CONFIDENCE` |
| Broker | `META_API_TOKEN`, `META_API_ACCOUNT_ID`, `META_API_REGION` |
| Trading | `LIVE_TRADING`, `RUN_MODE`, `TRADING_KILL_SWITCH` |
| Risk | `TRINITY_ENABLED`, `RISK_PERCENT`, `MIN_RR_RATIO`, `MAX_LOT_SIZE` |
| Prop Firm | `EVALUATION_MODE`, `PHASE1_*`, `TRINITY_MAX_DAILY_LOSS_PCT` |
| CORS | `FRONTEND_URL` |
