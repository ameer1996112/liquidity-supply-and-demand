# Technology Stack

**Analysis Date:** 2025-01-09

## Languages

**Primary:**
- Python 3.11 - Backend API, Worker, AI/ML logic
- TypeScript 5.x (ES2017 target) - Frontend Next.js application

**Secondary:**
- Bash - Build scripts, start.sh
- Pine Script - TradingView strategy scripts (`/scripts/pinescript/`)
- SQL - Supabase migrations (`/scripts/sql/`)

## Runtime

**Environment:**
- Python 3.11 (slim-bookworm Docker base)
- Node.js 20 (Alpine for frontend)

**Package Manager:**
- pip (Python) - requirements.txt
- npm (Node.js) - package.json
- Lockfile: Not detected (no package-lock.json in version control)

## Frameworks

**Core Backend:**
- FastAPI 0.115.6 - Web framework for API endpoints
- Uvicorn 0.34.0 - ASGI server
- Gunicorn - WSGI/ASGI HTTP Server
- APScheduler 3.11.0 - Background job scheduling
- RQ (Redis Queue) - Task queue processing
- Pydantic 2.10.5 + pydantic-settings - Data validation and settings management

**Core Frontend:**
- Next.js 16.1.6 - React framework (App Router pattern)
- React 19.2.3 - UI library
- TailwindCSS v4 - Utility-first CSS framework
- Radix UI primitives - Headless UI components (via shadcn/ui pattern)

**Testing:**
- pytest 8.3.4 - Python testing framework
- pytest-asyncio 0.25.3 - Async test support
- pytest-mock 3.14.0 - Mocking utilities
- Vitest - Frontend testing framework
- @testing-library/react - React component testing

**Build/Dev:**
- ruff 0.9.2 - Python linter/formatter (PEP 8, 98 pre-existing warnings)
- husky - Git hooks manager
- Docker + Docker Compose - Container orchestration

## Key Dependencies

**Critical Backend:**
- metaapi-cloud-sdk 29.0.0 - MetaTrader 4/5 trade execution via WebSocket
- supabase 2.12.0 (supabase-py) - Database client with realtime
- redis 5.2.1 - Queue and caching
- lightgbm 4.6.0 - Gradient boosting for ML Guardian
- scikit-learn 1.6.1 - Random Forest and ML utilities
- langchain 0.3.30 + langchain-openai/groq/anthropic - LLM agent framework
- pandas 2.2.3 - Data manipulation
- numpy 2.2.6 - Numerical computing
- yfinance 0.2.52 - Market data retrieval

**Critical Frontend:**
- @supabase/supabase-js 2.49.1 - Supabase client
- @supabase/ssr 0.5.2 - Server-side rendering auth
- @tanstack/react-query 5.74.3 - Async state management
- @tanstack/react-table 8.21.2 - Table component
- recharts 2.15.2 - Chart library
- lightweight-charts 5.0.6 - Trading charts
- zod 3.25.54 - Schema validation
- lucide-react 0.507.0 - Icons

**Infrastructure:**
- HTTPX 0.28.1 - Async HTTP client
- aiohttp 3.11.12 - Async HTTP server/client
- websockets 15.0.1 - WebSocket client
- tenacity 9.0.0 - Retry utilities
- mplfinance 0.12.10 - Matplotlib finance charts
- playwright 1.52.0 - Browser automation

## Configuration

**Environment:**
- Config management via Pydantic Settings with `@lru_cache` pattern
- Centralized in `config/settings.py` - 517 lines of env vars
- Key env files: `.env`, `.env.local`, `.env.production`
- `get_settings()` function required for all config access
- Never access `os.environ` directly per AGENTS.md rules

**Build:**
- Docker multi-stage builds for production optimization
- Nixpacks for Railway deployment (nixpacks.toml, nixpacks.worker.toml)
- railway.json for deployment configuration with watch patterns

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 20+
- Redis server (local or Docker)
- Docker and Docker Compose

**Production:**
- Railway (primary deployment platform)
- Docker or Nixpacks builders
- Supabase cloud (PostgreSQL + Realtime)
- Redis (managed or containerized)
- MetaApi Cloud (MT4/MT5 broker bridge)

---

*Stack analysis: 2025-01-09*