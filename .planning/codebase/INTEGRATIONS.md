# INTEGRATIONS.md — External Integrations

## Signal Source
- **TradingView** — webhook sender
  - Entry point: `POST /webhook` (protected by `WEBHOOK_SECRET`)
  - `POST /webhook/test` — dry-run mode (schema validation + guard rail simulation, no execution)
  - Payload: `{symbol, side, entry, sl, tp, size, bar_time, zone_id, rr_ratio, event_type, run_mode}`
  - JSON sanitization handles TradingView's unquoted `{{time}}` template values

---

## Broker / Execution

### MetaAPI (MT5 over HTTP)
- **Purpose**: Live order placement, positions, account info
- **Config**: `META_API_TOKEN`, `META_API_ACCOUNT_ID`, `META_API_REGION` (default: `new-york`)
- **Adapter**: `src/adapters/execution/` + `src/adapters/metaapi.py`
- **Execution mode**: `EXECUTION_MODE=METAAPI` (vs `SHADOW`)
- **Caching**: 30s TTL via Redis to limit MetaAPI polling frequency (bug: previously polled too frequently — fixed)
- **Paper trading**: `src/adapters/paper_trader.py` — simulated execution, no real orders

---

## Database

### Supabase (PostgreSQL)
- **Main adapter**: `src/adapters/supabase.py` (41KB — largest adapter)
- **Frontend direct**: `@supabase/supabase-js` for real-time subscriptions
- **Auth keys**: `SUPABASE_ANON_KEY` (frontend) / `SUPABASE_SERVICE_ROLE_KEY` (backend)
- **Key tables** (inferred from code):
  - `trading_signals` — signal lifecycle (received → queued → executed → closed)
  - `ai_runs` — debate/LLM decisions per signal
  - `ai_mode_toggles` — shadow/enforce mode audit log
  - `trades` — executed trade records
  - `alerts` — risk and operational alerts
  - `accounts` — broker account metadata
  - `strategy_configs` — strategy-as-data configuration
  - `incidents` — auto-created from worker errors / ML drift
  - `tickets` — Jira-proxy task/bug board
- **Background sync**: `src/services/background_sync_worker.py` — polls MetaAPI on interval, writes to Supabase

---

## AI / LLM Providers

### OpenAI / Groq (via OpenAI-compatible API)
- **Client**: `src/ai/llm_client.py` — unified wrapper
- **Config**: `AI_PROVIDER=openai`, `AI_API_KEY`, `AI_BASE_URL` (empty = provider default, set for Groq)
- **Default model**: `llama-3.3-70b-versatile` (Groq-hosted)
- **Quick model**: `llama-3.1-8b-instant` — first-tier fast call
- **Deep model**: `llama-3.3-70b-versatile` — second-tier escalation

### Anthropic (Claude)
- **Config**: `AI_PROVIDER=anthropic`, `AI_API_KEY`
- **Client**: same unified `src/ai/llm_client.py`

### Gemini (Google)
- **Config**: `AI_PROVIDER=gemini`

---

## Notifications

### Discord
- **Adapter**: `src/adapters/discord.py` (27KB — complex formatting with trade embeds)
- **Config**: `DISCORD_WEBHOOK_URL` — main channel
- `DISCORD_ALERTS_WEBHOOK_URL` — separate operational alerts channel
- `DISCORD_BOT_TOKEN` — enables thread-per-trade (message threads)
- **Content**: Trade notifications, late fills, watchdog alerts, MTM events

### Telegram
- **Config**: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- Lightweight text messages for critical alerts

---

## Market Data

### Yahoo Finance (`yfinance`)
- **Used for**: Historical prices for backtesting, ML feature prep
- **CORS proxy**: `src/api_market.py` (`GET /api/market/*`) — frontend passes requests through backend to avoid CORS

### Market Data Adapter
- `src/adapters/market_data.py` — live price quotes for spread gate validation

---

## Jira (External Project Management)
- **Proxy**: `src/api_tickets.py` (39KB) — forwards requests to Jira REST API
- **Auth**: `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_API_TOKEN`, `JIRA_EMAIL`
- **Usage**: AI skills auto-create/update tickets for phases and todos
- **Frontend**: Standalone Jira Next.js app at `/jira/`

---

## Redis (Internal Queue)
- **Transport**: `src/adapters/redis_queue.py` — LPUSH/BRPOP pattern
- **Pub/Sub**: `trading:debate_logs` — real-time WebSocket stream to frontend AI Terminal (`/ws/debate`)
- **Caching**: `src/services/redis_cache.py` — TTL-based cache for MetaAPI responses

---

## Railway (Deployment Platform)
- `railway.json` — service definition
- `nixpacks.toml` / `nixpacks.worker.toml` — build config for api and worker services
- CORS: `CORS_ORIGIN_REGEX` defaults to `https://.*\.up\.railway\.app`
- Production frontend URL: `https://frontend-production-a7cf.up.railway.app`
