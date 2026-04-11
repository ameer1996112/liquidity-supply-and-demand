# Codebase Structure

## Directory Layout

```
./
├── .planning/                    # GSD planning artifacts
│   └── codebase/                 # Architecture docs (this dir)
│       ├── ARCHITECTURE.md       # System architecture
│       └── STRUCTURE.md          # This file
├── .claude/                      # Claude Code configuration
│   └── skills/                   # Custom skills for this project
│       └── trading-reconcile/
│           └── SKILL.md
├── frontend/                     # Next.js 15 + React 19 + TypeScript
│   ├── src/
│   │   ├── app/                  # Next.js app router
│   │   │   ├── accounts/
│   │   │   ├── copilot/
│   │   │   ├── login/
│   │   │   ├── metrics/
│   │   │   ├── settings/
│   │   │   ├── signals/
│   │   │   └── trades/
│   │   ├── components/           # Feature-organized components
│   │   │   ├── copilot/          # AI council UI
│   │   │   ├── metrics/          # Dashboard charts
│   │   │   ├── risk/             # Kill switches, limits
│   │   │   └── trading/          # Signal panels
│   │   └── lib/
│   │       └── supabase.ts      # Supabase client config
│   ├── next.config.ts
│   └── package.json
├── src/                          # Python backend (FastAPI)
│   ├── api.py                    # Main FastAPI app (1,091 lines)
│   ├── api_*.py                  # 35+ API endpoint modules
│   │   ├── api_accounts.py       # Account management
│   │   ├── api_kill_switch.py    # Kill switch endpoints
│   │   ├── api_metrics.py        # Metrics API
│   │   ├── api_signals.py        # Signal query endpoints
│   │   └── ...
│   ├── worker.py                 # Redis queue worker
│   ├── logic.py                  # Core trading logic (946 lines)
│   ├── adapters/                 # External service adapters
│   │   ├── execution/
│   │   │   └── meta_api_adapter.py  # MT5 bridge (974 lines)
│   │   └── supabase.py           # Supabase ORM
│   ├── ai/                       # AI/ML layer
│   │   ├── trading_council.py    # Multi-agent debate
│   │   ├── rag_engine.py         # Retrieval for context
│   │   └── llm_client.py         # OpenAI/Anthropic wrapper
│   ├── core/                     # Domain primitives
│   │   ├── broker_profiles.py    # Multi-account config (132 lines)
│   │   ├── risk_engine.py        # Risk calculations (601 lines)
│   │   ├── guard_rails/          # Trade veto implementations
│   │   │   ├── __init__.py
│   │   │   ├── staleness.py
│   │   │   ├── pine_guardian.py
│   │   │   ├── prop_guard.py
│   │   │   ├── sector.py
│   │   │   ├── holiday.py
│   │   │   ├── market_filter.py
│   │   │   ├── correlation.py
│   │   │   └── portfolio_var.py
│   │   └── observers/            # Event-driven observers
│   │       ├── auditor.py
│   │       ├── risk_observer.py
│   │       ├── metrics.py
│   │       └── account_router.py
│   ├── pipeline/                 # Signal processing pipeline
│   │   ├── __init__.py
│   │   ├── executor.py           # Main pipeline orchestrator
│   │   └── profile_executor.py   # Per-account execution (144 lines)
│   └── services/                 # 40+ business logic services
│       ├── signal_service.py
│       ├── trade_service.py
│       ├── account_service.py
│       └── ...
├── tests/                        # Test suites
│   ├── test_api.py
│   ├── test_worker.py
│   ├── test_risk_engine.py
│   └── test_guard_rails.py
├── config/                       # Configuration
│   └── settings.py               # Pydantic-settings config
├── scripts/                      # Utility scripts
│   ├── pinescript/               # TradingView strategies
│   ├── sql/                      # Supabase migrations
│   └── jira-*.js                 # Jira automation
├── docs/                         # Project documentation
├── docker-compose.yml            # 4-service infrastructure
└── requirements.txt              # Python dependencies
```

## Directory Purposes

### `/frontend/src/app/`
- **Purpose:** Next.js 14+ app router pages
- **Naming:** Route segments as directories (e.g., `/accounts/` → `accounts/`)
- **Key files:** `page.tsx` (Server Component), `layout.tsx` (route layout)

### `/frontend/src/components/`
- **Purpose:** Reusable React components organized by feature
- **Subdirectories:**
  - `copilot/` - AI trading council UI
  - `metrics/` - Charts, PnL displays, dashboards
  - `risk/` - Kill switches, risk limit displays
  - `trading/` - Signal panels, order forms

### `/frontend/src/lib/`
- **Purpose:** Utilities, clients, configuration
- **Key file:** `supabase.ts` - Supabase client with realtime subscriptions

### `/src/api*.py`
- **Purpose:** FastAPI routers grouped by domain
- **Naming:** `api_{domain}.py` pattern
- **Registration:** All imported in `api.py` main app
- **Count:** 35+ endpoint modules

