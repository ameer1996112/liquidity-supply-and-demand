# STRUCTURE.md — Directory Layout

## Root Level

```
trading/
├── src/                    # Python backend (API + Worker + Domain)
├── frontend/               # Next.js frontend
├── tests/                  # Python backend tests
├── config/                 # Backend config (settings.py)
├── ml/                     # ML model files, training scripts
├── migrations/             # Database migrations (Supabase)
├── docs/                   # Documentation
├── scripts/                # Utility scripts (simulate_signal.py, etc.)
├── plans/                  # Planning documents
├── data/                   # Data artifacts
├── .planning/              # GSD planning directory (codebase maps, roadmap)
├── .agent/                 # GSD agent configuration
├── .agents/                # Additional agent skills
├── .env                    # Local secrets (not committed)
├── .env.example            # Full reference for all env vars (264 lines)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Combined image
├── Dockerfile.api          # API-only image
├── Dockerfile.worker       # Worker-only image
├── docker-compose.yml      # Local full-stack compose
├── railway.json            # Railway deployment config
├── nixpacks.toml           # Nixpacks build spec (API)
├── nixpacks.worker.toml    # Nixpacks build spec (Worker)
├── start.sh                # Local dev orchestrator
├── Makefile                # Developer shortcuts
├── AGENTS.md               # AI agent instructions
└── TODO.md                 # Known issues and backlog
```

## Backend Source (`src/`)

```
src/
├── api.py                  # Main FastAPI app entry point (30KB)
├── api_accounts.py         # Account management endpoints
├── api_admin.py            # Admin endpoints
├── api_ai_runs.py          # AI run history endpoints
├── api_alerts.py           # Alert management
├── api_analytics.py        # Analytics dashboard endpoints (17KB)
├── api_backtests.py        # Backtest trigger/results
├── api_board.py            # Kanban board endpoints
├── api_copilot.py          # AI copilot (YouTube strategy research)
├── api_evaluation.py       # Prop firm evaluation endpoints
├── api_execution.py        # Execution trace endpoints (9KB)
├── api_funding.py          # Funding/account funding endpoints
├── api_market.py           # Market data endpoints
├── api_portfolio.py        # Portfolio data (14KB)
├── api_portfolio_control.py # Portfolio control (83KB — largest file!)
├── api_positions.py        # Open positions (21KB)
├── api_prop_firm.py        # Prop firm tracking (8KB)
├── api_risk.py             # Risk monitoring (19KB)
├── api_risk_monitor.py     # Real-time risk monitor (21KB)
├── api_rules.py            # Rules management
├── api_strategies.py       # Strategy config
├── api_traces.py           # Signal + execution traces (10KB)
├── api_webhook_read.py     # Webhook history read
├── logic.py                # Business logic utilities (37KB)
├── worker.py               # Worker process entry point (82KB)
│
├── adapters/               # External service integrations
│   ├── __init__.py
│   ├── discord.py          # Discord notifications (12KB)
│   ├── market_data.py      # yfinance market data (9KB)
│   ├── paper_trader.py     # Simulated execution (11KB)
│   ├── redis_queue.py      # Redis queue operations (3KB)
│   ├── supabase.py         # All DB operations (41KB)
│   ├── supabase_api.py     # Supabase API helpers
│   └── execution/
│       └── meta_api_adapter.py  # MetaTrader 5 via MetaAPI
│
├── ai/                     # AI/LLM ensemble
│   ├── __init__.py
│   ├── ai_guardian.py      # LLM signal confidence scoring (26KB)
│   ├── brain.py            # AI ensemble orchestrator (59KB)
│   ├── council_memory.py   # Trade situation memory
│   ├── debate.py           # Council debate logic
│   ├── features.py         # ML feature engineering
│   ├── llm_client.py       # Unified LLM client
│   ├── ml_guardian.py      # LightGBM win probability (20KB)
│   ├── rag_engine.py       # BM25 retrieval engine
│   └── trading_council.py  # Multi-agent debate (38KB)
│
├── core/                   # Domain/business logic
│   ├── __init__.py
│   ├── account_router.py   # Multi-account signal routing
│   ├── broker_profiles.py  # Broker symbol mappings (5KB)
│   ├── circuit_breaker.py  # Circuit breaker pattern
│   ├── consumer_validator.py # Webhook payload validation
│   ├── dynamic_config.py   # Runtime configuration (12KB)
│   ├── news_filter.py      # Market hours/news filter
│   ├── risk_engine.py      # Position sizing, R:R (17KB)
│   ├── signal.py           # Signal domain model
│   ├── transport.py        # Queue abstraction (10KB)
│   ├── guard_rails/        # Trade guard implementations
│   │   ├── correlation.py  # Correlation guard (28KB)
│   │   ├── market_filter.py # Market/session filter (28KB)
│   │   ├── pine_guardian.py # Pine Script alignment guard (26KB)
│   │   ├── portfolio_var_guard.py # Portfolio VaR
│   │   ├── prop_guard.py   # Prop firm limits
│   │   ├── sector_guard.py # Sector exposure guard
│   │   └── staleness_guard.py # Signal staleness (15KB)
│   ├── observers/          # Post-execution observers
│   └── ...
│
├── agents/                 # Background agent tasks
├── backtest/               # Backtesting framework
├── data/                   # Data models
├── services/               # Service layer
└── utils/                  # Shared utilities
```

