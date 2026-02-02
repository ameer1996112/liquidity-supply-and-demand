# DDD v9.0 Project Structure

Refactor completed: flat `backend/` reorganized into domain-driven layout.

## Layout

```text
project_root/
├── config/                 # Configuration
│   ├── __init__.py
│   └── settings.py         # Pydantic Settings (from backend/config.py)
│
├── src/                    # Main source
│   ├── __init__.py
│   ├── core/               # Pure domain (no external API calls)
│   │   ├── signal.py       # Entry/Exit webhook payload models
│   │   ├── risk_engine.py  # RiskGuardian, calculate_max_position_size
│   │   └── guard_rails/
│   │       ├── prop_guard.py   # Risk (create_risk_guardian_from_settings)
│   │       ├── market_filter.py # MarketAdapter, lot sizing
│   │       └── correlation.py  # CorrelationManager
│   │
│   ├── adapters/           # External services
│   │   ├── supabase.py     # DB (from backend/supabase_db.py)
│   │   ├── discord.py      # Discord/Telegram alerts
│   │   ├── redis_queue.py  # Redis client, QUEUE_NAME, push_payload
│   │   ├── metaapi.py      # Execution router (get_adapter)
│   │   ├── paper_trader.py # Paper trading
│   │   └── execution/     # DRY_RUN, PAPER, LIVE adapters
│   │
│   ├── ai/                 # ML
│   │   ├── brain.py        # load_brain, get_prediction
│   │   └── features.py     # Feature engineering
│   │
│   ├── logic.py            # process_trade, should_forward_alert
│   ├── worker.py           # Orchestrator (guards → logic)
│   └── api.py              # FastAPI app (webhook, health)
│
├── frontend/               # Next.js app (was dashboard/)
│   ├── src/lib/api.ts      # getApiUrl(), getHealthUrl(), getWebhookUrl() from NEXT_PUBLIC_API_URL
│   └── Dockerfile          # Standalone build; port 3000
├── tests/                  # Unit & integration (unchanged location)
├── scripts/                # Utilities
├── .env
├── requirements.txt        # Root deps
├── Dockerfile.api          # Backend API (project root)
├── Dockerfile.worker
└── start.sh                # Backend only (default) or fullstack (frontend + backend)
```

## Running

- **Local backend only:** `./start.sh` (sets `PYTHONPATH=$ROOT_DIR`, starts API + worker).
- **Local full stack:** `./start.sh fullstack` (starts Next.js in `frontend/` on port 3000 + backend).
- **API:** `uvicorn src.api:app --host 0.0.0.0 --port 8000` (with `PYTHONPATH=.` or project root).
- **Worker:** `python -m src.worker` (with `PYTHONPATH=.`).
- **Frontend:** `cd frontend && npm run dev` (port 3000). Set `NEXT_PUBLIC_API_URL=http://localhost:8000` to talk to backend.
- **Tests:** `pytest tests/unit -v -m unit` (with `pythonpath = .` in pytest.ini or `PYTHONPATH=.`).

## Backend shims

`backend/` remains as **compatibility shims**: thin modules that re-export from `config` and `src` so existing imports like `from backend.config import get_settings` and `from backend.worker import process_trade` still work. Tests and any external code can keep using `backend.*` until updated to `config.*` / `src.*`.

## Docker

- **Backend:** Build context is project root (`.`). `Dockerfile.api` and `Dockerfile.worker` copy `config/`, `src/`, and (worker) `ml/`.
- **Frontend:** Build context `./frontend`, `Dockerfile`; exposes port 3000; env `NEXT_PUBLIC_API_URL=http://backend:8000`.
- `docker-compose.yml`: services `backend` (API), `worker`, `redis`, `frontend`. Frontend depends on backend.

## Dead code

- No application code was deleted. Legacy scripts (e.g. `backend/backtest_ai_filter.py`, `train_model.py`) remain under `backend/` for now; they can be moved to `scripts/` or `_archive/` in a follow-up.
- `backend/ml_guardian.py`, `backend/pine_guardian.py`, `backend/ai_guardian.py`, `backend/news_filter.py` are unchanged and still used by tests; they depend on `backend.config` (shimmed).
