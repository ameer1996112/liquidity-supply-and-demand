# STRUCTURE.md — Directory Layout & Organization

## Top-Level Structure

```
/trading
├── src/                    # Backend Python source (API + Worker)
├── frontend/               # Next.js 16 dashboard
├── jira/                   # Standalone Jira-like project management app
├── config/                 # Pydantic settings + logging
├── tests/                  # Backend pytest test suite
├── migrations/             # 57+ Supabase SQL migration files
├── scripts/                # One-off utility/maintenance scripts
├── ml/                     # ML data ingestion utilities
├── docs/                   # Documentation
├── data/                   # Pine Script strategy files + training data
├── plans/                  # Historical implementation plans (markdown)
├── .planning/              # GSD planning artifacts
│   └── codebase/           # ← This codebase map
├── .agent/ .agents/        # GSD agent skills + workflows
├── requirements.txt        # Python dependencies
├── Dockerfile / Dockerfile.api / Dockerfile.worker
├── docker-compose.yml
├── railway.json / nixpacks.toml
├── start.sh                # Multi-service launcher
└── Makefile                # Dev shortcuts
```

## Backend Source (`src/`)

```
src/
├── api.py                  # Main FastAPI app + webhook endpoint (36KB)
├── worker.py               # Signal consumer + pipeline orchestrator (85KB)
├── logic.py                # Core business logic utilities (41KB)
│
├── api_*.py                # Router modules (prefix-mounted in api.py):
│   ├── api_accounts.py     # Account management
│   ├── api_admin.py        # Admin endpoints
│   ├── api_ai_runs.py      # AI decision history
│   ├── api_alerts.py       # Alerts CRUD + history (11KB)
│   ├── api_analytics.py    # PnL analytics + metrics (22KB)
│   ├── api_backtests.py    # Backtest execution
│   ├── api_copilot.py      # AI copilot queries (12KB)
│   ├── api_evaluation.py   # Prop firm evaluation tracking
│   ├── api_execution.py    # Manual order execution (9.5KB)
│   ├── api_funding.py      # Funding/swap rates
│   ├── api_market.py       # Market data endpoints
│   ├── api_portfolio.py    # Portfolio summary (14KB)
│   ├── api_portfolio_control.py  # Portfolio risk control (83KB — largest file)
│   ├── api_positions.py    # Open positions (23KB)
│   ├── api_prop_firm.py    # Prop firm metrics (8.4KB)
│   ├── api_prop_firm_v1.py # Prop firm v1 (legacy)
│   ├── api_risk.py         # Risk exposure (19KB)
│   ├── api_risk_monitor.py # Real-time risk monitor (21KB)
│   ├── api_rules.py        # Trading rules config
│   ├── api_strategies.py   # Strategy configuration
│   ├── api_tickets.py      # Jira proxy + ticket management (22KB)
│   ├── api_traces.py       # Execution trace log (10KB)
│   └── api_webhook_read.py # Webhook signal read (9.8KB)
│
├── adapters/               # External service adapters
│   ├── discord.py          # Discord notifications (27KB)
│   ├── market_data.py      # Market data aggregation
│   ├── paper_trader.py     # Paper trading simulator (11KB)
│   ├── redis_queue.py      # Redis signal queue
│   ├── supabase.py         # Supabase data access layer (41KB — primary DB client)
│   ├── supabase_api.py     # Supabase REST helper
│   └── execution/          # MetaAPI execution adapter
│
├── ai/                     # AI/ML guardrail stack
│   ├── brain.py            # Ensemble orchestrator (59KB)
│   ├── ai_guardian.py      # LLM signal validator (26KB)
│   ├── ml_guardian.py      # LightGBM win-probability (20KB)
│   ├── trading_council.py  # Multi-agent debate system (38KB)
│   ├── debate.py           # Bull/Bear/Risk/Chair debate
│   ├── rag_engine.py       # BM25 + LangChain retrieval
│   ├── llm_client.py       # Unified LLM client (9.6KB)
│   ├── features.py         # Feature engineering for ML
│   └── council_memory.py   # Trading council memory
│
├── core/                   # Domain logic
│   ├── signal.py           # Signal data model
│   ├── risk_engine.py      # Position sizing (17KB)
│   ├── transport.py        # Redis/memory signal transport (10KB)
│   ├── dynamic_config.py   # Runtime config overrides (12KB)
│   ├── account_router.py   # Multi-account routing
│   ├── consumer_validator.py # Payload validation
│   ├── circuit_breaker.py  # Circuit breaker pattern
│   ├── news_filter.py      # News event filtering
│   ├── broker_profiles.py  # Broker profile management
│   ├── guard_rails/        # Each is an independent filter
│   │   ├── pine_guardian.py      # Pine Script rule mirroring (26KB)
│   │   ├── staleness_guard.py    # Signal freshness check (15KB)
│   │   ├── correlation.py        # Correlation matrix (28KB)
│   │   ├── market_filter.py      # Market session filter (28KB)
│   │   ├── portfolio_var_guard.py # VaR limit
│   │   ├── sector_guard.py       # Sector exposure
│   │   └── prop_guard.py         # Prop firm compliance
│   └── observers/          # Event observer pattern
│
├── services/               # Business services (35 files, ~400KB total)
│   ├── account_orchestrator.py   # Multi-account orchestration (28KB)
│   ├── account_sync_service.py   # MetaAPI account sync (23KB)
│   ├── alert_engine.py           # Alert rule engine (13KB)
│   ├── backtest_engine.py        # Strategy backtesting (9.6KB)
│   ├── breakeven_manager.py      # Auto-breakeven (13KB)
│   ├── broker_reconciliation.py  # Trade reconciliation (12KB)
│   ├── execution_engine.py       # Execution orchestration (14KB)
│   ├── hedging_engine.py         # Position hedging (14KB)
│   ├── mtm_guardian.py           # Real-time floating PnL (15KB)
│   ├── portfolio_analyzer.py     # Portfolio analysis (22KB)
│   ├── prop_firm_tracker.py      # Prop firm evaluation (16KB)
│   ├── tca_analyzer.py           # Transaction cost analysis (17KB)
│   ├── trailing_stop_manager.py  # Trailing stops (15KB)
│   ├── watchdog.py               # Trade fill watchdog (20KB)
│   └── ...
│
├── backtest/               # Backtesting modules
├── data/                   # Data access utilities
└── utils/                  # Shared utilities
```

