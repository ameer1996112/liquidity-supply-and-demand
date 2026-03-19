# External Integrations

**Analysis Date:** 2026-03-19

## APIs & External Services

**Broker Execution (MT5):**
- MetaApi Cloud - MT5 broker bridge over HTTP REST
  - SDK/Client: `requests` HTTP calls via `src/adapters/execution/meta_api_adapter.py`
  - Base URL pattern: `https://mt-client-api-v1.{region}.agiliumtrade.ai`
  - Auth: `META_API_TOKEN` (env var), passed as `auth-token` header
  - Account: `META_API_ACCOUNT_ID` (env var)
  - Region: `META_API_REGION` (env var, default `new-york`)
  - Multi-account: `BROKER_PROFILES_JSON` (JSON array of broker profiles)
  - Circuit breaker: `src/core/circuit_breaker.py` guards against 429/5xx cascades

**Market Data:**
- Yahoo Finance (yfinance) - Market narrative generation and historical returns
  - SDK: `yfinance>=0.2.36`
  - Used in: `src/adapters/market_data.py`, `src/services/historical_returns.py`, `src/api_market.py` (CORS proxy for frontend)
  - Symbol mapping: `XAUUSD → GC=F`, `NAS100 → NQ=F`, `EURUSD → EURUSD=X`, etc.
  - No API key required (public Yahoo Finance API)

**AI Providers:**
- Anthropic Claude - Primary AI guardian
  - SDK: `anthropic>=0.18.0`
  - Client: `src/ai/llm_client.py` `AnthropicClient`
  - Auth: `ANTHROPIC_API_KEY` (via `AI_API_KEY` alias)
  - Default model: `claude-3-5-sonnet-20241022`
- OpenAI / OpenAI-compatible (Groq) - Ensemble brain LLM
  - SDK: `openai>=1.0.0`
  - Client: `src/ai/llm_client.py` `OpenAIClient`
  - Auth: `OPENAI_API_KEY` (via `AI_API_KEY` alias)
  - Base URL override: `AI_BASE_URL` (allows routing to Groq `api.groq.com/openai/v1`)
  - Default quick model: `llama-3.1-8b-instant` (Groq-hosted)
  - Default deep model: `llama-3.3-70b-versatile` (Groq-hosted)
- Google Gemini - Stub only (`GeminiClient` in `src/ai/llm_client.py`), not implemented
- Local/Ollama - Stub only (`LocalClient` in `src/ai/llm_client.py`), not implemented
- Provider selection: `AI_PROVIDER` env var (`anthropic` | `openai` | `gemini` | `local`)

**Notifications:**
- Discord - Trade alerts and bot notifications
  - SDK: `requests` HTTP POST to webhook URL
  - Client: `src/adapters/discord.py`
  - Auth: `DISCORD_WEBHOOK_URL` (full webhook URL)
  - Optional async mode: `ASYNC_NOTIFICATIONS=true` uses background ThreadPoolExecutor
- Telegram - Trade alerts
  - SDK: `requests` HTTP calls to Bot API
  - Client: `src/adapters/discord.py` (shared module)
  - Auth: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`

**Trading Signals (Inbound):**
- TradingView Webhooks - Signal source
  - Receives `POST /webhook` on backend API (`src/api.py`)
  - Auth: `WEBHOOK_SECRET` (HMAC or bearer token validation via `src/core/signal.py`)
  - Payload: JSON with symbol, side, entry, stop_loss, take_profit, position_size, score, etc.

## Data Storage

**Databases:**
- Supabase (PostgreSQL) - Primary persistent store
  - Backend client: `supabase==2.10.0` (`src/adapters/supabase.py`, `src/adapters/supabase_api.py`)
  - Frontend client: `@supabase/supabase-js ^2.93.3` (`frontend/src/lib/supabase.ts`, `frontend/src/lib/boardSupabase.ts`)
  - Backend connection: `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`)
  - Frontend connection: `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - Key tables: `trading_signals`, `account_strategies`, `broker_profiles`, `account_status_snapshots`, `symbol_risk_rules`, `portfolio_snapshots`, `ai_runs`, `board_tickets`
  - Migrations: `migrations/` directory (SQL files, numbered `001` through `026+`)
  - Realtime: enabled on frontend with 10 events/second cap

