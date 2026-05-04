# Module Map

## How to Use

When asked to work on a feature, find the module below and read **only** those files.
Do not scan the repository. Do not read files outside the relevant module.

---

## Modules

### Webhook Ingress
Receives TradingView webhooks, validates payloads, queues to Redis.

| File | Purpose |
|------|---------|
| `src/api.py` | Main FastAPI app, webhook handler, router registration |
| `config/settings.py` | Pydantic-settings (env var definitions, `get_settings()`) |
| `src/core/signal.py` | Signal schema and validation |
| `src/core/consumer_validator.py` | Dequeued message validation |

---

### Signal Pipeline
Consumes Redis queue, orchestrates guard rails → risk → execution.

| File | Purpose |
|------|---------|
| `src/worker.py` | Queue consumer, pipeline orchestrator (⚠️ 2000+ lines) |
| `src/pipeline/__init__.py` | Pipeline package exports |
| `src/pipeline/profile_executor.py` | Per-account execution routing |
| `src/pipeline/account_guards.py` | Account-level pre-checks |
| `src/pipeline/account_state.py` | Account state loading |
| `src/pipeline/audit.py` | Pipeline audit trail |
| `src/pipeline/idempotency.py` | Duplicate signal detection |

---

### Guard Rails
Pluggable trade veto implementations. Chain-of-responsibility pattern.

| File | Purpose |
|------|---------|
| `src/core/guard_rails/__init__.py` | Guard exports and registration |
| `src/core/guard_rails/guard_registry.py` | Auto-discovery and ordering |
| `src/core/guard_rails/staleness_guard.py` | Reject stale signals (>30s) |
| `src/core/guard_rails/pine_guardian.py` | Validate against Pine script logic |
| `src/core/guard_rails/prop_guard.py` | Prop firm capital preservation |
| `src/core/guard_rails/sector_guard.py` | Sector exposure limits |
| `src/core/guard_rails/holiday_guard.py` | Market holiday detection |
| `src/core/guard_rails/market_filter.py` | Volatility regime filtering |
| `src/core/guard_rails/correlation.py` | Correlation-based position limits |
| `src/core/guard_rails/portfolio_var_guard.py` | Portfolio Value-at-Risk |

**To add a new guard:** Create `src/core/guard_rails/<name>.py` implementing `check(signal, context) → GuardResult`, then export in `__init__.py`.

---

### Risk Engine
Position sizing, drawdown tracking, prop firm compliance.

| File | Purpose |
|------|---------|
| `src/core/risk_engine.py` | Position sizing formulas, risk calculations |
| `src/core/broker_profiles.py` | Multi-account config, profile loader |
| `src/core/safety.py` | Kill switch, fail-closed policies |
| `src/core/circuit_breaker.py` | Per-account circuit breaker state |

---

### Trade Execution
Opens, closes, and updates positions on the broker.

| File | Purpose |
|------|---------|
| `src/logic.py` | Core open/close/update position logic (⚠️ 950+ lines) |
| `src/adapters/execution/meta_api_adapter.py` | MetaApi broker bridge with retry/circuit breaker |
| `src/adapters/paper_trader.py` | Paper trading adapter |
| `src/services/execution_engine.py` | Execution orchestration |
| `src/services/breakeven_manager.py` | Breakeven stop management |
| `src/services/trailing_stop_manager.py` | Trailing stop logic |

---

### API Endpoints
FastAPI routers grouped by domain. One file per domain.

| File | Domain |
|------|--------|
| `src/api_accounts.py` | Account management |
| `src/api_admin.py` | Admin controls |
| `src/api_alerts.py` | Alert configuration |
| `src/api_analytics.py` | Analytics and PnL |
| `src/api_analytics_signals_perf.py` | Signal performance analytics |
| `src/api_broker_profiles.py` | Broker profile CRUD |
| `src/api_config.py` | System configuration |
| `src/api_copilot.py` | AI copilot endpoints |
| `src/api_dashboard.py` | Dashboard data |
| `src/api_evaluation.py` | Strategy evaluation |
| `src/api_execution.py` | Manual execution |
| `src/api_funding.py` | Funding management |
| `src/api_guards.py` | Guard rail status |
| `src/api_health_trading.py` | Health checks |
| `src/api_incidents.py` | Incident management |
| `src/api_market.py` | Market data |
| `src/api_notifications.py` | Notification settings |
| `src/api_portfolio.py` | Portfolio overview |
| `src/api_portfolio_control.py` | Portfolio control (⚠️ 2400+ lines) |
| `src/api_positions.py` | Position management |
| `src/api_prop_firm.py` | Prop firm endpoints |
| `src/api_prop_firm_v1.py` | Prop firm v1 compat |
| `src/api_risk.py` | Risk settings |
| `src/api_risk_monitor.py` | Risk monitoring |
| `src/api_rules.py` | Trading rules |
| `src/api_strategies.py` | Strategy config |
| `src/api_tickets.py` | Jira ticket proxy |
| `src/api_traces.py` | Execution traces |
| `src/api_webhook_read.py` | Webhook history |
| `src/api_agent_status.py` | Agent status |
| `src/api_ai_runs.py` | AI run logs |

**To add a new endpoint:** Create `src/api_{domain}.py`, then import and `app.include_router()` in `src/api.py`.

---

### Services (Business Logic)
Domain logic layer. Do not call these from API handlers directly — route through the pipeline or a service.

