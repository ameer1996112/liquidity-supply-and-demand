# Codebase Structure

**Analysis Date:** 2026-03-18

## Directory Layout

```
project-root/
├── src/                         # Backend Python source code
│   ├── api.py                  # FastAPI app + route registration
│   ├── api_*.py                # Specialized routers (execution, positions, analytics, etc.)
│   ├── worker.py               # Background consumer + guard orchestration
│   ├── logic.py                # Trade execution engine
│   ├── core/                   # Pure domain logic (no I/O)
│   │   ├── risk_engine.py      # Position sizing, pip calculations
│   │   ├── signal.py           # Webhook payload schemas
│   │   ├── transport.py        # Message envelope
│   │   ├── account_router.py   # Signal → account routing
│   │   ├── circuit_breaker.py  # Failure isolation
│   │   ├── dynamic_config.py   # Runtime settings override
│   │   ├── observers/          # Observer pattern (audit, metrics, risk tracking)
│   │   └── guard_rails/        # Fail-safe guards (sector, correlation, VAR, prop, etc.)
│   ├── services/               # Business operations (complex, stateful)
│   │   ├── account_orchestrator.py
│   │   ├── account_sync_service.py
│   │   ├── execution_engine.py
│   │   ├── position_optimizer.py
│   │   ├── portfolio_analyzer.py
│   │   ├── mtm_guardian.py
│   │   ├── watchdog.py
│   │   ├── trailing_stop_manager.py
│   │   ├── breakeven_manager.py
│   │   ├── alert_engine.py
│   │   └── ... (13 total)
│   ├── adapters/               # External integrations (swap-able)
│   │   ├── execution/          # Router: MetaAPI, paper, dry-run
│   │   ├── supabase.py         # Database client
│   │   ├── discord.py          # Notifications
│   │   ├── paper_trader.py     # Paper trading sim
│   │   ├── market_data.py      # Yahoo Finance, news
│   │   └── redis_queue.py      # Queue operations
│   ├── ai/                     # ML + LLM ensemble
│   │   ├── brain.py            # Orchestrator (RF + RAG + Council)
│   │   ├── ml_guardian.py      # Random Forest scoring
│   │   ├── trading_council.py  # LLM debate
│   │   ├── rag_engine.py       # History retrieval
│   │   ├── llm_client.py       # Provider abstraction
│   │   └── features.py         # Feature engineering
│   ├── agents/                 # Agentic workflows (future)
│   └── backtest/               # Backtest engine (legacy)
│
├── frontend/                   # Next.js React application
│   ├── src/
│   │   ├── app/                # Page routes (App Router)
│   │   │   ├── page.tsx        # Dashboard
│   │   │   ├── positions/      # Positions page
│   │   │   ├── journal/        # Trade journal
│   │   │   ├── analytics/      # Analytics page
│   │   │   ├── prop-firm/      # Prop firm metrics
│   │   │   ├── execution-quality/
│   │   │   ├── alerts/
│   │   │   ├── board/          # Kanban board for agents
│   │   │   └── ...
│   │   ├── components/         # Reusable React components
│   │   │   ├── positions/      # Position cards, tables
│   │   │   ├── journal/        # Trade journal UI
│   │   │   ├── ui/             # Headless UI (card, button, dialog, etc.)
│   │   │   ├── dashboard/      # Dashboard widgets
│   │   │   └── ... (31 total)
│   │   ├── hooks/              # Custom React hooks
│   │   ├── providers/          # Context providers
│   │   ├── lib/                # Utilities (API client, formatters)
│   │   ├── types/              # TypeScript interfaces
│   │   └── domain/             # Domain models
│   ├── public/                 # Static assets
│   └── next.config.js          # Next.js config
│
├── config/                     # Centralized settings
│   ├── settings.py             # Pydantic BaseSettings (load from .env)
│   └── logging_config.py       # Structured logging setup
│
├── migrations/                 # SQL schema (51 total)
│   ├── 001_initial.sql
│   ├── ...
│   ├── 041_board_tables.sql    # Board (Kanban) schema
│   ├── 046_be_trigger.sql      # Breakeven trigger
│   └── RUN_MIGRATIONS.md
│
├── scripts/                    # Operational scripts
│   ├── diagnose_latency.py     # Latency trace analysis
│   ├── cleanup_stale_positions.py
│   ├── check_account_data.py
│   ├── check_dlq.py            # Dead letter queue inspection
│   └── ... (15 total)
│
├── tests/                      # Unit + integration tests
│   ├── test_*.py
│   └── conftest.py             # Pytest fixtures
│
├── docs/                       # Decision records, guides
│   ├── decisions.md            # Architecture decisions
│   ├── worklog.md              # Session-by-session changes
│   ├── bugs.md                 # Bug tracking
│   └── ... (20 total guides)
│
├── ml/                         # ML analysis (legacy)
│   ├── analyze_symbol_performance.py
│   ├── train_rf_model.py
│   └── ...
│
├── app/                        # Legacy backtest app
│   └── (mostly deprecated)
│
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (NOT committed)
├── .env.example                # Environment template
├── pyproject.toml              # Project metadata (if present)
├── docker-compose.yml          # Local dev environment
├── Dockerfile                  # Production image
├── Makefile                    # Development commands
├── railway.json                # Deployment config (Railway)
└── README.md                   # Quick start guide
```