## Frontend Source (`frontend/src/`)

```
frontend/src/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx          # Root layout (providers, nav)
│   ├── page.tsx            # Main dashboard (22KB)
│   ├── globals.css         # Global styles (25KB)
│   ├── accounts/           # Account management pages
│   ├── alerts/             # Alert pages
│   ├── analytics/          # Analytics charts/heatmaps
│   ├── backtest/           # ML backtest interface
│   ├── board/              # Kanban project board
│   ├── execution-quality/  # TCA + trace viewer
│   ├── journal/            # Trade journal
│   ├── positions/          # Open positions view
│   ├── prop-firm/          # Prop firm tracker
│   ├── risk/               # Risk dashboard
│   ├── rules/              # Trading rules/alerts config
│   ├── scanner/            # Market scanner
│   ├── settings/           # App settings
│   └── strategies/         # Strategy configuration
│
├── components/             # Reusable UI components
│   ├── dashboard/          # Dashboard-specific components
│   │   ├── RecentSignalsPanel.tsx
│   │   └── RecentSignalsPanel.test.tsx
│   ├── execution/          # Execution trace components
│   │   └── TraceTable.tsx
│   ├── SignalInspector.tsx
│   └── SignalInspector.test.tsx
│
├── domain/                 # TypeScript domain models
│   └── metrics/
│       ├── tradingMetrics.ts
│       └── tradingMetrics.test.ts  # ⚠️ Known pre-existing failure
│
├── hooks/                  # React custom hooks
├── lib/                    # Utilities (Supabase client setup, API client)
├── providers/              # React Context providers
│   ├── AuthProvider
│   ├── QueryClientProvider
│   └── WebSocketProvider (real-time logs)
└── types/                  # TypeScript type definitions
```

## Config Directory

```
config/
└── settings.py             # Pydantic Settings (all env vars, @lru_cache)
```

## Key File Sizes (Complexity Indicators)

| File | Size | Notes |
|------|------|-------|
| `src/api_portfolio_control.py` | 83KB | Largest file — portfolio controls |
| `src/worker.py` | 82KB | Full pipeline — growing unwieldy |
| `src/ai/brain.py` | 59KB | AI ensemble orchestrator |
| `src/adapters/supabase.py` | 41KB | All DB operations |
| `src/ai/trading_council.py` | 38KB | Multi-agent debate |
| `src/logic.py` | 37KB | Business logic |

## Naming Conventions

### Backend (Python)
- Modules: `snake_case` (e.g., `meta_api_adapter.py`)
- API routers: `api_{domain}.py` pattern
- Adapters: named by external service (e.g., `supabase.py`, `discord.py`)
- Guards: `{name}_guard.py` or `{name}_guardian.py`

### Frontend (TypeScript)
- Components: `PascalCase.tsx` (e.g., `TraceTable.tsx`)
- Hooks: `use{Name}.ts` (e.g., `useSignals.ts`)
- Pages: directory-based App Router convention (`app/{route}/page.tsx`)
- Tests: co-located `{Component}.test.tsx` or `{Module}.test.ts`
