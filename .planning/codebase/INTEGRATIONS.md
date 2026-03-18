# External Integrations

## Database — Supabase (PostgreSQL)

- **Adapter**: `src/adapters/supabase.py` (41KB — largest adapter)
- **API layer**: `src/adapters/supabase_api.py` (3KB — simplified API access)
- **Frontend client**: `frontend/src/lib/supabase.ts` (27KB)
- **Auth**: Service role key for backend, anon key for frontend
- **Tables**: Signals, trades, accounts, ai_runs, reflections, risk configs, alerts, board items, positions, portfolio data
- **Config**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

## Broker — MetaAPI (MT5 over HTTP)

- **Adapter**: `src/adapters/execution/meta_api_adapter.py` (29KB)
- **Interface**: `src/adapters/execution/interfaces.py` — abstract execution adapter
- **Router**: `src/adapters/execution/router.py` — routes to MetaAPI/Paper/DryRun based on config
- **Multi-account**: `src/core/broker_profiles.py` — one signal → many accounts
- **Config**: `META_API_TOKEN`, `META_API_ACCOUNT_ID`, `META_API_REGION`
- **Modes**: DRY_RUN (no-op), PAPER (simulated), LIVE (real orders via MetaAPI), SHADOW (log only)

## Signal Queue — Redis

- **Adapter**: `src/adapters/redis_queue.py` (3.7KB)
- **Cache service**: `src/services/redis_cache.py` (4.5KB)
- **Transport**: `src/core/transport.py` — signal queue backend (redis or memory)
- **Config**: `REDIS_URL`, `SIGNAL_TRANSPORT` (redis | memory)
- **Usage**: API pushes signals → Redis queue → Worker consumes

## AI/LLM Providers

- **Client**: `src/ai/llm_client.py` (9.6KB) — unified LLM interface
- **Providers**: Anthropic, OpenAI, Gemini, Local (configurable via `AI_PROVIDER`)
- **Models**: Two-tier: quick (llama 8b) + deep (llama 70b) for escalation
- **Config**: `AI_API_KEY`, `AI_PROVIDER`, `AI_MODEL`, `AI_QUICK_MODEL`, `AI_DEEP_MODEL`

## Market Data

- **Adapter**: `src/adapters/market_data.py` (9.5KB)
- **Source**: yfinance for historical data, live price from MetaAPI
- **Usage**: ML feature engineering, correlation analysis, TCA

## Notifications — Discord

- **Adapter**: `src/adapters/discord.py` (12.9KB)
- **Config**: `DISCORD_WEBHOOK_URL`
- **Usage**: Trade notifications, alerts, system status

## Notifications — Telegram

- **Config**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **Usage**: Optional trade notifications

## Webhooks — TradingView

- **Endpoint**: `POST /webhook` on the FastAPI backend
- **Payload**: `{symbol, side, entry, sl, tp, size}` + optional `WEBHOOK_SECRET`
- **Flow**: TradingView alert → webhook → Redis queue → worker processing
