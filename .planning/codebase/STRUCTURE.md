# Codebase Structure

## Directory Tree
```text
.
├── config/                 # YAML/Env configuration files
├── data/                   # Local storage for ML models and datasets
├── docs/                   # System documentation and manuals
├── frontend/               # Next.js Dashboard application
│   ├── src/
│   │   ├── app/            # Next.js App Router pages
│   │   ├── components/     # UI components (TradingView charts, Signal feed)
│   │   ├── hooks/          # React hooks for data fetching (Tanstack Query)
│   │   ├── services/       # Frontend-side API clients
│   │   └── types/          # TypeScript interfaces
├── migrations/             # SQL migrations for Supabase
├── ml/                     # ML model training and evaluation scripts
├── src/                    # Backend Source Code
│   ├── adapters/           # External service integrations (DB, Broker, Redis)
│   ├── agents/             # Multi-agent AI logic (Trading Council)
│   ├── ai/                 # Prediction models and guardrail logic
│   ├── api/                # Modular API routers (risk, alerts, analytics)
│   ├── core/               # Shared logic, models, and risk engines
│   │   ├── guard_rails/    # Specific risk check implementations
│   │   └── observers/      # Audit and metric collection
│   ├── services/           # Business logic modules (Execution, Alerts, Prop firm)
│   ├── utils/              # General helper functions
│   ├── api.py              # API Entry Point
│   ├── worker.py           # Worker Entry Point
│   └── logic.py            # Core Trade Execution Logic
└── tests/                  # Pytest suite (unit, integration, and backtests)
```

## Key Folders & Roles
- **`src/adapters/`**: Critical abstraction layer. If switching brokers or databases, this is where changes are made.
- **`src/core/`**: The "Heart" of the system. Contains the domain models (`signal.py`), risk logic (`risk_engine.py`), and transport abstractions.
- **`src/services/`**: High-level modules that orchestrate complex tasks like moving SL to breakeven or tracking prop firm drawdown.
- **`frontend/src/`**: Standard Next.js structure. Uses Tailwind CSS and Radix UI components.

## Key Files
- `src/api.py`: Initializes FastAPI, sets up middleware, and defines the primary webhook ingestion route.
- `src/worker.py`: Implements the `WorkerSubject` loop that continuously polls Redis and dispatches signals to the execution engine.
- `src/logic.py`: Contains the `process_trade` function which acts as the final step before hitting the broker adapters.
- `config/settings.py`: Centralized settings with `pydantic-settings` (cached via `@lru_cache`).
- `.env`: Vital environment variables (Supabase keys, Redis URL, MetaApi tokens).
- `migrations/`: Numbered SQL migration files for Supabase schema evolution.

## Naming Conventions
- **Python**: `snake_case` for files, variables, and functions. `PascalCase` for classes.
- **Frontend**: `kebab-case` for file names in `components/`. `PascalCase` for React components. `camelCase` for hooks and utility functions.
- **Constants**: `UPPER_SNAKE_CASE` (mostly found in `src/core/`).

## Where to find...
- **Application Config**: `config/settings.py` and project root `.env`.
- **Database Schemas**: `src/core/signal.py` (Pydantic models) and `migrations/`.
- **Trade Execution Logic**: `src/services/execution_engine.py` and `src/logic.py`.
- **Risk Parameters**: `src/core/risk_engine.py` and dynamic configs in Supabase.
- **API Endpoints**: `src/api.py` and modules under `src/api/`.
- **Tests**: `tests/` directory with pytest suite.
