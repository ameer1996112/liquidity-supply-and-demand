# STRUCTURE.md — Directory Structure

## Root Layout

```
trading/                        ← Project root (PYTHONPATH=/workspace → maps here)
├── src/                        ← Python backend source
├── config/                     ← Settings + logging
├── tests/                      ← Python test suite
├── frontend/                   ← Next.js 16 app
├── docs/                       ← Documentation
├── scripts/                    ← Utility scripts
├── migrations/                 ← DB migration files
├── ml/                         ← ML model artifacts / training notebooks
├── data/                       ← Data files (gitignored datasets)
├── plans/                      ← Legacy planning docs
├── .planning/                  ← GSD planning system (codebase maps, STATE.md, todos)
├── .agent/                     ← GSD agent skills and workflows
├── .agents/                    ← Agent skill library (parallel/subagent skills)
├── requirements.txt            ← Python dependencies
├── start.sh                    ← Multi-service launcher: ./start.sh fullstack|api|worker|frontend
├── AGENTS.md                   ← Agent instructions (architecture, gotchas, commands)
├── Makefile                    ← Dev convenience targets
├── docker-compose.yml          ← Container stack
├── Dockerfile.api              ← API service image
├── Dockerfile.worker           ← Worker service image
├── railway.json                ← Railway deployment config
├── nixpacks.toml               ← API nixpacks build
├── nixpacks.worker.toml        ← Worker nixpacks build
├── .env                        ← Local environment (gitignored)
└── .env.example                ← All env var reference with docs
```

---

## Backend: `src/`