| File | Purpose |
|------|---------|
| `src/services/account_orchestrator.py` | Multi-account orchestration |
| `src/services/account_sync_service.py` | Account data sync |
| `src/services/alert_engine.py` | Alert evaluation engine |
| `src/services/alert_service.py` | Alert CRUD |
| `src/services/background_sync_worker.py` | Background sync tasks |
| `src/services/broker_reconciliation.py` | Broker vs. DB reconciliation |
| `src/services/chart_generator.py` | Chart generation |
| `src/services/consistency_analyzer.py` | Data consistency checks |
| `src/services/daily_reset_scheduler.py` | Daily counter resets |
| `src/services/digest_service.py` | Digest/summary generation |
| `src/services/evaluation_tracker.py` | Strategy evaluation tracking |
| `src/services/graduation_service.py` | Prop firm phase graduation |
| `src/services/hedging_engine.py` | Hedging logic |
| `src/services/historical_returns.py` | Historical return calculations |
| `src/services/liquidity_scorer.py` | Liquidity scoring |
| `src/services/metaapi_streaming_service.py` | MetaApi WebSocket streaming |
| `src/services/mtm_guardian.py` | Mark-to-market monitoring |
| `src/services/notification_service.py` | Discord/Telegram notifications |
| `src/services/pine_streak.py` | Pine streak tracking |
| `src/services/portfolio_analyzer.py` | Portfolio analysis |
| `src/services/position_optimizer.py` | Position optimization (partial impl) |
| `src/services/prop_firm_detector.py` | Prop firm detection |
| `src/services/prop_firm_tracker.py` | Prop firm phase tracking |
| `src/services/redis_cache.py` | Redis caching helpers |
| `src/services/reflection_service.py` | AI reflection/analysis |
| `src/services/strategy_config.py` | Strategy configuration |
| `src/services/symbol_mapper.py` | Symbol name mapping |
| `src/services/tca_analyzer.py` | Transaction cost analysis |
| `src/services/trade_copier.py` | Trade copying |
| `src/services/watchdog.py` | System health watchdog |

---

### AI / ML
LLM agents, ML models, Trading Council debate system.

| File | Purpose |
|------|---------|
| `src/ai/` | Trading council, LLM client, RAG engine, debate logic |
| `src/agents/` | Agent implementations |
| `src/services/ai_decision_cache.py` | AI decision caching |
| `src/services/ai_mode_override.py` | AI mode override logic |
| `src/services/ai_run_service.py` | AI run logging |
| `src/services/memory_retrieval.py` | RAG memory retrieval |
| `ml/` | Local model files and ML assets |

---

### Observers (Event System)
Cross-cutting concerns via observer pattern. Observers must never raise exceptions.

| File | Purpose |
|------|---------|
| `src/core/observers/__init__.py` | Observer exports |
| `src/core/observers/base.py` | Observer base class, WorkerSubject, TradeEvent |
| `src/core/observers/auditor.py` | Audit trail observer |
| `src/core/observers/risk_observer.py` | Risk event observer |
| `src/core/observers/metrics.py` | Metrics collection observer |
| `src/core/observers/executor.py` | Execution observer |
| `src/core/observers/account_router_observer.py` | Multi-account routing observer |

---

### Adapters (External Services)
Infrastructure adapters for external dependencies.

| File | Purpose |
|------|---------|
| `src/adapters/supabase.py` | Supabase ORM layer |
| `src/adapters/supabase_api.py` | Supabase API helper |
| `src/adapters/discord.py` | Discord webhook + bot |
| `src/adapters/redis_queue.py` | Redis queue adapter |
| `src/adapters/market_data.py` | Market data (yfinance) |
| `src/adapters/jira.py` | Jira API adapter |
| `src/core/transport.py` | Signal transport abstraction |
| `src/core/metaapi_credentials.py` | MetaApi credential management |
| `src/core/news_filter.py` | News event filtering |

---

### Frontend
Next.js 15 + React 19 + TypeScript dashboard.

| Path | Purpose |
|------|---------|
| `frontend/src/app/` | App Router pages (accounts, copilot, login, metrics, settings, signals, trades) |
| `frontend/src/components/` | Feature components (copilot, metrics, risk, trading) |
| `frontend/src/lib/supabase.ts` | Supabase client config |
| `frontend/next.config.ts` | Next.js configuration |
| `frontend/package.json` | Frontend dependencies |

---

### Database
Schema migrations and data layer.

| Path | Purpose |
|------|---------|
| `scripts/sql/*.sql` | Supabase schema migrations |
| `migrations/` | Numbered migration files |
| `src/adapters/supabase.py` | TypedDict ORM |

---

### Configuration
Environment and application configuration.

| File | Purpose |
|------|---------|
| `config/settings.py` | Pydantic-settings (all env vars) |
| `.env` | Environment variables (not committed) |
| `.env.example` | Environment variable reference |
| `docker-compose.yml` | 4-service infrastructure |
| `nixpacks.toml` | Railway API deployment |
| `nixpacks.worker.toml` | Railway worker deployment |
| `railway.json` | Railway service config |

---

### Scripts & Tools
Operational utilities and strategy files.

| Path | Purpose |
|------|---------|
| `scripts/pinescript/` | TradingView .pine strategy files |
| `scripts/sql/` | Database migrations |
| `scripts/optimizer/` | Strategy parameter optimizer |
| `scripts/jira-*.js` | Jira automation scripts |
| `start.sh` | Full stack launcher |

---

### Tests
Test suites and fixtures.

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Global fixtures, mock Redis, dummy env vars |
| `tests/test_worker_observers.py` | Observer pipeline tests |
| `tests/test_dynamic_sizing.py` | Position sizing tests |
| `tests/test_pipeline.py` | End-to-end pipeline tests |
| `tests/test_prop_firm_phase1.py` | Prop firm guard rail tests |
| `tests/test_consumer_validation.py` | Message validation tests |
| `tests/test_signal_transport.py` | Transport layer tests |
| `tests/test_account_routing.py` | Account routing tests |