### `/src/core/guard_rails/`
- **Purpose:** Trade veto implementations
- **Pattern:** Each guard is a module with `check(signal, context)` function
- **Registration:** Auto-discovered in pipeline executor

### `/src/core/observers/`
- **Purpose:** Event consumers for cross-cutting concerns
- **Pattern:** Observer base class, async event handlers

### `/src/pipeline/`
- **Purpose:** Signal processing workflow
- **Key files:**
  - `executor.py` - Orchestrates guards → risk → execution
  - `profile_executor.py` - Multi-account routing

### `/src/services/`
- **Purpose:** Business logic layer (DDD services)
- **Count:** 40+ service modules
- **Scope:** Domain operations, not HTTP or infrastructure

### `/src/adapters/`
- **Purpose:** External service integration
- **Pattern:** Adapter pattern, async interfaces
- **Key files:**
  - `execution/meta_api_adapter.py` - MT5 broker bridge
  - `supabase.py` - Database operations

### `/src/ai/`
- **Purpose:** LLM/ML components
- **Key files:**
  - `trading_council.py` - Multi-agent debate system
  - `rag_engine.py` - Context retrieval for LLM prompts

### `/tests/`
- **Purpose:** Test suites (pytest)
- **Coverage:** API, worker, risk engine, guard rails

### `/scripts/`
- **Purpose:** Operational scripts
- **Subdirectories:**
  - `pinescript/` - TradingView .pine strategy files
  - `sql/` - Database migrations and schema

## Key File Locations

### Entry Points
- `src/api.py` - FastAPI application factory
- `src/worker.py` - Redis consumer main loop

### Configuration
- `config/settings.py` - Pydantic-settings (env var mapping)
- `docker-compose.yml` - 4-service infrastructure
- `.env` - Environment variables (not committed)

### Core Logic
- `src/logic.py` - Trading decision engine (946 lines)
- `src/core/risk_engine.py` - Risk calculations (601 lines)
- `src/core/broker_profiles.py` - Multi-account config (132 lines)

### Execution
- `src/adapters/execution/meta_api_adapter.py` - MT5 bridge (974 lines)
- `src/pipeline/profile_executor.py` - Trade execution pipeline (144 lines)

### Frontend
- `frontend/next.config.ts` - Next.js configuration
- `frontend/src/lib/supabase.ts` - Supabase client

## Naming Conventions

### Python
- **Files:** `snake_case.py`
- **API files:** `api_{domain}.py` (e.g., `api_accounts.py`)
- **Classes:** `PascalCase` (e.g., `RiskEngine`, `MetaApiAdapter`)
- **Functions:** `snake_case` with type hints
- **Constants:** `UPPER_SNAKE_CASE` at module level
- **Private:** `_leading_underscore` for internal methods

### TypeScript/React
- **Files:** `PascalCase.tsx` for components, `camelCase.ts` for utils
- **Components:** `PascalCase` function names
- **Hooks:** `use{Feature}` naming (e.g., `useSupabase`)
- **Types:** `PascalCase` interfaces/types with explicit exports

### Directories
- **Backend:** Feature-based (e.g., `guard_rails/`, `observers/`)
- **Frontend:** Route-based in `app/`, feature-based in `components/`

## Where to Add New Code

### New API Endpoint
- **Route definition:** `src/api_{domain}.py`
- **Schema:** Co-located in same file or `src/schemas/{domain}.py`
- **Registration:** Import and include in `src/api.py`

### New Guard Rail
- **Implementation:** `src/core/guard_rails/{guard_name}.py`
- **Interface:** Implement `check(signal, context) → GuardResult`
- **Registration:** Auto-discovered by pipeline (add to `__init__.py` exports)

### New React Component
- **Feature component:** `frontend/src/components/{feature}/{ComponentName}.tsx`
- **Page component:** `frontend/src/app/{route}/page.tsx`
- **Client component:** Add `"use client"` directive if using hooks/interactivity

### New Service
- **Implementation:** `src/services/{domain}_service.py`
- **Pattern:** Async functions with typed parameters, return domain objects
- **Error handling:** Raise domain exceptions, catch in API layer

### New Database Table
- **Migration:** `scripts/sql/{timestamp}_{change}.sql`
- **Supabase types:** Update `src/adapters/supabase.py` TypedDicts
- **Frontend types:** Update `frontend/src/lib/supabase.ts` TypeScript interfaces

## Special Directories

### `/.planning/`
- **Purpose:** GSD (Get Stuff Done) workflow artifacts
- **Contents:** Architecture docs, roadmaps, conventions
- **This directory:** Created by gsd-codebase-mapper agent

### `/.claude/skills/`
- **Purpose:** Claude Code custom skills
- **Pattern:** SKILL.md files for domain-specific agent behaviors

### `/scripts/pinescript/`
- **Purpose:** TradingView strategy files (.pine)
- **Usage:** Copied to TradingView Pinescript editor

### `/scripts/sql/`
- **Purpose:** Database migrations
- **Pattern:** Manual migration tracking (no ORM migrations)

---

