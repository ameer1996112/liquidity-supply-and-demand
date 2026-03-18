# Directory Structure

## Root Layout

```
trading/
├── config/               # Centralized configuration
│   ├── settings.py       # Pydantic BaseSettings (431 lines, 100+ fields)
│   └── logging_config.py # Structured logging setup
├── src/                  # Backend Python source
│   ├── api.py            # FastAPI main app (30KB)
│   ├── api_*.py          # Route modules (20+ files)
│   ├── logic.py          # Shared business logic (37KB)
│   ├── worker.py         # Signal consumer/executor (82KB)
│   ├── adapters/         # External service adapters
│   │   ├── execution/    # Trade execution (MetaAPI, Paper, DryRun)
│   │   ├── supabase.py   # Database adapter (41KB)
│   │   ├── redis_queue.py# Signal queue
│   │   ├── discord.py    # Notifications
│   │   └── market_data.py# Market data (yfinance)
│   ├── ai/               # AI/ML decision layer
│   │   ├── brain.py      # Ensemble decision engine (59KB)
│   │   ├── trading_council.py  # Multi-agent debate (39KB)
│   │   ├── ai_guardian.py      # LLM trade validation (27KB)
│   │   ├── ml_guardian.py      # ML model predictions (20KB)
│   │   ├── debate.py     # Bull/Bear debate
│   │   ├── rag_engine.py # RAG for trade context
│   │   └── llm_client.py # Unified LLM client
│   ├── core/             # Core domain logic
│   │   ├── guard_rails/  # 7 pre-execution filters
│   │   ├── risk_engine.py# Position sizing
│   │   ├── signal.py     # Signal data model
│   │   ├── transport.py  # Signal transport abstraction
│   │   └── circuit_breaker.py
│   ├── services/         # Business services (35+ files)
│   │   ├── execution_engine.py
│   │   ├── account_orchestrator.py
│   │   ├── portfolio_analyzer.py
│   │   ├── prop_firm_tracker.py
│   │   └── ... (30+ more)
│   ├── data/             # Data files
│   └── utils/            # Utilities (latency_tracker.py)
├── frontend/             # Next.js frontend
│   ├── src/
│   │   ├── app/          # App Router pages (15 routes)
│   │   ├── components/   # UI components (22 folders + shared)
│   │   ├── hooks/        # Custom hooks (28 files)
│   │   ├── lib/          # API client, Supabase, formatters
│   │   ├── domain/       # Domain logic (metrics)
│   │   ├── providers/    # React providers
│   │   └── types/        # TypeScript types
│   ├── package.json      # Dependencies
│   └── tsconfig.json     # TypeScript config
├── tests/                # Pytest test suite (21 files)
├── ml/                   # ML model data/artifacts
├── data/                 # Data files
├── scripts/              # Utility scripts
├── migrations/           # Database migrations
├── docs/                 # Documentation
├── plans/                # Legacy planning docs
├── docker-compose.yml    # 4-service Docker setup
├── requirements.txt      # Python dependencies
├── start.sh              # Full-stack launcher
├── .env                  # Environment variables
└── .env.example          # Config reference (10KB)
```

## Key Locations

| Purpose | Path |
|---------|------|
| Configuration | `config/settings.py` |
| API entry point | `src/api.py` |
| Worker entry point | `src/worker.py` |
| Webhook handler | `src/api.py` → `POST /webhook` |
| Trade execution | `src/services/execution_engine.py` |
| MetaAPI adapter | `src/adapters/execution/meta_api_adapter.py` |
| AI decision brain | `src/ai/brain.py` |
| Trading council | `src/ai/trading_council.py` |
| ML models | `src/ai/ml_guardian.py` |
| Guard rails | `src/core/guard_rails/*.py` |
| Risk engine | `src/core/risk_engine.py` |
| Database adapter | `src/adapters/supabase.py` |
| Frontend API client | `frontend/src/lib/api.ts` |
| Frontend Supabase | `frontend/src/lib/supabase.ts` |
| Dashboard page | `frontend/src/app/page.tsx` |
| Environment config | `.env` + `.env.example` |
| Docker setup | `docker-compose.yml` |

## Naming Conventions

- **Backend routes**: `api_*.py` (e.g., `api_positions.py`, `api_analytics.py`)
- **Backend services**: `*_service.py`, `*_engine.py`, `*_analyzer.py`, `*_manager.py`
- **Guard rails**: `*_guard.py`, `*_filter.py`, `*_guardian.py`
- **Frontend hooks**: `use*.ts` (e.g., `usePositions.ts`, `useAnalytics.ts`)
- **Frontend components**: PascalCase `.tsx` (e.g., `SignalCard.tsx`, `SignalFeed.tsx`)
- **Frontend pages**: `app/[route]/page.tsx` (Next.js App Router)