```
src/
├── __init__.py
├── api.py                      ← FastAPI app entrypoint (923 lines) — routers, middleware, /webhook
├── worker.py                   ← Signal consumer loop (87KB — largest file)
├── logic.py                    ← Shared business logic utilities (41KB)
│
├── api_*.py                    ← Route modules (one file per domain area):
│   ├── api_accounts.py         ← Multi-account management
│   ├── api_admin.py            ← Admin controls
│   ├── api_ai_runs.py          ← AI/debate decision log
│   ├── api_alerts.py           ← Alert management
│   ├── api_analytics.py        ← Historical analytics (22KB)
│   ├── api_analytics_signals_perf.py  ← v1.1 signal performance
│   ├── api_backtests.py        ← Backtest lab
│   ├── api_copilot.py          ← AI copilot chat (12KB)
│   ├── api_evaluation.py       ← Prop firm evaluation
│   ├── api_execution.py        ← Execution quality
│   ├── api_funding.py          ← Daily PnL / funding stats
│   ├── api_health_trading.py   ← v1.1 trading health widget
│   ├── api_incidents.py        ← Auto-incident creation
│   ├── api_market.py           ← Yahoo Finance CORS proxy
│   ├── api_portfolio.py        ← Portfolio overview (14KB)
│   ├── api_portfolio_control.py← Portfolio Command Center (83KB — largest router)
│   ├── api_positions.py        ← Open positions (23KB)
│   ├── api_prop_firm.py        ← Prop firm metrics (8KB)
│   ├── api_prop_firm_v1.py     ← Phase 1 prop firm endpoints
│   ├── api_risk.py             ← Risk settings (19KB)
│   ├── api_risk_monitor.py     ← Real-time risk monitor (21KB)
│   ├── api_rules.py            ← Rule management
│   ├── api_strategies.py       ← Strategy-as-data configs
│   ├── api_tickets.py          ← Jira proxy (39KB)
│   ├── api_traces.py           ← Latency pipeline traces
│   └── api_webhook_read.py     ← Read-side webhook data
│
├── adapters/                   ← External I/O adapters
│   ├── discord.py              ← Discord notifications (27KB)
│   ├── market_data.py          ← Live price quotes
│   ├── metaapi.py              ← MetaAPI thin wrapper
│   ├── paper_trader.py         ← Simulated execution (11KB)
│   ├── redis_queue.py          ← Queue enqueue/dequeue
│   ├── supabase.py             ← Supabase client + all DB operations (41KB)
│   ├── supabase_api.py         ← API-layer supabase helpers
│   └── execution/              ← Execution adapters (MetaAPI order flow)
│
├── core/                       ← Domain logic (pure, no side effects ideal)
│   ├── account_router.py       ← Symbol → account mapping
│   ├── broker_profiles.py      ← Multi-broker profile loading
│   ├── circuit_breaker.py      ← Trading circuit breaker state
│   ├── consumer_validator.py   ← Worker-side payload validation
│   ├── dynamic_config.py       ← Runtime config overrides (11KB)
│   ├── news_filter.py          ← High-impact news blocking
│   ├── risk_engine.py          ← Trinity + dynamic risk (17KB)
│   ├── signal.py               ← Signal schema + validation (shared API/Worker)
│   ├── transport.py            ← Pluggable queue transport
│   ├── guard_rails/            ← Sequential pre-execution filters:
│   │   ├── staleness_guard.py  ← Max signal age check
│   │   ├── market_filter.py    ← Trading hours + session filter (28KB)
│   │   ├── pine_guardian.py    ← Pine Script rule mirror (43KB — largest guard)
│   │   ├── correlation.py      ← Cross-pair correlation matrix (28KB)
│   │   ├── portfolio_var_guard.py ← Portfolio VaR limit
│   │   ├── prop_guard.py       ← Prop firm phase rules
│   │   └── sector_guard.py     ← Sector exposure limits
│   └── observers/              ← Worker pipeline hooks:
│       ├── base.py             ← Observer base class + registry
│       ├── auditor.py          ← Audit log observer
│       ├── executor.py         ← Trade execution observer
│       ├── metrics.py          ← Latency metrics observer
│       ├── risk_observer.py    ← Risk gate observer
│       └── account_router_observer.py
│
├── ai/                         ← AI/ML decision layer
│   ├── llm_client.py           ← Unified LLM client (OpenAI/Anthropic/Gemini)
│   ├── ai_guardian.py          ← LLM signal quality check (26KB)
│   ├── ml_guardian.py          ← Random Forest win probability (20KB)
│   ├── brain.py                ← EnsembleBrain orchestrator (59KB — largest AI file)
│   ├── trading_council.py      ← Multi-agent Bull/Bear/Risk/Chair debate (38KB)
│   ├── debate.py               ← Debate orchestration
│   ├── features.py             ← ML feature extraction
│   ├── rag_engine.py           ← RAG memory retrieval
│   └── council_memory.py       ← Council decision memory
│
├── agents/                     ← LangChain-style trading agents
│   ├── quant_agent.py          ← Quantitative analysis agent
│   ├── risk_agent.py           ← Risk assessment agent
│   └── supervisor.py           ← Agent supervisor
│
├── services/                   ← Business logic services (36 files)
│   ├── account_orchestrator.py ← Multi-account trade orchestration (28KB)
│   ├── account_sync_service.py ← MetaAPI → Supabase sync (23KB)
│   ├── ai_decision_cache.py    ← Decision caching
│   ├── ai_mode_override.py     ← Shadow/enforce mode toggle
│   ├── ai_run_service.py       ← AI run persistence
│   ├── alert_engine.py         ← Alert generation logic (13KB)
│   ├── alert_service.py        ← Alert CRUD (12KB)
│   ├── background_sync_worker.py ← Periodic MetaAPI sync
│   ├── backtest_engine.py      ← Strategy backtesting
│   ├── breakeven_manager.py    ← BE stop management (13KB)
│   ├── broker_reconciliation.py← Trade reconciliation (12KB)
│   ├── consistency_analyzer.py ← FTMO 40% consistency rule (11KB)
│   ├── daily_reset_scheduler.py← Daily state resets
│   ├── evaluation_tracker.py   ← Prop firm evaluation (13KB)
│   ├── execution_engine.py     ← Order execution + fills (14KB)
│   ├── graduation_service.py   ← AI shadow→enforce graduation
│   ├── hedging_engine.py       ← Hedge pair management (14KB)
│   ├── historical_returns.py   ← Return calculation
│   ├── mtm_guardian.py         ← Real-time floating PnL (15KB)
│   ├── pine_streak.py          ← Multi-day profitable streak tracking (8KB)
│   ├── portfolio_analyzer.py   ← Portfolio analytics (22KB)
│   ├── position_optimizer.py   ← Position sizing optimizer (12KB)
│   ├── prop_firm_tracker.py    ← Prop firm challenge tracking (15KB)
│   ├── redis_cache.py          ← Redis TTL caching wrapper
│   ├── reflection_service.py   ← Post-trade reflection & memory
│   ├── strategy_config.py      ← Strategy-as-data loader + validator
│   ├── symbol_mapper.py        ← Symbol → instrument mapping (10KB)
│   ├── tca_analyzer.py         ← Transaction cost analysis (16KB)
│   ├── trade_copier.py         ← Trade copy service (11KB)
│   ├── trailing_stop_manager.py← Trailing stop management (15KB)
│   ├── watchdog.py             ← Trade late-fill watchdog (20KB)
│   └── [ML classifiers, etc.]
│
├── backtest/                   ← Backtesting module
├── data/                       ← Runtime data files
└── utils/
    └── latency_tracker.py      ← Execution latency instrumentation
```

