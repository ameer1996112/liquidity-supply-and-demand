# Directory Structure

## Root Level
- `/frontend`: Next.js frontend application.
- `/src`: Primary Python source code for Backend API and Worker.
- `/scripts`: Utility scripts, Jira sync tools, and TradingView Pine Scripts.
- `/tests`: Python end-to-end and unit test suite.
- `/docs`: Project documentation and guides.

## Source Code (`/src`)
- `api*.py` (e.g., `api.py`, `api_accounts.py`): FastAPI routers and endpoints. Contains modules split by domain (analytics, backtests, risk, etc.).
- `worker.py`: The main background worker loop consuming Redis queues and executing trades.
- `logic.py`: Core trading logic and decision trees.
- `/ai`: AI/LLM integration logic, Trading Council agents, and prompt templates.
- `/agents`, `/adapters`, `/services`, `/core`, `/utils`: Domain-driven modularized logic and helpers.
- `/backtest`: Backtesting engine code utilizing scikit-learn and LightGBM.

## Frontend (`/frontend`)
- `/src`: Next.js App router or standard React components.
- `/public`: Static assets.
- `package.json`, `next.config.ts`, `vitest.config.ts`: Frontend configuration files.

## Scripts (`/scripts`)
- `/pinescript`: Contains `.pine` strategy files used in TradingView.
- `/sql`: Supabase schema migrations.
- `jira-agent.js`, `jira-sync.js`: Node.js scripts for syncing to Jira.
