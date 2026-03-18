# Technology Stack

**Analysis Date:** 2026-03-18

## Languages

**Primary:**
- Python 3.11 - Backend API, worker, signal processing, ML models, trading logic
- TypeScript 5 - Frontend React application (Next.js)

**Secondary:**
- JavaScript (Node 20) - Frontend runtime and build tooling
- SQL - Supabase PostgreSQL schema migrations

## Runtime

**Environment:**
- Python 3.11-slim (Docker: `python:3.11-slim`)
- Node.js 20-alpine (Docker: `node:20-alpine`)

**Package Manager:**
- pip (Python) - `requirements.txt` at project root
- npm (Node.js) - `frontend/package.json`
- Lockfile: `frontend/package-lock.json` present

## Frameworks

**Core:**
- FastAPI 0.109+ - REST API server for signal webhook reception and trade management endpoints
- Uvicorn 0.27+ - ASGI server for FastAPI
- Next.js 16.1.6 - React framework for frontend, runs on Node 20

**Testing:**
- Vitest 3.2.4 - Frontend unit testing (replaces Jest)
- Pytest - Backend unit/integration testing (implicit from codebase structure)

**Build/Dev:**
- Tailwind CSS 4 - Frontend styling
- TypeScript 5 - Type safety for frontend
- ESLint 9 - JavaScript/TypeScript linting with Next.js config

## Key Dependencies

**Critical:**
- supabase 2.10.0 - Cloud PostgreSQL database and REST API client (`src/adapters/supabase.py`)
- redis 5.0.0 - Message queue for signal processing (webhook → Redis → worker)
- pydantic-settings 2.0.0 - Environment configuration management with validation
- requests 2.28+ - HTTP client for MetaAPI broker calls

**Infrastructure:**
- apscheduler 3.10+ - Background job scheduling (account sync, market checks)
- slowapi 0.1.9 - Rate limiting middleware for API (200/minute default)
- python-dotenv 1.0+ - Environment variable loading from `.env`

**ML/Data:**
- scikit-learn 1.7.2 - Random Forest ML Guardian model training
- lightgbm 4.0+ - Gradient boosting (alternative/future models)
- pandas 2.0+ - Data manipulation for backtesting/analysis
- numpy 1.24+ - Numerical computation for position sizing, statistics
- backtesting 0.3.3 - Python backtesting framework for strategy validation
- numba 0.58+ - JIT compilation for backtesting performance

**AI/LLM:**
- anthropic 0.18+ - Claude API client
- openai 1.0+ - OpenAI API client (fallback)
- langchain 0.2+ - LLM orchestration framework
- langchain-community 0.2+ - LangChain community integrations
- langchain-openai 0.1+ - LangChain OpenAI integration
- tiktoken 0.7+ - Token counting for LLM APIs

**Market Data & Visualization:**
- yfinance 0.2.36+ - Yahoo Finance data for market price validation
- lightweight-charts 2.0+ - TradingView-style charting (Python/frontend)
- plotly 5.18+ - Interactive heatmaps and analytics visualizations
- beautifulsoup4 - Web scraping for market context

**Frontend UI:**
- @supabase/supabase-js 2.93.3 - Supabase JavaScript client (auth, real-time)
- @tanstack/react-query 5.90+ - Data fetching and caching (TanStack Query)
- @tanstack/react-table 8.21+ - Headless table component
- @radix-ui/* - Accessible UI components (dialog, popover, tabs, tooltip)
- lucide-react 0.563+ - Icon library
- recharts 3.7+ - React charting library
- date-fns 4.1+ - Date manipulation
- tailwind-merge 3.4+ - Merge Tailwind CSS classes safely

**Optional/Advanced:**
- optuna 3.5+ - Bayesian hyperparameter optimization
- rank-bm25 0.2+ - BM25 ranking for RAG (trading council memory)
- youtube-transcript-api - Educational content ingestion
- scrapetube - YouTube scraping for market updates
- streamlit 1.28+ - Optional dashboard/reporting UI

## Configuration

**Environment:**
- `.env` file at project root (loaded by `config/settings.py`)
- `.env.example` documents all variables with descriptions
- Settings managed via Pydantic `BaseSettings` class in `config/settings.py`

**Key configs required:**
- `SUPABASE_URL` - PostgreSQL database endpoint (required)
- `REDIS_URL` - Message queue endpoint (required)
- `SUPABASE_ANON_KEY` or `SUPABASE_KEY` - Database access token
- `SUPABASE_SERVICE_ROLE_KEY` - Admin database access (backend only)
- `META_API_TOKEN` - Broker API authentication token
- `META_API_ACCOUNT_ID` - Broker account identifier

**Build:**
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/eslint.config.mjs` - ESLint configuration
- `frontend/next.config.ts` - Next.js build configuration (output: standalone)
- `Dockerfile` - Multi-image build for backend
- `Dockerfile.api` - API container (FastAPI + Uvicorn)
- `Dockerfile.worker` - Worker container (signal processing)
- `frontend/Dockerfile` - Next.js container with multi-stage build
- `docker-compose.yml` - Local development orchestration (Redis + API + Worker + Frontend)

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 20.9.0+ (from `frontend/package.json` engines)
- Git for version control
- Docker/Docker Compose for containerized development

**Production:**
- Deployment target: Railway.app (specified in multiple places)
- Container orchestration via Docker
- Redis instance (cloud or self-hosted)
- Supabase PostgreSQL database
- MetaAPI broker gateway (SaaS)

---

*Stack analysis: 2026-03-18*
