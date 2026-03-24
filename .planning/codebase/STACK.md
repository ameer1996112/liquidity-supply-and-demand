# STACK.md — Technology Stack

## Overview
Institutional liquidity-based algorithmic trading system. Three-service architecture:
1. **Backend API** — FastAPI (port 8000)
2. **Worker** — Python async consumer
3. **Frontend** — Next.js 16 (port 3000)

---

## Languages & Runtimes

| Layer | Language | Runtime |
|-------|----------|---------|
| Backend API | Python 3.11+ | CPython (venv at `/workspace/.venv`) |
| Worker | Python 3.11+ | CPython |
| Frontend | TypeScript 5 | Node ≥ 20.9 |
| ML | Python | scikit-learn, LightGBM, Numba |
| Pine Script | Pine Script v5 | TradingView runtime |

---

## Backend Frameworks & Libraries

### Web Framework
- **FastAPI** ≥ 0.109.0 — async API framework
- **Uvicorn** ≥ 0.27.0 — ASGI server (with `standard` extras)
- **SlowAPI** ≥ 0.1.9 — rate limiting middleware (wraps `limits` lib)
- **Starlette** — request/response middleware pipeline

### Configuration
- **Pydantic-Settings** ≥ 2.0.0 — typed settings with `@lru_cache`
- **python-dotenv** ≥ 1.0.0 — `.env` file loading
- Config class: `config/settings.py::Settings` (pydantic `BaseSettings`)

### Queue / Transport
- **Redis** ≥ 5.0.0 — signal queue backend (BLPOP consumer pattern)
- `src/adapters/redis_queue.py` — enqueue/dequeue abstraction
- `src/core/transport.py` — pluggable transport (redis | memory for tests)

### Scheduling
- **APScheduler** ≥ 3.10.0 — background job scheduling

### HTTP Client
- **requests** ≥ 2.28.0 — outbound HTTP (MetaAPI, Discord, Telegram)

### Database Client
- **supabase** 2.10.0 — Postgres via Supabase REST API

### AI / LLM
- **LangChain** ≥ 0.2.0 + langchain-community + langchain-openai
- **OpenAI** ≥ 1.0.0 — compatible with Groq via `ai_base_url`
- **Anthropic** ≥ 0.18.0 — Claude models
- **tiktoken** ≥ 0.7.0 — token counting

### ML / Data Science
- **scikit-learn** 1.7.2 — Random Forest classifier (`MLGuardian`)
- **LightGBM** ≥ 4.0.0 — gradient boosting (memory-efficient)
- **NumPy** ≥ 1.24.0, **pandas** ≥ 2.0.0, **pyarrow** ≥ 14.0.0
- **Numba** ≥ 0.58.0 — JIT compilation for backtesting
- **backtesting** ≥ 0.3.3 — strategy simulation framework
- **Optuna** ≥ 3.5.0 — Bayesian hyperparameter optimization
- **rank-bm25** ≥ 0.2 — BM25 retrieval for RAG / council memory

### Visualization (mostly backend analytical)
- **Plotly** ≥ 5.18.0 — analytics heatmaps
- **lightweight-charts** ≥ 2.0.0 — TradingView-style charts (backend helper)
- **streamlit** ≥ 1.28.0 — internal dashboards
- **yfinance** ≥ 0.2.36, **beautifulsoup4**, **lxml** — market data scraping

### Linting / Quality
- **ruff** — fast Python linter (configured for `src/`, `config/`, `tests/`)

---

## Frontend Stack

### Framework
- **Next.js 16.1.6** — App Router, React Server Components
- **React 19.2.3** + **react-dom 19.2.3**
- **TypeScript 5**

### Styling
- **TailwindCSS 4** (PostCSS plugin)
- **tw-animate-css** — animation utilities

### UI Components
- **Radix UI** — Dialog, Popover, ScrollArea, Separator, Slot, Tabs, Tooltip
- **lucide-react** 0.563.0 — icon library
- **class-variance-authority** + **clsx** + **tailwind-merge** — conditional class utilities

### Data & State
- **@tanstack/react-query** 5.90.20 — server state + caching
- **@tanstack/react-table** 8.21.3 — table rendering
- **@supabase/supabase-js** 2.93.3 — real-time subscriptions + direct DB queries
- **recharts** 3.7.0 — charting
- **lightweight-charts** 5.1.0 — TradingView-style price charts

### Utilities
- **date-fns** 4.1.0 — date formatting

### Testing
- **Vitest** 3.2.4 — unit testing framework
- **jsdom** 27.0.1 — DOM environment for tests

---

## Infrastructure

| Component | Technology |
|-----------|-----------|
| Signal Queue | Redis (localhost:6379 default) |
| Database | Supabase (PostgreSQL) |
| Deployment | Railway.app (nixpacks, `railway.json`) |
| Containers | Docker + docker-compose.yml |
| CI/CD | GitHub Actions (`.github/`) |
| Process Init | `start.sh` (fullstack / api / worker flags) |
| System Services | `install-services.sh` / `uninstall-services.sh` |

---

## Environment Variables (key subset)

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_URL` | ✅ | Database |
| `REDIS_URL` | ✅ | Signal queue |
| `WEBHOOK_SECRET` | Optional | Validate TradingView webhooks |
| `AI_FILTER_ENABLED` | Optional | Toggle AI Guardian |
| `ML_GUARDIAN_ENABLED` | Optional | Toggle ML Guardian |
| `TRINITY_ENABLED` | Optional | Toggle Trinity risk engine |
| `META_API_TOKEN` | Optional | Live broker execution |
| `META_API_ACCOUNT_ID` | Optional | Live broker execution |
| `LIVE_TRADING_ENABLED` | Optional | Gate for live order flow |
| `DISCORD_WEBHOOK_URL` | Optional | Notifications |
| `AI_API_KEY` | Optional | OpenAI/Anthropic/Groq API key |
| `FRONTEND_URL` | Optional | CORS allow-list |

Full reference: `.env.example`