## Directory Purposes

**`src/`:**
- Purpose: All backend Python source code
- Contains: API server, worker consumer, domain logic, adapters, ML/AI
- Key files: `api.py` (entry), `worker.py` (executor), `logic.py` (engine)

**`src/core/`:**
- Purpose: Pure domain logic with no I/O or external dependencies
- Contains: Risk calculations, signal validation, routing, circuit breaking
- Key files: `risk_engine.py`, `signal.py`, `account_router.py`
- Subdirectories:
  - `guard_rails/`: Fail-safe guards (sector, correlation, VAR, prop, etc.)
  - `observers/`: Observer pattern for pipeline events

**`src/services/`:**
- Purpose: Complex, stateful business operations
- Contains: Account orchestration, position sync, execution analysis, monitoring
- Stateless: No; services maintain cached state (balance, positions)
- Examples: `account_orchestrator.py`, `watchdog.py`, `execution_engine.py`

**`src/adapters/`:**
- Purpose: Technology integration and dependency injection
- Contains: Broker APIs, database, notifications, market data
- Pattern: Swap implementations without changing business logic
- Subdirectories:
  - `execution/`: MetaAPI, paper trader, dry-run routing

**`src/ai/`:**
- Purpose: Machine learning and LLM integration
- Contains: Random Forest model, LLM debate, feature engineering, RAG
- Key files: `brain.py` (orchestrator), `ml_guardian.py` (RF), `trading_council.py` (LLM)

**`frontend/src/app/`:**
- Purpose: Next.js page routes (App Router)
- Pattern: File-based routing (`page.tsx` files)
- Pages:
  - `/`: Dashboard (real-time overview)
  - `/positions`: Open and closed positions
  - `/journal`: Trade journal with filters
  - `/analytics`: Trade analysis and statistics
  - `/prop-firm`: Prop firm performance metrics
  - `/board`: Kanban tickets for AI agents

**`frontend/src/components/`:**
- Purpose: Reusable React components
- Organization: By domain (positions, journal, dashboard, etc.)
- Pattern: Uncontrolled state where possible; React hooks for complex state
- Example:
  - `positions/PositionCard.tsx`: Single position card with PnL
  - `journal/TradeTable.tsx`: Trade list with filtering
  - `ui/card.tsx`: Headless UI primitive (no logic)

**`config/`:**
- Purpose: Centralized configuration
- Contains: Pydantic Settings model, logging config
- Pattern: Load from .env at startup; fail-fast if required vars missing
- Required: `SUPABASE_URL`, `REDIS_URL`

**`migrations/`:**
- Purpose: SQL schema versioning
- Pattern: Numbered files (001, 002, …, 051)
- Latest: 046_be_trigger.sql (breakeven trigger)
- To run: `python scripts/run_migrations.py` or SQL client

**`scripts/`:**
- Purpose: Operational utilities and diagnostics
- Executable: Most have `if __name__ == '__main__':` entry
- Examples:
  - `diagnose_latency.py`: Analyze latency traces from database
  - `cleanup_stale_positions.py`: Batch close stale positions
  - `check_account_data.py`: Inspect account state, test API

**`tests/`:**
- Purpose: Unit and integration tests
- Framework: Pytest
- Pattern: `test_<module>.py` mirrors `src/<module>.py`
- Fixtures: `conftest.py` provides mock Supabase, Redis, adapters

**`docs/`:**
- Purpose: Decision records and guides
- Key files:
  - `decisions.md`: Architecture choices and rationale
  - `worklog.md`: Session-by-session progress
  - `bugs.md`: Known issues and workarounds

## Key File Locations

**Entry Points:**
- `src/api.py`: FastAPI app (HTTP server)
- `src/worker.py`: Background consumer (event loop)
- `frontend/src/app/page.tsx`: Dashboard (Next.js entry)

**Configuration:**
- `config/settings.py`: Pydantic BaseSettings (load from .env)
- `.env`: Environment variables (secrets, API keys, flags) — NOT committed
- `.env.example`: Template for required variables

**Core Logic:**
- `src/logic.py`: Trade execution and alert saving
- `src/core/risk_engine.py`: Position sizing and risk metrics
- `src/core/guard_rails/`: Fail-safe guards

**Database:**
- `src/adapters/supabase.py`: Supabase client (41KB, 1200+ lines)
- `migrations/`: SQL schema (51 files)

**Testing:**
- `tests/`: Test files (pytest)
- `tests/conftest.py`: Fixtures and mocks

## Naming Conventions

**Files:**
- Python: `snake_case` (e.g., `risk_engine.py`, `account_router.py`)
- React: `PascalCase` for components (e.g., `PositionCard.tsx`), `camelCase` for utilities
- SQL: `<number>_<description>.sql` (e.g., `026_add_missing_jpy_pairs.sql`)

