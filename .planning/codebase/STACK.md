# STACK.md — Technology Stack

## Languages & Runtimes

| Layer | Language | Runtime |
|-------|----------|---------|
| Backend API | Python | 3.10.1 (venv at `venv/`) |
| Worker | Python | 3.10.1 (same venv) |
| Frontend | TypeScript / JavaScript | Node.js ≥20.9 |

## Backend Frameworks & Libraries

| Library | Version | Role |
|---------|---------|------|
| **FastAPI** | latest | HTTP API framework, all routers |
| **Uvicorn** | latest | ASGI server (PYTHONPATH=/workspace) |
| **Pydantic v2** | latest | Schema validation (BaseModel, BaseSettings) |
| **pydantic-settings** | latest | `config/settings.py` BaseSettings from .env |
| **supabase-py** | latest | Supabase client (queries, inserts) |
| **redis-py** | latest | Redis pub/sub and list queue |
| **python-dotenv** | latest | `.env` loading in worker/scripts |
| **slowapi** | latest | Rate limiting on webhook endpoints |
| **ruff** | latest | Linter/formatter (Python) |
| **pytest** | latest | Backend test runner |

### Key Python-only Internal Libraries
- `src.ai` — LLM guardian (OpenAI/Anthropic via `AI_API_KEY`)
- `src.adapters.metaapi` — MetaAPI broker adapter
- `src.adapters.paper_trader` — Paper trading engine
- `src.services.trailing_stop_manager` — trailing stop service
- `src.services.breakeven_manager` — breakeven management

## Frontend Frameworks & Libraries

| Library | Version | Role |
|---------|---------|------|
| **Next.js** | 16.1.6 | App Router framework, SSR/CSR |
| **React** | 19.2.3 | UI rendering |
| **TypeScript** | ^5 | Type safety |
| **Tailwind CSS** | ^4 | Utility-first styling |
| **@tanstack/react-query** | ^5 | Server state, caching, polling |
| **@tanstack/react-table** | ^8 | Sortable/filterable data tables |
| **recharts** | ^3 | Charts (equity curve, bar charts) |
| **lightweight-charts** | ^5 | TradingView-style candlestick/line charts |
| **@supabase/supabase-js** | ^2 | Realtime subscriptions + REST |
| **@radix-ui** | various | Headless UI primitives (dialog, tabs, tooltip, etc.) |
| **lucide-react** | ^0.563 | Icon set |
| **date-fns** | ^4 | Date formatting |
| **vitest** | ^3 | Frontend test runner |

## Database Layer

- **Supabase (PostgreSQL)** — primary store
  - Table: `trading_signals` (signals, PnL, outcomes, status)
  - Table: `prop_firm_accounts` (account configs, phases)
  - Real-time subscriptions from frontend via `@supabase/supabase-js`
  - Backend uses `supabase-py` with service role key

## Message Queue / Transport

- **Redis** — `redis://localhost:6379` (required before API start)
  - Backend API pushes signals to a Redis list/queue
  - Worker consumes from the queue
  - `config/settings.py`: `SIGNAL_TRANSPORT` env var — `"redis"` (prod) or `"memory"` (tests)
  - Transport abstraction: `src/core/transport.py`

## Configuration

- `.env` at project root — loaded by `config/settings.py` (pydantic-settings)
- `config/settings.py` — `Settings` class with `@lru_cache` via `get_settings()`
- `config/logging_config.py` — structured logging setup
- Fail-fast: `SUPABASE_URL` and `REDIS_URL` required at startup
- **Cache gotcha**: settings are cached — restart process after `.env` changes

## Build & Deployment

- **Railway** — hosting platform (backend + worker + frontend as separate services)
- **start.sh** — local full-stack launcher
- Frontend: `npm run dev` (port 3000), `npm run build` for production
- Backend: `uvicorn src.api:app --host 0.0.0.0 --port 8000`
- Worker: `python3 -m src.worker`

## Package Management

- Python: pip + `venv/` (lockfile via `requirements.txt` or `pyproject.toml`)
- Frontend: npm (`package-lock.json` — use npm, not yarn/pnpm)