**Message Queue:**
- Redis 7 (Alpine) - Signal queue between API producer and Worker consumer
  - SDK: `redis>=5.0.0`
  - Client: `src/adapters/redis_queue.py`
  - Connection: `REDIS_URL` (env var)
  - Queue name: `signals:default` (LPUSH/BRPOP pattern)
  - Dead letter queue: `signals:dead_letter` (failed signals)
  - Cache layer: `src/services/redis_cache.py` (account data, MTM snapshots)
  - In-memory fallback: `SIGNAL_TRANSPORT=memory` for tests

**File Storage:**
- Local filesystem only - ML model artifacts stored at `ml/` (`model_v3_lgbm.txt`, `model_v3.pkl`, `encoders_v3.pkl`, `scaler_v2.pkl`)
- No cloud file storage (S3/GCS) detected

**Caching:**
- Redis - Account data cache TTL `ACCOUNT_CACHE_TTL_SECONDS` (default 30s)
- Redis - MTM guardian cache TTL `MTM_CACHE_TTL_SECONDS` (default 10s)
- Python `lru_cache` - Settings singleton (`config/settings.py`)

## Authentication & Identity

**Auth Provider:**
- None (no user authentication layer detected)
- Backend uses `WEBHOOK_SECRET` for TradingView webhook HMAC validation only
- Supabase accessed with service role key server-side (full access)
- Frontend uses anon key directly (no user login/RLS enforcement detected)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Datadog, etc.)

**Logs:**
- Python structured logging via `config/logging_config.py` (`configure_logging()`)
- Log level configurable via `LOG_LEVEL` env var (default `INFO`)
- Named loggers per module (e.g. `trinity.api`, `trinity.worker`)
- Frontend: `console.log` / `console.warn` / `console.error` only

**Kanban Board:**
- Internal board via Supabase (`board_tickets` table)
- API: `POST /api/board/create-ticket`, `POST /api/board/agent-update` (`src/api_board.py`)
- Frontend: `/board` route, uses `frontend/src/lib/boardSupabase.ts`

## CI/CD & Deployment

**Hosting:**
- Railway (PaaS) - all three services (API, Worker, Frontend)
- Services auto-deploy on push to main via Railway GitHub integration

**CI Pipeline:**
- Not detected (no GitHub Actions, CircleCI config found)

**Container Registry:**
- Railway's internal registry (Docker builds run by Railway)

## Webhooks & Callbacks

**Incoming:**
- `POST /webhook` - TradingView signal receiver (`src/api.py`)
  - Validates `WEBHOOK_SECRET`, pushes to Redis queue
- `POST /api/board/create-ticket` - Agent board ticket creation
- `POST /api/board/agent-update` - Agent board ticket status updates

**Outgoing:**
- Discord webhooks - `DISCORD_WEBHOOK_URL` (trade notifications)
- Telegram Bot API - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (trade notifications)
- MetaApi REST - Trade execution (`src/adapters/execution/meta_api_adapter.py`)
- Anthropic API - AI guardian calls (`src/ai/llm_client.py`)
- OpenAI / Groq API - LLM ensemble calls (`src/ai/llm_client.py`)
- Yahoo Finance API - Market data pulls (`src/adapters/market_data.py`)

## Environment Configuration

**Required env vars:**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY` - Supabase auth key
- `REDIS_URL` - Redis connection URL

**Critical optional env vars:**
- `META_API_TOKEN` - MetaApi JWT for broker execution
- `META_API_ACCOUNT_ID` - MT5 account identifier
- `WEBHOOK_SECRET` - TradingView webhook authentication
- `DISCORD_WEBHOOK_URL` - Discord notification endpoint
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` - Telegram notifications
- `AI_API_KEY` - Anthropic or OpenAI key (aliased from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`)
- `AI_PROVIDER` - `anthropic` | `openai` | `gemini` | `local`
- `AI_BASE_URL` - Override for Groq or other OpenAI-compatible endpoints
- `NEXT_PUBLIC_API_URL` - Frontend → backend URL
- `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Frontend Supabase

**Secrets location:**
- `.env` file at project root (gitignored)
- Railway environment variable panel in production
- `.env.example` documents all variables with defaults

---

*Integration audit: 2026-03-19*
