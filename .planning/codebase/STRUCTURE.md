# STRUCTURE

## Directory Layout
- `/src/` or `/app/` - Python backend API and Worker source code. Contains core logic, API definitions (`api.py`), and worker process (`worker.py`).
- `/config/` - Configuration modules, including Pydantic settings (`settings.py`), logging configurations, and `.env` loading.
- `/frontend/` - Next.js codebase for the operational dashboard.
- `/docs/` - System documentation, fix plans, and latency optimization reports.
- `/data/` - Static and cached historical data, backtest results, and raw datasets used for ML. 

## Key Entry Points
- Frontend: `cd frontend && npm run dev`
- API: `python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000`
- Worker: `python3 -m src.worker`
- Start Script: `./start.sh fullstack` triggers all three components.
