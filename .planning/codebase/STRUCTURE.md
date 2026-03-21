# STRUCTURE.md — Directory Layout

## Top-Level

```
/trading
├── src/                    # Backend Python source
├── config/                 # Settings + logging config
├── tests/                  # pytest test suite
├── frontend/               # Next.js dashboard
├── docs/                   # Documentation (webhook-payload-reference.md)
├── scripts/                # Utility scripts (simulate_signal.py, etc.)
├── .planning/              # GSD planning artifacts
├── .agent/                 # GSD workflow config
├── .env.example            # Environment variable reference
├── start.sh                # Local full-stack launcher
├── AGENTS.md               # Architecture + gotchas for AI agents
└── venv/                   # Python virtual environment
```

## `src/` — Backend Source

```
src/
├── api.py                      # Main FastAPI app — /webhook, /webhook/test, /health
├── api_analytics.py            # Analytics router — /analytics/*
├── api_risk.py                 # Risk router — /risk/*
├── api_positions.py            # Positions router — /positions/*
├── api_funding.py              # Funding router — /funding/*
├── api_evaluation.py           # Evaluation router — /evaluation/*
├── api_execution.py            # Execution quality router
├── api_rules.py                # Dynamic config rules — /rules/*
├── api_backtests.py            # Backtesting router
├── api_strategies.py           # Strategies router
├── api_board.py                # Trading board router
├── api_portfolio_control.py    # Portfolio control router
├── api_copilot.py              # AI copilot router
├── api_traces.py               # Pipeline traces router
├── worker.py                   # Worker entrypoint (consumer loop)
├── logic.py                    # Trade execution logic
├── __init__.py
│
├── core/                       # Core business logic
│   ├── signal.py               # EntryWebhookPayload Pydantic model
│   ├── risk_engine.py          # Lot size calculation
│   ├── transport.py            # Redis vs memory queue abstraction
│   ├── account_router.py       # Account routing from signal
│   ├── circuit_breaker.py      # Per-account circuit breaker
│   ├── dynamic_config.py       # Runtime config from DB
│   ├── consumer_validator.py   # Worker-side payload validation
│   ├── news_filter.py          # News event filter
│   ├── broker_profiles.py      # Broker-specific configs
│   │
│   ├── guard_rails/            # Risk guard plugins
│   │   ├── prop_guard.py       # Prop firm guards (RR, consec losses)
│   │   ├── staleness_guard.py  # Bar time staleness check
│   │   ├── correlation.py      # Correlation exposure guard
│   │   ├── portfolio_var_guard.py # Portfolio VaR check
│   │   ├── sector_guard.py     # Sector concentration
│   │   ├── market_filter.py    # Market hours filter
│   │   └── pine_guardian.py    # Pine Script signal validation
│   │
│   └── observers/              # Observer pattern (side effects)
│       ├── auditor.py          # Trade audit logging
│       ├── executor.py         # Execution observer
│       ├── risk_observer.py    # Risk metric tracking
│       ├── metrics.py          # Performance metrics
│       ├── account_router_observer.py
│       └── base.py             # Observer base class
│
├── adapters/                   # External service adapters
│   ├── metaapi.py              # MetaAPI broker adapter
│   ├── paper_trader.py         # Paper trading simulator
│   ├── supabase.py             # Worker Supabase client
│   ├── supabase_api.py         # API Supabase client (auto-reconnect)
│   ├── redis_queue.py          # Redis client
│   ├── discord.py              # Discord notifications
│   ├── market_data.py          # Market data fetching
│   └── execution/              # Execution adapters
│
├── ai/                         # AI/ML layer
│   └── brain.py                # LLM guardian + prediction
│
├── agents/                     # Multi-agent supervisor
│   └── supervisor.py
│
└── services/                   # Background services
    ├── trailing_stop_manager.py
    ├── breakeven_manager.py
    ├── trade_events.py         # Trade event logging helpers
    └── watchdog.py             # Trade watchdog service
```

## `config/` — Configuration

```
config/
├── settings.py                 # Pydantic BaseSettings, @lru_cache get_settings()
└── logging_config.py           # Structured logging setup
```

## `frontend/src/` — Frontend Source

```
frontend/src/
├── app/                        # Next.js App Router pages
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Dashboard (/)
│   ├── analytics/              # Analytics page (/analytics)
│   ├── positions/              # Positions (/positions)
│   ├── risk/                   # Risk monitor (/risk)
│   ├── prop-firm/              # Prop firm (/prop-firm)
│   ├── accounts/               # Account management (/accounts)
│   ├── alerts/                 # Alerts (/alerts)
│   ├── backtest/               # Backtesting (/backtest)
│   ├── board/                  # Trading board (/board)
│   ├── execution-quality/      # Execution analytics (/execution-quality)
│   ├── journal/                # Trade journal (/journal)
│   ├── rules/                  # Dynamic rules (/rules)
│   ├── scanner/                # Market scanner (/scanner)
│   ├── settings/               # Settings (/settings)
│   ├── strategies/             # Strategies (/strategies)
│   └── api/                    # API routes (if any)
│
├── components/                 # Shared components
│   ├── SignalCard.tsx           # Signal display card
│   ├── SignalFeed.tsx           # Live signal feed list
│   ├── SignalGrid.tsx           # Grid layout for signals
│   ├── SignalInspector.tsx      # Signal detail inspector
│   ├── StatsTicker.tsx          # Stats ticker strip
│   ├── ConnectionStatus.tsx     # API connection indicator
│   ├── DebugStatus.tsx          # Debug status panel
│   └── [feature]/              # Feature-specific components
│
└── hooks/                      # React hooks (data fetching)
    ├── useAnalytics.ts          # /analytics/* data
    ├── usePositions.ts          # /positions/* data
    ├── usePropFirm.ts           # /prop-firm data
    ├── useAccounts.ts           # /accounts data
    ├── useLiveTrading.ts        # Live signal feed
    ├── usePortfolioRisk.ts      # Risk data
    └── [20+ hooks total]
```

## Where to Add New Features

| Feature type | Location |
|-------------|----------|
| New API endpoint | New `src/api_[name].py`, mount in `src/api.py` |
| New guard rail | `src/core/guard_rails/[name]_guard.py` |
| New pydantic schema | `src/core/signal.py` or new `src/core/[name].py` |
| New frontend page | `frontend/src/app/[route]/page.tsx` |
| New data hook | `frontend/src/hooks/use[Feature].ts` |
| New component | `frontend/src/components/[Feature]/` |
| New adapter | `src/adapters/[service].py` |
| New test | `tests/test_[feature].py` |