---

## Frontend: `frontend/src/`

```
frontend/src/
├── app/
│   ├── page.tsx                ← Main dashboard (25KB)
│   ├── layout.tsx              ← Root layout
│   ├── globals.css             ← Global styles (31KB)
│   ├── api/                    ← Next.js API routes (SSR)
│   ├── analytics/              ← Analytics dashboard
│   ├── accounts/               ← Account management
│   ├── alerts/                 ← Alert feed
│   ├── backtest/               ← Backtest lab
│   ├── execution-quality/      ← TCA & slippage
│   ├── journal/                ← Trade journal
│   ├── positions/              ← Open positions
│   ├── prop-firm/              ← Prop firm tracker
│   ├── risk/                   ← Risk configuration
│   ├── rules/                  ← Rule editor
│   ├── scanner/                ← Signal scanner
│   ├── settings/               ← App settings
│   ├── strategies/             ← Strategy configs
│   └── tickets/                ← Jira-style board
├── components/                 ← Shared components
├── domain/                     ← Domain logic (pure functions, types)
├── hooks/                      ← Data-fetching hooks
├── lib/                        ← API client, utils
├── providers/                  ← React Context providers
└── types/                      ← TypeScript types
```

---

## Config: `config/`

```
config/
├── __init__.py                 ← Exports get_settings()
├── settings.py                 ← Settings class (469 lines, @lru_cache)
└── logging_config.py           ← Structured logging setup
```

---

## Tests: `tests/`

```
tests/
├── conftest.py                 ← Shared fixtures + InMemoryTransport setup
├── conftest_incidents.py       ← Incident test fixtures
├── test_e2e.py                 ← End-to-end signal pipeline (21KB)
├── test_pipeline.py            ← Worker pipeline tests (11KB)
├── test_pipeline_traces.py     ← Latency trace tests (19KB)
├── test_worker_observers.py    ← Observer tests (17KB)
├── test_pine_guardian_adaptive.py ← PineGuardian adaptive limits
├── test_sprint55_reliability.py ← Reliability regression suite (18KB)
├── test_account_routing.py     ← Multi-account routing (20KB)
├── test_ai_brain.py            ← EnsembleBrain tests (14KB)
├── test_debate.py              ← Trading council debate (11KB)
├── test_llm_client.py          ← LLM client tests (11KB)
├── test_reflection_memory.py   ← Memory/reflection tests
├── test_backtests.py           ← Backtest engine tests
├── test_consumer_validation.py ← Payload validation
├── test_signal_transport.py    ← Transport abstraction
├── test_strategy_config.py     ← Strategy-as-data configs
├── test_graduation.py          ← AI graduation logic
├── test_api_tickets.py         ← Jira proxy tests
└── test_*.py                   ← Domain-specific suites
```

---

## Key Naming Conventions

| Pattern | Meaning |
|---------|---------|
| `api_*.py` | FastAPI router module (one domain per file) |
| `*_service.py` | Business logic service in `src/services/` |
| `*_guard.py` | Guard rail filter in `src/core/guard_rails/` |
| `*_adapter.py` or file in `adapters/` | External I/O |
| `*_observer.py` | Pipeline observer hook |
| `test_*.py` | Test file |
| `*.pine` | Pine Script source |