**Directories:**
- Lowercase (e.g., `src/`, `core/`, `services/`, `adapters/`)
- Plural for collections (e.g., `services/`, `components/`, `guards/`)

**Functions/Classes:**
- Python: `camelCase` for functions (e.g., `calculate_max_position_size()`), `PascalCase` for classes (e.g., `RiskEngine`)
- React: `PascalCase` for components (e.g., `PositionCard`), `camelCase` for hooks (e.g., `usePositions()`)

**Constants:**
- Python: `SCREAMING_SNAKE_CASE` (e.g., `MAX_LOT_SIZE`, `DEFAULT_ACCOUNT_ID`)

**Variables:**
- Snake case (e.g., `account_balance`, `signal_payload`)

**Environment Variables:**
- `SCREAMING_SNAKE_CASE` (e.g., `SUPABASE_URL`, `TRADING_KILL_SWITCH`, `RUN_MODE`)

## Where to Add New Code

**New Feature (e.g., new guard rail):**
- Implementation: `src/core/guard_rails/<name>.py`
- Class: `<Name>Guard`, inherit from no parent (pure domain logic)
- Call site: `src/worker.py` in the per-account or global guard loop
- Test: `tests/test_<name>_guard.py`
- Docs: Add rationale to `docs/decisions.md`

**New API Endpoint:**
- Create: `src/api_<feature>.py` (e.g., `api_evaluation.py`)
- Import router in: `src/api.py:97-118` (include_router section)
- Route pattern: `/api/v1/<feature>/<endpoint>`
- Example:
  ```python
  # src/api_evaluation.py
  from fastapi import APIRouter
  router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])
  @router.post("/check")
  async def check_evaluation(payload: EvaluationRequest) -> EvaluationResponse: ...

  # src/api.py (add line)
  app.include_router(evaluation_router)
  ```

**New Service (complex, stateful operation):**
- Location: `src/services/<name>.py`
- Class: `<Name>Service` or `<Name>Manager`
- Initialization: Either lazy-load or register in `worker.py:init_connections()`
- Example: `src/services/watchdog.py` is registered as global `watchdog` in worker

**New Component (React):**
- Location: `frontend/src/components/<domain>/<ComponentName>.tsx`
- Pattern: Functional component with TypeScript props interface
- Hooks: Use `frontend/src/hooks/` for custom state logic
- Example:
  ```tsx
  // frontend/src/components/positions/PositionCard.tsx
  interface PositionCardProps {
    position: Position
    onClose?: () => void
  }
  export function PositionCard({ position, onClose }: PositionCardProps) { ... }
  ```

**New Page (Next.js):**
- Location: `frontend/src/app/<route>/page.tsx`
- Pattern: Default export function
- Layout: Use `frontend/src/app/layout.tsx` for root wrapper
- Example:
  ```tsx
  // frontend/src/app/my-page/page.tsx
  import { MyComponent } from '@/components/my-component'
  export default function Page() { return <MyComponent /> }
  ```

**Database Schema Change:**
- Migration: `migrations/NNN_<description>.sql`
- Numbering: Increment from latest (046 → 047)
- Pattern: `CREATE TABLE`, `ALTER TABLE`, `ADD COLUMN`
- Run: `python scripts/run_migrations.py` or manual SQL
- Update: `docs/decisions.md` with schema rationale

**New API Client Call (frontend):**
- Hook location: `frontend/src/hooks/useAPI<Feature>.ts` or similar
- Pattern: Custom hook wrapping `fetch()` or axios
- Example:
  ```ts
  // frontend/src/hooks/usePositions.ts
  export function usePositions() {
    const [positions, setPositions] = useState<Position[]>([])
    useEffect(() => {
      fetch('/api/v1/positions/active').then(r => r.json()).then(setPositions)
    }, [])
    return positions
  }
  ```

**Utilities:**
- Shared helpers: `frontend/src/lib/` (formatters, API client)
- Python utilities: `src/utils/` (latency_tracker.py)

## Special Directories

**`.planning/`:**
- Purpose: GSD (Get Shit Done) planning directory
- Generated: Yes, by `/gsd:map-codebase` and `/gsd:plan-phase`
- Committed: Yes (planning docs tracked in git)
- Contents: `codebase/` (ARCHITECTURE.md, STRUCTURE.md, etc.), `phases/` (implementation plans)

**`migrations/`:**
- Purpose: SQL schema versioning
- Generated: No (hand-written)
- Committed: Yes (schema changes tracked)
- Latest: 046_be_trigger.sql
- To apply: Run SQL file against Supabase

**`.env`:**
- Purpose: Environment variables and secrets
- Generated: No (created manually or via deployment config)
- Committed: No (added to `.gitignore`)
- Template: `.env.example`

**`node_modules/` and `venv/`:**
- Purpose: Dependency directories
- Generated: Yes (npm install, pip install)
- Committed: No

**`.next/` and `.ruff_cache/`:**
- Purpose: Build caches
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-03-18*
