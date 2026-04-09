# Project: Liquidity Supply & Demand Trading System

## What This Is
An event-driven, DDD-styled algorithmic trading platform. TradingView sends webhook signals → FastAPI validates and queues them → Python Worker applies AI/ML guardrails → trades execute on MetaTrader via MetaApi → results sync to Supabase → Next.js dashboard displays live metrics.

---

## Architecture at a Glance

```
TradingView → FastAPI (api.py) → Redis Queue → Worker (worker.py)
  → AI Guardrails (Trading Council) → MetaApi (MT4/MT5)
  → Supabase (logs/state) → Next.js Dashboard
```

### Three Services
- **Backend API** (`/src/api*.py`): FastAPI + uvicorn. Receives TradingView webhooks, validates with Pydantic, rate-limits with slowapi, pushes to Redis.
- **Worker** (`/src/worker.py`): Async Python. Consumes Redis queue, runs AI/ML guardrails, executes trades via MetaApi, writes state to Supabase.
- **Frontend** (`/frontend`): Next.js 14+ (TypeScript). Real-time dashboard using Supabase subscriptions. Server/client components split per Next.js 14 paradigms.

---

## Tech Stack

### Backend
- Python, FastAPI, uvicorn, asyncio
- Pydantic + pydantic-settings for validation and config (`get_settings()` with `@lru_cache`)
- Redis (queue + rate limit cache)
- Supabase (PostgreSQL + realtime)
- MetaApi cloud SDK (MT4/MT5 broker execution)
- LangChain + OpenAI + Anthropic (Trading Council multi-agent debate)
- LightGBM + scikit-learn (ML Guardian)
- ruff (linting), pytest (testing)

### Frontend
- Next.js 14+, TypeScript, React
- Supabase JS client (realtime subscriptions)
- eslint, vitest

### Infrastructure
- Docker + Docker Compose
- Railway (deployment)
- nixpacks
- python-dotenv

---

## Directory Structure

```
/src
  api.py, api_accounts.py, api_*.py  ← FastAPI routers by domain
  worker.py                           ← Main worker loop
  logic.py                            ← Core trading decision logic
  /ai                                 ← LLM agents, Trading Council, prompts
  /agents                             ← Agent implementations
  /adapters                           ← External service adapters
  /services                           ← Business logic services
  /core                               ← Shared domain primitives
  /utils                              ← Helpers
  /backtest                           ← Backtesting engine (LightGBM, optuna)
/frontend
  /src                                ← Next.js app router + components
  package.json, next.config.ts
/scripts
  /pinescript                         ← TradingView .pine strategy files
  /sql                                ← Supabase schema migrations
  jira-agent.js, jira-sync.js         ← Jira automation
/tests                                ← pytest e2e + unit tests
/docs                                 ← Project documentation
/.planning                            ← Architecture, conventions, roadmap
```

---

## Coding Conventions

### Python (strict — always follow these)
- **Type hints everywhere** — all function signatures must be typed
- **Pydantic schemas** for all API payloads — no raw dicts at boundaries
- **async/await** for all I/O — FastAPI endpoints, MetaApi calls, Supabase writes
- **ruff** enforced — PEP 8, no unused imports, no bare excepts
- **Config via `get_settings()`** — never hardcode env vars, always use the settings singleton
- **Error handling** — structured try/except with logging to Supabase or Discord/Telegram alerts
- **DDD structure** — keep domain logic in `/services`, adapters in `/adapters`, never mix concerns

### TypeScript/Next.js (strict — always follow these)
- **Strict TypeScript** — no `any`, no implicit types
- **Server vs Client components** — use `"use client"` only when needed (interactivity/hooks)
- **ESLint enforced** — don't introduce lint violations
- **Supabase realtime** for live data — don't poll, subscribe

### Git / Jira
- Every branch must reference a Jira ticket: `feature/DEV-XX-description`
- Every commit must reference the ticket: `DEV-XX: description`
- PRs are tethered to Jira tickets — always include ticket number

---

## Key Abstractions

- **Guardrails** — pluggable modules that can veto a trade before execution. Current: AI Filter, ML Guardian (LightGBM), Trinity. Adding a new guardrail = implement the interface in `/ai` or `/agents`.
- **Trading Council** — multi-agent LLM debate system that evaluates signal quality. Lives in `/ai`.
- **Paper Trading Mode** — toggled via env var. Always check before assuming real capital is at risk.
- **Kill Switch** — per-account kill switch to halt trading. Currently being fixed (DEV-94).

---

## Active Work (current focus)

- **DEV-94**: Per-account kill switch bug — `feature/DEV-94-fix-peraccount-kill-switch-cannot-be`
- **v1 Milestones**: PnL & metrics sync accuracy
  - Live PnL showing `0.00` for active trades → fixing MetaApi → Supabase sync
  - Historical PnL mismatches (swaps, commissions, slippage not captured)
  - Account metrics sync (Balance, Margin, Daily Drawdown) must match MetaTrader 1:1
  - Retroactive repair script for existing Supabase signal data

---

## External Integrations

| Service | Purpose | Direction |
|---------|---------|-----------|
| TradingView | Webhook signals | Inbound |
| MetaApi | MT4/MT5 trade execution + realtime events | Outbound |
| Supabase | Database, realtime, auth | Read/Write |
| Redis | Signal queue + rate limit cache | Read/Write |
| OpenAI / Anthropic | Trading Council agents | Outbound |
| Discord | Trade alerts + system health | Outbound |
| Telegram | Notifications | Outbound |
| yfinance | Market data | Outbound |

---

## Rules for the AI Assistant

- **Never change trading logic or strategy algorithms** unless explicitly asked — this is a live trading system
- **Always use async/await** for any new I/O code
- **Always add type hints** to new functions
- **Always use `get_settings()`** for config — never `os.environ` directly
- **Run ruff before suggesting code is done**: `ruff check src/`
- **Respect the DDD structure** — don't dump logic in api.py, route it to the right layer
- **Paper trading mode** — when writing trade execution code, always check `settings.paper_trading`
- **Jira discipline** — remind to create a DEV-XX ticket for any new feature or bug
- **Supabase realtime** — prefer subscriptions over polling in frontend code
- **MetaApi is async** — all MetaApi calls must be awaited, never called synchronously
