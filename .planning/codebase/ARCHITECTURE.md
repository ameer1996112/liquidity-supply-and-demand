# ARCHITECTURE.md — System Architecture

## Pattern
**Event-driven pipeline** with a TradingView → API → Redis Queue → Worker → Broker flow. The API is stateless (no business logic); all intelligence runs in the Worker.

The system follows a layered DDD-inspired architecture with clear separation between:
- **Adapters** (external I/O)
- **Core** (domain logic, guard rails)
- **Services** (orchestration & business logic)
- **AI layer** (ML + LLM decision making)

---

## Service Architecture

```
[TradingView]
     │ POST /webhook
     ▼
[FastAPI API — src/api.py]  ←── CORS, rate limiting, auth
     │ validate + enqueue
     ▼
[Redis Queue — signal:{account_id}]
     │ BRPOP
     ▼
[Worker — src/worker.py]
     │
     ├── Guard Rails (src/core/guard_rails/)
     │     ├── StalenessGuard     → reject delayed signals
     │     ├── MarketFilter       → session hours, news filter
     │     ├── PineGuardian       → Pine Script rule mirror (score, grade, RR, adaptive limits)
     │     ├── CorrelationGuard   → cross-pair correlation matrix
     │     ├── PortfolioVarGuard  → portfolio Value-at-Risk limit
     │     ├── SectorGuard        → sector exposure limits
     │     └── PropGuard          → prop firm phase rules
     │
     ├── AI/ML Layer (src/ai/)
     │     ├── MLGuardian         → Random Forest / LightGBM win probability gate
     │     ├── AIGuardian         → LLM-based signal quality check (shadow or enforce)
     │     ├── TradingCouncil     → Bull/Bear/Risk/Chair multi-agent debate (shadow)
     │     └── EnsembleBrain      → orchestrates ML + LLM + Council
     │
     ├── Risk Engine (src/core/risk_engine.py)
     │     ├── Trinity Engine     → daily loss/drawdown/position count limits
     │     ├── Dynamic risk scaling → drawdown-based size reduction
     │     └── Adaptive trade limits → session-based + streak-based slots
     │
     └── Execution (src/services/execution_engine.py)
           ├── MetaAPI adapter    → live MT5 orders
           ├── PaperTrader        → simulated fills
           └── HedgingEngine      → paired trade management
```

---

## Data Flow (Signal Lifecycle)

1. **Receive**: TradingView fires webhook → `POST /webhook`
2. **Validate**: Schema check (Pydantic) + secret auth
3. **Persist early**: API inserts signal row (`status=received`) into Supabase for frontend visibility
4. **Queue**: API serializes payload + account routing → Redis LPUSH
5. **Consume**: Worker BRPOP from queue
6. **Guard rails**: Sequential pre-filters (staleness → market hours → Pine rules → portfolio risk)
7. **AI/ML vote**: ML confidence score → LLM check → Council debate (all optional / shadowed)
8. **Risk engine**: Trinity limits, dynamic scaling, adaptive caps
9. **Execute**: Order to MetaAPI (live) or PaperTrader (paper), or log-only (shadow)
10. **Post-trade**: Update Supabase, notify Discord/Telegram, track TCA metrics, start watchdog

---

## Key Abstractions

### Signal Transport (`src/core/transport.py`)
Pluggable queue backend: `RedisTransport` (production) | `InMemoryTransport` (tests).
```python
transport = get_transport()  # factory reads SIGNAL_TRANSPORT setting
transport.enqueue(payload_str, queue_key="signal:default")
```

### Account Router (`src/core/account_router.py`)
Maps signal symbols to broker accounts (multi-account support). Stamps `_account_id` and `queue_key` onto payload before Redis push.

### Observer Pattern (`src/core/observers/`)
Worker executes a list of observers per signal:
- `auditor.py` — write audit log
- `executor.py` — trigger trade execution
- `metrics.py` — record latency metrics
- `risk_observer.py` — risk checks
- `account_router_observer.py` — account routing