## Frontend Source (`frontend/src/`)

```
frontend/src/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Dashboard (25KB)
│   ├── globals.css         # Global styles (31KB)
│   ├── api/                # API route handlers (server-side)
│   ├── accounts/           # Account management page
│   ├── alerts/             # Alert configuration page
│   ├── analytics/          # Analytics + charts page
│   ├── backtest/           # Backtesting UI page
│   ├── execution-quality/  # TCA metrics page
│   ├── journal/            # Trade journal
│   ├── positions/          # Open positions page
│   ├── prop-firm/          # Prop firm metrics
│   ├── risk/               # Risk exposure page
│   ├── rules/              # Trading rules config
│   ├── scanner/            # Market scanner
│   ├── settings/           # Settings page
│   ├── strategies/         # Strategy management
│   └── tickets/            # Project board (Jira-like)
├── components/             # Reusable UI components
├── domain/                 # Domain types and business logic
├── hooks/                  # Custom React hooks
├── lib/                    # Utility libraries
├── providers/              # React context providers
└── types/                  # TypeScript type definitions
```

## Configuration & Config (`config/`)

```
config/
├── __init__.py             # Exports get_settings()
├── settings.py             # Pydantic BaseSettings (460 lines, 400+ vars)
└── logging_config.py       # Logging configuration (5KB)
```

## Key Naming Conventions

- **API routers**: `src/api_<domain>.py` (prefix-mounted in `api.py`)
- **Services**: `src/services/<domain>_<role>.py`
- **Adapters**: `src/adapters/<service>.py`
- **Guard rails**: `src/core/guard_rails/<name>_guard.py`
- **Tests**: `tests/test_<what>.py` (mirrors src module name)
- **Migrations**: `migrations/<NNN>_<description>.sql` (sequential numbered)
- **Planning**: `.planning/<milestone>/<phase>/` with `PLAN.md`, `STATE.md`

## Important Files

| File | Purpose |
|---|---|
| `src/worker.py` | The heart of the system — 85KB orchestration |
| `src/ai/brain.py` | AI ensemble logic — 59KB |
| `src/adapters/supabase.py` | All DB operations — 41KB |
| `src/api_portfolio_control.py` | Portfolio control — 83KB (largest) |
| `config/settings.py` | Every config var — 460 lines |
| `requirements.txt` | Python dependencies |
| `frontend/package.json` | Frontend dependencies |
| `start.sh` | Multi-service launcher script |
| `.env` / `.env.example` | Config template (11KB example) |
