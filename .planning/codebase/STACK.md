# STACK.md — Technology Stack

## Languages & Runtimes

| Layer | Language | Runtime |
|---|---|---|
| Backend API | Python 3.11 | CPython (venv at `.venv/`) |
| Worker | Python 3.11 | CPython (venv at `.venv/`) |
| Frontend | TypeScript | Node.js ≥20.9 |
| Pine Script | Pine Script v5 | TradingView cloud |

## Backend Frameworks & Libraries

### Web Framework
- **FastAPI** ≥0.109.0 — REST API, webhook receiver
- **Uvicorn** ≥0.27.0 — ASGI server (standard extras)
- **SlowAPI** ≥0.1.9 — Rate limiting (wraps `limits` library)
- **APScheduler** ≥3.10.0 — Background scheduled jobs (daily reset, sync)

### Data / ML
- **scikit-learn** 1.7.2 — Classic ML models (RandomForest)
- **LightGBM** ≥4.0.0 — Gradient boosting (memory-efficient, replaces RF for ML Guardian)
- **NumPy** ≥1.24.0 / **Pandas** ≥2.0.0 / **PyArrow** ≥14.0.0
- **Numba** ≥0.58.0 — JIT compilation for backtesting loops
- **Backtesting** ≥0.3.3 — Python backtesting framework
- **Optuna** ≥3.5.0 — Bayesian hyperparameter optimization

### AI / LLM / RAG
- **OpenAI** ≥1.0.0 — GPT models (primary or fallback)
- **Anthropic** ≥0.18.0 — Claude models
- **LangChain** ≥0.2.0 + **langchain-openai** + **langchain-community** — LLM orchestration, RAG pipeline
- **Tiktoken** ≥0.7.0 — Token counting
- **rank-bm25** ≥0.2 — BM25 retrieval for Trading Council RAG

### Infrastructure
- **Redis** ≥5.0.0 — Signal queue (primary transport, fail-fast checked on boot)
- **Supabase** 2.10.0 — PostgreSQL database client (Python)
- **Pydantic-settings** ≥2.0.0 — Typed configuration from env/`.env`
- **Requests** ≥2.28.0 — HTTP client for MetaAPI, Discord, external calls
- **python-dotenv** ≥1.0.0 — .env loader

### Data Enrichment
- **yfinance** ≥0.2.36 — Yahoo Finance market data
- **BeautifulSoup4 + lxml** — HTML scraping (news filter)
- **youtube-transcript-api + scrapetube** — YouTube transcript ingestion for RAG
- **Streamlit** ≥1.28.0 — Internal dashboards / ML notebooks
- **Plotly** ≥5.18.0 / **Lightweight-charts** ≥2.0.0 — Chart libraries

## Frontend Stack

### Core Framework
- **Next.js** 16.1.6 — App Router (React 19)
- **React** 19.2.3 + **react-dom**
- **TypeScript** ≥5

### UI
- **Tailwind CSS** v4 (@tailwindcss/postcss)
- **Radix UI** — Headless components: dialog, popover, scroll-area, separator, slot, tabs, tooltip
- **Lucide React** ^0.563.0 — Icon set
- **class-variance-authority**, **clsx**, **tailwind-merge** — Class utilities
- **tw-animate-css** — Tailwind animation utilities

### Data / State
- **@tanstack/react-query** v5 — Server state management, polling
- **@tanstack/react-table** v8 — Data table management
- **@supabase/supabase-js** v2 — Realtime and DB queries from browser

### Charts / Visualization
- **lightweight-charts** v5 — TradingView-style candlestick/line charts
- **Recharts** v3 — React chart components (bar, pie, area)

### Testing / DevTools
- **Vitest** v3 — Unit test runner
- **jsdom** — DOM environment for tests
- **@tanstack/react-query-devtools** — Query inspector

## Configuration Management

- **Settings class** in `config/settings.py` using `pydantic-settings` `BaseSettings`
- `.env` at project root loaded via `SettingsConfigDict(env_file=...)`
- **`@lru_cache` on `get_settings()`** — singleton per process; restart required for `.env` changes
- Env aliases via `AliasChoices` (multiple env var names map to same setting)
- Required vars: `SUPABASE_URL`, `REDIS_URL` (fail-fast on missing)
- Optional critical: `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `META_API_TOKEN`, `AI_API_KEY`

## Build & Packaging

| Tool | Purpose |
|---|---|
| `pip` + `requirements.txt` | Backend deps |
| `npm` + `package-lock.json` | Frontend deps (Node ≥20.9) |
| `Dockerfile` / `Dockerfile.api` / `Dockerfile.worker` | Container images |
| `docker-compose.yml` | Local multi-service stack |
| `nixpacks.toml` / `nixpacks.worker.toml` | Railway deployment configs |
| `railway.json` | Railway service config |
| `ruff` | Python linting |
| `pytest` | Backend testing |

## Execution Modes

| Mode | Behavior |
|---|---|
| `DRY_RUN` | Default; no broker API calls |
| `PAPER` | Paper trader (simulated fills) |
| `LIVE` | Real MetaAPI execution |

Controlled via `RUN_MODE` env var + `LIVE_TRADING_ENABLED` boolean gate.