### Settings (`config/settings.py`)
Single `Settings` class loaded via `@lru_cache`. Restart required after `.env` changes. ~90 configurable fields covering risk, AI tuning, prop firm rules, latency thresholds.

---

## API Router Structure (`src/api.py`)

Main app includes ~20 FastAPI routers:

| Router | Prefix | Purpose |
|--------|--------|---------|
| `api_rules` | `/api/rules` | Trading rule management |
| `api_risk` | `/api/risk` | Risk settings |
| `api_risk_monitor` | `/api/risk-monitor` | Real-time risk read |
| `api_analytics` | `/api/analytics` | Historical analytics |
| `api_analytics_signals_perf` | `/api/analytics/signals-perf` | v1.1 signal performance |
| `api_health_trading` | `/api/health/trading` | Real-time health widget data |
| `api_positions` | `/api/positions` | Open positions |
| `api_execution` | `/api/execution` | Execution quality |
| `api_portfolio` | `/api/portfolio` | Portfolio overview |
| `api_portfolio_control` | `/api/portfolio-control` | Portfolio Command Center |
| `api_prop_firm` | `/api/prop-firm` | Prop firm metrics |
| `api_traces` | `/api/traces` | Pipeline latency traces |
| `api_accounts` | `/api/accounts` | Multi-account |
| `api_ai_runs` | `/api/ai-runs` | AI/debate decisions |
| `api_backtests` | `/api/backtests` | Backtest lab |
| `api_strategies` | `/api/strategies` | Strategy-as-data configs |
| `api_webhook_read` | `/api/v1/webhook` | Recent signals/trades/stats |
| `api_copilot` | `/api/copilot` | AI natural language copilot |
| `api_market` | `/api/market` | Market data CORS proxy |
| `api_funding` | `/api/v1/funding` | Prop firm daily PnL |
| `api_tickets` | `/api/tickets` | Jira proxy |
| `api_incidents` | `/api/incidents` | Auto-incident tickets |

---

## Frontend Architecture

Next.js 16 App Router with route-based page structure:

```
frontend/src/
├── app/
│   ├── page.tsx          ← Main dashboard (25KB, all widgets)
│   ├── layout.tsx        ← Root layout + providers
│   ├── analytics/        ← Analytics pages
│   ├── accounts/         ← Multi-account management
│   ├── alerts/           ← Alert feed
│   ├── backtest/         ← Backtest lab UI
│   ├── execution-quality/← TCA and execution metrics
│   ├── journal/          ← Trade journal
│   ├── positions/        ← Open positions
│   ├── prop-firm/        ← Prop firm dashboard
│   ├── risk/             ← Risk settings
│   ├── rules/            ← Trading rules
│   ├── scanner/          ← Signal scanner
│   ├── settings/         ← App settings
│   ├── strategies/       ← Strategy configs
│   └── tickets/          ← Jira board
├── components/           ← Shared UI components
├── domain/               ← Business logic / hooks
├── hooks/                ← Custom React hooks
├── lib/                  ← API client utilities
├── providers/            ← Context providers (QueryClient, etc.)
└── types/                ← TypeScript type definitions
```

### Real-time Updates
- **WebSocket**: `/ws/debate` — streams AI Council logs from Redis pub/sub
- **Supabase Realtime**: direct subscriptions for trading signal feed

---

## Background Processes

| Service | File | Trigger |
|---------|------|---------|
| Background Sync Worker | `src/services/background_sync_worker.py` | API startup (if `ACCOUNT_SYNC_ENABLED`) |
| Daily Reset Scheduler | `src/services/daily_reset_scheduler.py` | APScheduler cron |
| TradeWatchdog | `src/services/watchdog.py` | Per-trade thread |
| MTM Guardian | `src/services/mtm_guardian.py` | Polling loop |
| Trailing Stop Manager | `src/services/trailing_stop_manager.py` | Active position polling |
| Breakeven Manager | `src/services/breakeven_manager.py` | Active position polling |
