# AGENTS.md

## Cursor Cloud specific instructions

### Architecture overview
This is an institutional liquidity-based algorithmic trading system with three main services:
- **Backend API** (FastAPI, port 8000): Receives TradingView webhook signals, validates them, pushes to Redis queue
- **Worker** (Python): Consumes signals from Redis, runs AI/ML guardrails, executes trades
- **Frontend** (Next.js, port 3000): Real-time trading dashboard with signal feed, risk monitoring, analytics

### Required infrastructure
- **Redis** must be running on `localhost:6379` before the backend API starts (it fail-fast checks Redis on startup). Start with `redis-server --daemonize yes`.

### Environment
- Python venv is at `/workspace/.venv` — activate with `source /workspace/.venv/bin/activate`
- Backend `.env` is at project root (`/workspace/.env`). Required vars: `SUPABASE_URL`, `REDIS_URL`. See `.env.example` for all options.
- Frontend uses `npm` (lockfile: `package-lock.json`). Node >=20.9 required.
- `PYTHONPATH=/workspace` must be set when running backend commands outside `start.sh`.

### Running services
- **Backend API**: `source .venv/bin/activate && PYTHONPATH=/workspace python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000`
- **Worker**: `source .venv/bin/activate && PYTHONPATH=/workspace python3 -m src.worker`
- **Frontend dev**: `cd frontend && npm run dev`
- **Full stack**: `./start.sh fullstack` (starts API + Worker + Frontend)

### Lint / Test / Build
- **Backend lint**: `ruff check src/ config/ tests/` (98 pre-existing warnings)
- **Backend tests**: `PYTHONPATH=/workspace pytest tests/ -v` (11 tests, all pass)
- **Frontend lint**: `cd frontend && npx eslint` (pre-existing warnings/errors)
- **Frontend tests**: `cd frontend && npx vitest run` (1 pre-existing failure in `tradingMetrics.test.ts`)
- **Frontend build**: `cd frontend && npm run build`

### Gotchas
- The `config/settings.py` uses `@lru_cache` for `get_settings()`. If you change `.env` values, the backend process must be restarted for changes to take effect.
- The Makefile references `docker-compose.test.yml` which does not exist in the repo. Use a local Redis server directly instead.
- AI/ML guardrails (`AI_FILTER_ENABLED`, `ML_GUARDIAN_ENABLED`, `TRINITY_ENABLED`) can be disabled in `.env` for local dev to avoid needing external API keys.
- The webhook endpoint at `POST /webhook` accepts JSON with fields: `symbol`, `side`, `entry`, `sl`, `tp`, `size`. A `WEBHOOK_SECRET` is only checked if set in `.env`.
