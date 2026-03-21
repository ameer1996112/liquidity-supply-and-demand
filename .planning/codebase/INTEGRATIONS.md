# INTEGRATIONS.md — External Services & APIs

## Signal Ingestion

### TradingView (Inbound Webhooks)
- **Direction:** TradingView → Bot
- **Endpoint:** `POST /webhook` on the FastAPI backend
- **Auth:** Optional `X-Webhook-Secret` header (env: `WEBHOOK_SECRET`)
- **Payload fields:** `symbol`, `side`, `entry`, `sl`, `tp`, `size`, `rr_ratio`, `bar_time`, `zone_id`, `run_mode`
- **Test endpoint:** `POST /webhook/test` — dry-run without executing
- **Docs:** `docs/webhook-payload-reference.md`

## Database

### Supabase (PostgreSQL)
- **Adapter:** `src/adapters/supabase.py` (worker), `src/adapters/supabase_api.py` (API)
- **API adapter** has auto-reconnect logic (recreates client every 90s to avoid stale HTTP/2)
- **Env vars:** `SUPABASE_URL`, `SUPABASE_ANON_KEY` / `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- **Frontend:** `@supabase/supabase-js` — realtime subscriptions + REST
- **Frontend env vars:** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Key tables:**
  - `trading_signals` — signals, PnL, outcomes, account assignment
  - `prop_firm_accounts` — account configs, phases, challenge state
  - `dynamic_rules` — dynamic config picked up by `src/core/dynamic_config.py`

## Message Queue

### Redis
- **Adapter:** `src/adapters/redis_queue.py`
- **URL:** env `REDIS_URL` (default: `redis://localhost:6379`)
- **Role:** Decouples API (publisher) from Worker (consumer)
- **Transport:** `src/core/transport.py` abstracts Redis vs in-memory (for tests)
- **Must run before API or startup fails** — fail-fast check in API boot

## Broker / Trade Execution

### MetaAPI (MetaTrader connector)
- **Adapter:** `src/adapters/metaapi.py` + `src/adapters/execution/`
- **Env vars:** `META_API_TOKEN`, `META_API_ACCOUNT_ID`
- **Role:** Opens/closes MT4/MT5 positions, fetches open trades
- **Paper trader fallback:** `src/adapters/paper_trader.py` — simulates execution when `PAPER_TRADING_ENABLED=true`

## AI / ML Services

### AI Guardian (OpenAI / Anthropic)
- **Module:** `src/ai/brain.py`
- **Env var:** `AI_API_KEY` (accepts OpenAI or Anthropic key)
- **Role:** LLM-based signal validation in worker pipeline
- **Config flags:**
  - `AI_FILTER_ENABLED` (bool) — enable/disable
  - `AI_SHADOW_MODE` (bool) — log but never block
  - `ML_GUARDIAN_ENABLED` — ML random forest layer
  - `TRINITY_ENABLED` — full AI ensemble (AI + ML + RF)
- **For local dev:** set `AI_FILTER_ENABLED=false` to skip

## Notifications

### Discord
- **Adapter:** `src/adapters/discord.py`
- **Env var:** `DISCORD_WEBHOOK_URL`
- **Role:** Trade alerts, risk events, circuit breaker triggers

### Telegram
- **Env vars:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **Role:** Mobile trade alerts

## Deployment

### Railway
- **Services:** `backend` (API), `worker`, `frontend` (Next.js)
- **Env vars** set per-service in Railway dashboard
- **Tool:** `railway` CLI for setting env vars
- **No docker-compose.test.yml** — use local Redis directly for tests

## Frontend API Communication

- Frontend talks to backend via `NEXT_PUBLIC_API_URL` (e.g. Railway backend URL)
- Uses `@tanstack/react-query` with polling for live data
- Supabase realtime for signal feed updates
- Hooks in `frontend/src/hooks/` wrap all API calls
