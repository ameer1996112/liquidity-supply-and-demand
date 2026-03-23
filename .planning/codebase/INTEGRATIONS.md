# INTEGRATIONS.md — External Services & APIs

## Databases

### Supabase (PostgreSQL)
- **Python client**: `src/adapters/supabase.py` (41KB — primary data access layer)
- **Frontend client**: `@supabase/supabase-js` — realtime subscriptions + REST queries
- **Config**: `SUPABASE_URL` (required), `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- **Migration files**: `migrations/` — 57+ numbered SQL files (`001_*.sql` → `058_jira_upgrade.sql`)
- **Key tables**: `signals`, `trades`, `positions`, `accounts`, `ai_runs`, `alerts`, `backtest_results`, `project_tickets`
- **Realtime**: Frontend uses Supabase realtime channels for live signal feed updates

## Broker / Trading APIs

### MetaAPI (MT5 over HTTP)
- **Python adapter**: `src/adapters/execution/` (MetaAPI execution layer)
- **Config**: `META_API_TOKEN`, `META_API_ACCOUNT_ID`, `META_API_REGION` (default: `new-york`)
- **Multi-account**: `BROKER_PROFILES_JSON` — JSON array of broker profiles for Package A (one-signal-many-accounts)
- **Execution modes**: `SHADOW` (log-only) | `METAAPI` (live broker)
- **Caching**: `src/services/redis_cache.py` + `account_cache_ttl_seconds` setting to throttle MetaAPI calls
- **Account sync**: Background sync service with `account_sync_interval_seconds` (default: 60s)

### Paper Trader
- **Module**: `src/adapters/paper_trader.py` (11KB)
- **Config**: `PAPER_TRADING_ENABLED`, `PAPER_AUTO_EXECUTE`, `PAPER_SYMBOLS`, `PAPER_ACCOUNT_BALANCE`
- Simulates fills without broker API; persists results to Supabase

### TradingView (Webhooks — Inbound)
- **Endpoint**: `POST /webhook` on FastAPI
- **Payload**: `{ symbol, side, entry, sl, tp, size, ...pine_metadata }`
- **Auth**: Optional `WEBHOOK_SECRET` header check
- **Flow**: Webhook → Redis queue → Worker → AI/ML guardrails → execution

## Message Queue

### Redis
- **Adapter**: `src/adapters/redis_queue.py` (3.7KB)
- **Config**: `REDIS_URL` (required; checked on API startup)
- **Transport**: `SIGNAL_TRANSPORT=redis` (production) | `memory` (tests)
- Queue name: `trading:signals`; workers use BLPOP blocking pop

## AI / LLM Providers

### Multi-Provider LLM Client (`src/ai/llm_client.py`)
- **Unified client** switching between: `anthropic` | `openai` | `gemini` | `local`
- **Config**: `AI_PROVIDER`, `AI_API_KEY` (aliases: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- **Models**: `AI_QUICK_MODEL` (default: `llama-3.1-8b-instant`) + `AI_DEEP_MODEL` (default: `llama-3.3-70b-versatile`)
- **Fallback**: `LLM_MODEL_FALLBACK` used when primary returns 404

### AI Guardrails Stack
1. **AI Guardian** (`src/ai/ai_guardian.py`) — LLM-based signal validation
2. **ML Guardian** (`src/ai/ml_guardian.py`) — LightGBM win-probability model
3. **Trading Council** (`src/ai/trading_council.py`) — Multi-agent Bull/Bear/Risk/Chair debate
4. **Debate Engine** (`src/ai/debate.py`) — Structured debate orchestration
5. **Brain** (`src/ai/brain.py`, 59KB) — Ensemble orchestrator
6. **RAG Engine** (`src/ai/rag_engine.py`) — BM25 + LangChain retrieval for context

### Modes
- `AI_MODE=shadow` — log decisions only, never block
- `AI_MODE=enforce` — LLM NO_GO blocks execution
- `AI_SHADOW_MODE=true` — AI runs but never blocks (calibration)
- `AI_DEBATE_ENABLED=true` — Bull/Bear debate persisted to `ai_runs` table

## Notifications

### Discord
- **Adapter**: `src/adapters/discord.py` (27KB)
- **Config**: `DISCORD_WEBHOOK_URL` (signals), `DISCORD_ALERTS_WEBHOOK_URL` (operational alerts), `DISCORD_BOT_TOKEN` (optional, enables thread-per-trade)
- **Features**: Thread creation per trade, rich embeds with SL/TP/size, late fill alerts, order notifications

### Telegram
- **Config**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Sends signal notifications via Telegram bot API

## Market Data

### Yahoo Finance (`yfinance`)
- Used for historical data in ML feature engineering and backtesting

### Market Data Adapter
- `src/adapters/market_data.py` (9.5KB) — aggregates market data from multiple sources

## Project Management

### Jira (Real Jira API Proxy)
- **Backend**: `src/api_tickets.py` (22KB) — proxies to Jira REST API v3
- **Frontend app**: `jira/` — standalone Next.js 14 app with Supabase-backed ticket storage
- **Config**: `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_USER_EMAIL`, `JIRA_PROJECT_KEY`
- **Tables**: `project_tickets` (Supabase) — local ticket mirror

## Infrastructure / Deployment

### Railway
- `railway.json` — service configuration for Railway cloud deployment
- `nixpacks.toml` / `nixpacks.worker.toml` — build configs for API and Worker services

### Docker
- `Dockerfile` — main container
- `Dockerfile.api` — API service container
- `Dockerfile.worker` — Worker service container
- `docker-compose.yml` — local multi-service orchestration

## TradingView Pine Script
- Strategy files in `data/` — Pine Script v5 strategy + library files
- Send webhook payloads to backend `/webhook` endpoint on signal
- `SND_Core.pine` — Supply & Demand core library with scoring functions
