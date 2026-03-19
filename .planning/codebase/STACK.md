# Technology Stack

**Analysis Date:** 2026-03-19

## Languages

**Primary:**
- Python 3.11 (Docker/prod), 3.10 (local dev) - Backend API, Worker, ML, AI pipeline
- TypeScript 5.x - Frontend (all `.ts`/`.tsx` files under `frontend/src/`)

**Secondary:**
- Bash - Service startup script (`start.sh`), Docker entrypoints

## Runtime

**Environment:**
- Python: 3.11-slim (Docker), runtime pinned via `Dockerfile`
- Node.js: >=20.9.0 (enforced in `frontend/package.json`)

**Package Manager:**
- Python: pip with virtual env (nixpacks path: `/app/venv`)
- Node: npm 10.9.2 (lock file: `frontend/package-lock.json`)
- Lockfiles: `frontend/package-lock.json` present; no Python lockfile (requirements.txt only)

## Frameworks

**Backend Core:**
- FastAPI >=0.109.0 - REST API (`src/api.py`), serves all `/api/v1/*` routes
- Uvicorn (standard) >=0.27.0 - ASGI server, configured in `start.sh` and nixpacks
- Pydantic / pydantic-settings >=2.0.0 - Schema validation and env config (`config/settings.py`)
- APScheduler >=3.10.0 - Background job scheduling (daily resets, sync workers)
- slowapi >=0.1.9 - Rate limiting (wraps `limits`), applied globally at 200/minute

**Frontend Core:**
- Next.js 16.1.6 - React framework, App Router, standalone output (`frontend/next.config.ts`)
- React 19.2.3 / React DOM 19.2.3 - UI rendering

**Frontend UI:**
- Tailwind CSS 4.x - Utility-first CSS
- shadcn/ui via Radix UI primitives: `@radix-ui/react-dialog`, `react-tabs`, `react-tooltip`, `react-scroll-area`, `react-popover`, `react-separator`, `react-slot`
- `class-variance-authority` + `clsx` + `tailwind-merge` - Conditional class composition
- `lucide-react` ^0.563.0 - Icons
- `tw-animate-css` - CSS animation utilities

**Frontend Data / Charts:**
- `@tanstack/react-query` ^5.90.20 - Server state management and caching
- `@tanstack/react-table` ^8.21.3 - Table primitives
- `recharts` ^3.7.0 - Analytics charts (bar, line charts)
- `lightweight-charts` ^5.1.0 - TradingView-style price charts
- `date-fns` ^4.1.0 - Date formatting utilities

**Testing:**
- Python: not detected (no pytest in requirements.txt; `tests/` directory exists)
- Frontend: Vitest ^3.2.4 with jsdom environment (`frontend/vitest.config.ts`)

**Build/Dev:**
- Docker / docker-compose - Multi-service containerisation (`docker-compose.yml`)
- Nixpacks - Railway-specific build config (`nixpacks.toml`, `nixpacks.worker.toml`)
- ESLint 9 + eslint-config-next 16.1.6 - Frontend linting (`frontend/eslint.config.mjs`)
- PostCSS + `@tailwindcss/postcss` - CSS processing

## Key Dependencies

**Critical Backend:**
- `supabase==2.10.0` - Primary database client (`src/adapters/supabase.py`, `src/adapters/supabase_api.py`)
- `redis>=5.0.0` - Signal queue between API and Worker (`src/adapters/redis_queue.py`)
- `requests>=2.28.0` - HTTP calls to MetaApi and other external services

**ML / AI:**
- `scikit-learn==1.7.2` - ML model loading/inference (legacy models `ml/model.pkl`, `ml/model_v2.pkl`)
- `lightgbm>=4.0.0` - Primary gradient boosting model (`ml/model_v3_lgbm.txt`)
- `numpy>=1.24.0` + `pandas>=2.0.0` + `pyarrow>=14.0.0` - Data processing
- `numba>=0.58.0` - JIT-compiled backtesting loops
- `backtesting>=0.3.3` - Python backtesting framework
- `optuna>=3.5.0` - Bayesian hyperparameter optimisation
- `langchain>=0.2.0` + `langchain-community` + `langchain-openai` - LangChain RAG pipeline (`src/ai/rag_engine.py`)
- `openai>=1.0.0` - OpenAI API client (also used for Groq-compatible endpoints)
- `anthropic>=0.18.0` - Anthropic Claude client (`src/ai/llm_client.py`)
- `rank-bm25>=0.2` - BM25 retrieval for Trading Council memory (`src/ai/council_memory.py`)
- `yfinance>=0.2.36` - Market data for narrative building (`src/adapters/market_data.py`)
- `plotly>=5.18.0` + `streamlit>=1.28.0` - Analytics visualisation (scripts/ML tooling)
- `lightweight-charts>=2.0.0` - Backend chart export

**Utilities:**
- `python-dotenv>=1.0.0` - `.env` file loading
- `pytz>=2023.3` - Timezone handling
- `beautifulsoup4` + `lxml` - HTML scraping (YouTube transcript / web tools)
- `youtube-transcript-api` + `scrapetube` - YouTube data for trading council context

**Frontend Critical:**
- `@supabase/supabase-js` ^2.93.3 - Frontend direct Supabase queries (`frontend/src/lib/supabase.ts`)

## Configuration

**Environment:**
- Backend reads from `.env` at project root via pydantic-settings (`config/settings.py`)
- Required: `SUPABASE_URL`, `REDIS_URL`
- Optional critical: `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `META_API_TOKEN`, `META_API_ACCOUNT_ID`, `WEBHOOK_SECRET`, `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- AI provider key: `AI_API_KEY` (aliases: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Frontend reads: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`

**Build:**
- `Dockerfile` / `Dockerfile.api` / `Dockerfile.worker` - Python 3.11-slim base
- `frontend/Dockerfile` - Node.js standalone Next.js build
- `docker-compose.yml` - Local multi-service orchestration
- `nixpacks.toml` / `nixpacks.worker.toml` - Railway deployment build specs
- `railway.json` / `frontend/railway.json` - Railway service config

## Platform Requirements

**Development:**
- Docker + Docker Compose for full local stack
- Python >=3.10 + pip for local backend
- Node.js >=20.9.0 + npm for frontend
- Redis (via Docker or local install)

**Production:**
- Deployed on **Railway** (PaaS)
- Backend API: Railway service (`nixpacks.toml` / `Dockerfile.api`)
- Worker: Separate Railway service (`nixpacks.worker.toml` / `Dockerfile.worker`)
- Frontend: Railway service (`frontend/railway.json`)
- Frontend production URL: `https://frontend-production-a7cf.up.railway.app`

---

*Stack analysis: 2026-03-19*
