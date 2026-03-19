# Structure

## Directory Layout

```
trading/
├── src/                          # Python backend
│   ├── api.py                    # FastAPI app entry point (API service)
│   ├── worker.py                 # Consumer/executor entry point (Worker service)
│   ├── logic.py                  # Trade execution logic (used by worker)
│   ├── api_*.py                  # Feature routers (20+ domain routers)
│   ├── core/                     # Pure domain logic
│   │   ├── risk_engine.py        # Risk calculations (no I/O)
│   │   ├── signal.py             # Signal validation
│   │   ├── transport.py          # Signal transport abstraction
│   │   ├── account_router.py     # Multi-account routing
│   │   ├── consumer_validator.py # Queue message validation
│   │   ├── guard_rails/          # Guard chain implementations
│   │   │   ├── correlation.py
│   │   │   ├── portfolio_var_guard.py
│   │   │   ├── prop_guard.py
│   │   │   ├── sector_guard.py
│   │   │   ├── staleness_guard.py
│   │   │   └── pine_guardian.py
│   │   └── observers/            # Observer pattern implementations
│   ├── services/                 # Application services (with I/O)
│   │   ├── execution_engine.py   # TCA-wrapped order execution
│   │   ├── account_orchestrator.py
│   │   ├── alert_engine.py
│   │   ├── backtest_engine.py
│   │   ├── broker_reconciliation.py
│   │   ├── graduation_service.py
│   │   ├── position_optimizer.py
│   │   ├── prop_firm_tracker.py
│   │   ├── redis_cache.py
│   │   ├── watchdog.py
│   │   └── ...
│   ├── ai/                       # AI/ML components
│   │   ├── brain.py              # Ensemble v9.1 (RF + RAG + LLM)
│   │   ├── debate.py             # LLM debate council
│   │   ├── trading_council.py    # AI council orchestration
│   │   ├── rag_engine.py         # RAG retrieval
│   │   ├── ml_guardian.py        # ML guard
│   │   ├── ai_guardian.py        # AI guard
│   │   ├── features.py           # Feature engineering
│   │   └── llm_client.py         # LLM client abstraction
│   ├── adapters/                 # External service adapters
│   │   ├── supabase.py           # Database adapter
│   │   ├── metaapi.py            # MetaAPI broker adapter
│   │   ├── redis_queue.py        # Redis adapter
│   │   ├── discord.py            # Discord/Telegram notifications
│   │   ├── market_data.py        # Market data (Yahoo Finance)
│   │   ├── paper_trader.py       # Paper trading adapter
│   │   └── execution/            # Execution adapters (live/paper)
│   ├── agents/                   # Background AI agents
│   ├── backtest/                 # Backtesting engine
│   └── data/                     # Data utilities
├── frontend/                     # Next.js frontend
│   ├── src/
│   │   ├── app/                  # Next.js App Router pages
│   │   │   ├── accounts/
│   │   │   ├── analytics/
│   │   │   ├── board/
│   │   │   ├── backtest/
│   │   │   ├── execution-quality/
│   │   │   ├── journal/
│   │   │   ├── positions/
│   │   │   ├── prop-firm/
│   │   │   ├── risk/
│   │   │   ├── rules/
│   │   │   ├── settings/
│   │   │   └── ...
│   │   ├── components/           # React components (feature-organized)
│   │   │   ├── shared/           # Shared/reusable components
│   │   │   ├── ui/               # Base UI primitives
│   │   │   ├── dashboard/
│   │   │   ├── positions/
│   │   │   ├── analytics/
│   │   │   └── ...
│   │   ├── hooks/                # Custom React hooks (useX.ts pattern)
│   │   ├── domain/               # Business types and models
│   │   ├── lib/                  # Utilities
│   │   ├── providers/            # React context providers
│   │   └── types/                # TypeScript type definitions
│   ├── vitest.config.ts          # Frontend test config
│   └── next.config.ts
├── config/
│   ├── settings.py               # Pydantic settings (env-var driven)
│   └── logging_config.py
├── migrations/                   # Supabase SQL migrations (028 files)
├── tests/                        # Python test suite (pytest)
├── scripts/                      # Admin/maintenance scripts
├── ml/                           # ML training/data scripts
├── docs/                         # Decision log, bugs, worklog
├── plans/                        # Feature plans
├── Dockerfile / Dockerfile.api / Dockerfile.worker
├── docker-compose.yml
├── requirements.txt
├── nixpacks.toml / nixpacks.worker.toml
└── railway.json
```

## Key File Locations

| Purpose | Path |
|---------|------|
| API entry point | `src/api.py` |
| Worker entry point | `src/worker.py` |
| Trade execution | `src/logic.py` |
| Risk calculations | `src/core/risk_engine.py` |
| Settings/config | `config/settings.py` |
| DB adapter | `src/adapters/supabase.py` |
| Broker adapter | `src/adapters/metaapi.py` |
| Redis adapter | `src/adapters/redis_queue.py` |
| AI ensemble | `src/ai/brain.py` |
| Frontend pages | `frontend/src/app/` |
| Frontend hooks | `frontend/src/hooks/` |
| DB migrations | `migrations/*.sql` |
| Python tests | `tests/` |
| Frontend tests | Co-located `*.test.tsx` |

## Naming Conventions

- **Backend routers:** `src/api_<domain>.py` (e.g., `api_positions.py`, `api_analytics.py`)
- **Services:** `src/services/<name>_service.py` or `src/services/<name>.py`
- **Frontend hooks:** `use<Domain>.ts` (e.g., `usePositions.ts`, `useAnalytics.ts`)
- **Frontend components:** PascalCase, co-located with feature folder
- **DB migrations:** Zero-padded number + description (e.g., `028_accounts.sql`)
- **Tests:** `tests/test_<module>.py` (Python), `<Component>.test.tsx` (frontend)
