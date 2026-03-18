# External Integrations

**Analysis Date:** 2026-03-18

## APIs & External Services

**Broker Execution:**
- MetaAPI (Agilium Trade) - MT5 trading platform bridge
  - SDK/Client: HTTP REST API calls via `requests` library
  - Auth: `META_API_TOKEN` (JWT bearer token) and `META_API_ACCOUNT_ID`
  - Endpoints: `https://mt-client-api-v1.{region}.agiliumtrade.ai` (region configurable, default: new-york)
  - Implementation: `src/adapters/execution/meta_api_adapter.py`
  - Features: Place/modify/close orders, fetch account balance, positions, deal history
  - Retry logic: Max 3 attempts with exponential backoff (1s, 2s)
  - Rate limit handling: 429 errors trigger circuit breaker (60s sleep)

**Market Data:**
- Yahoo Finance (via yfinance)
  - Purpose: Real-time price validation for market health checks
  - Implementation: `src/core/guard_rails/market_filter.py`, `src/adapters/market_data.py`
  - Features: Fetch last N candles (default 50 x 15-minute), validate bid-ask spread
  - CORS bypass: API wraps yfinance calls for frontend access

**Signal Reception:**
- TradingView Webhooks
  - Purpose: Receive trade entry/exit signals from Pine Script strategy
  - Entry endpoint: `POST /webhook` - receives `EntryWebhookPayload` with symbol, SL, TP, lot size
  - Exit endpoint: `POST /webhook-close` - receives `ExitWebhookPayload` with trade_key
  - Auth: Optional `WEBHOOK_SECRET` validation (header: `X-Webhook-Signature`)
  - Transport: Validated signals pushed to Redis queue for async processing

## Data Storage

**Databases:**
- Supabase PostgreSQL
  - Connection: `SUPABASE_URL` (e.g., `https://proj-id.supabase.co`)
  - Client: `supabase-py` (Python) and `@supabase/supabase-js` (frontend)
  - Auth: Anon key for row-level security (frontend), service role key for admin ops (backend only)
  - Tables: trades, positions, account_strategies, broker_profiles, portfolio_snapshots, trading_alerts, etc.
  - Schema: Defined in `migrations/` directory with 26+ migration files

**Message Queue:**
- Redis
  - Connection: `REDIS_URL` (default: `redis://localhost:6379`)
  - Purpose: Signal queue (webhook → Redis list → worker processing)
  - Implementation: `src/adapters/redis_queue.py` (BLPOP/LPUSH operations)
  - Queue name: `QUEUE_NAME` (typically `signals_v9`)
  - Dead letter queue: `{queue_name}_dlq` for failed signal handling
  - Transport mode: `SIGNAL_TRANSPORT` (redis or memory for tests)

**File Storage:**
- Local filesystem only (no S3/cloud storage detected)
  - ML model artifacts: `ml/` directory (model.pkl, encoders.pkl)
  - Backtest logs: `tests/` and `scripts/` directories

**Caching:**
- Redis (same instance as queue)
  - Purpose: Cache symbol rules, account data, MTM snapshots
  - Implementation: `src/services/redis_cache.py`
  - TTL: Configurable per operation (default 5-30 seconds)

## Authentication & Identity

**Auth Provider:**
- Supabase Auth (managed)
  - Implementation: `@supabase/supabase-js` on frontend
  - Features: Row-level security (RLS) for data isolation
  - Frontend access: Uses anon key (limited scope)
  - Backend admin: Uses service role key (full access, backend only)

**Broker Account Linking:**
- Custom implementation (no OAuth)
  - `src/core/broker_profiles.py` - Maps broker credentials to account strategies
  - Fields: broker_type (MetaAPI), token, account_id, account_name
  - Multi-broker support: VANTAGE (forex), FXCM/IC Markets (metals/indices)

**Webhook Auth:**
- HMAC signature validation (optional)
  - Header: `X-Webhook-Signature`
  - Secret: `WEBHOOK_SECRET` env var
  - Implementation: `src/core/signal.py` (validate_webhook_payload)

## Monitoring & Observability

**Error Tracking:**
- Not detected - No Sentry/Rollbar integration found
- Fallback: In-process logging with Python logging module

**Logs:**
- Approach: Python `logging` module + structured JSON logs to stdout
  - Config: `config/logging_config.py`
  - Levels: DEBUG, INFO, WARNING, ERROR
  - Format: Timestamp, logger name, level, message
  - Storage: Console (Docker) → Docker logs → external aggregation (Railway/monitoring)

**Alerts (Operational):**
- Supabase `trading_alerts` table - Persistent alert storage
  - Implementation: `src/services/alert_service.py`
  - Fields: alert_type, severity, title, message, metadata, created_at
  - Notifiers: Discord, Telegram (pluggable protocol)

## CI/CD & Deployment

**Hosting:**
- Railway.app
  - Frontend URL: `https://frontend-production-a7cf.up.railway.app`
  - Backend URL: Configured per deployment
  - Environment variables: Set via Railway dashboard (not in repo)

**CI Pipeline:**
- Not detected - No GitHub Actions/GitLab CI configuration found
- Manual deployment via Railway CLI or git push to Railway remote

**Container Registry:**
- Docker images built on-the-fly by Railway
  - Backend image: `Dockerfile` (Python 3.11-slim)
  - Frontend image: `frontend/Dockerfile` (Node 20-alpine, multi-stage)

## Environment Configuration

**Required env vars:**
- `SUPABASE_URL` - Database endpoint
- `REDIS_URL` - Message queue endpoint
- `META_API_TOKEN` - Broker authentication (or token per broker)
- `META_API_ACCOUNT_ID` - Broker account ID (or per broker)

**Optional env vars (critical for features):**
- `AI_PROVIDER` - LLM provider (anthropic|openai|gemini|local)
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` - AI/LLM authentication
- `DISCORD_WEBHOOK_URL` - Discord notifications
- `TELEGRAM_BOT_TOKEN` - Telegram notifications
- `SUPABASE_SERVICE_ROLE_KEY` - Admin database access (backend only, never frontend)

**Frontend-specific (NEXT_PUBLIC_*):**
- `NEXT_PUBLIC_SUPABASE_URL` - Baked at build time
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Baked at build time
- `NEXT_PUBLIC_API_URL` - Backend API endpoint (optional, for health checks)

**Secrets location:**
- Backend: `.env` file at project root (loaded by config/settings.py)
- Frontend: Build-time args or environment variables (NEXT_PUBLIC_* only)
- Railway: Environment variables in dashboard (not committed to repo)

## Webhooks & Callbacks

**Incoming:**
- `POST /webhook` - TradingView entry signal (EntryWebhookPayload)
- `POST /webhook-close` - TradingView exit signal (ExitWebhookPayload)
- Both endpoints validate payload, push to Redis queue, return 200 OK

**Outgoing:**
- Discord Webhook (via `DISCORD_WEBHOOK_URL`)
  - Triggered by: Important risk guards (kill-switch, drawdown, high latency)
  - Payload: Embed with severity color, title, message, metadata
  - Implementation: `src/services/alert_service.py` (DiscordAlertNotifier)

- Telegram Bot (via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`)
  - Triggered by: Important risk guards
  - Payload: Formatted message text
  - Implementation: `src/services/alert_service.py` (TelegramAlertNotifier)

- MetaAPI Callbacks
  - Purpose: Real-time order fill notifications (not currently implemented, polling used instead)
  - Future: WebSocket streaming for low-latency execution updates

## External AI/ML Services

**LLM Providers (via unified AIClient factory):**
- Anthropic Claude
  - Auth: `ANTHROPIC_API_KEY`
  - Models: claude-3-5-sonnet, claude-3-opus (configurable)
  - Implementation: `src/ai/llm_client.py` (AnthropicClient)
  - Purpose: AI Guardian validation, Trading Council debate

- OpenAI
  - Auth: `OPENAI_API_KEY`
  - Base URL: Configurable via `AI_BASE_URL` (can route to Groq, etc.)
  - Implementation: `src/ai/llm_client.py` (OpenAIClient)
  - Models: gpt-4, gpt-4-turbo, gpt-3.5-turbo

- Groq (via OpenAI-compatible API)
  - Auth: `AI_API_KEY` (Groq API key)
  - Base URL: `https://api.groq.com/openai/v1`
  - Models: llama-3.3-70b-versatile (quick), llama-3.1-8b-instant (fallback)
  - Implementation: `src/ai/llm_client.py` (uses OpenAI client with custom base_url)

**Unified AI Client:**
- Factory: `src/ai/llm_client.py` (get_ai_client())
- Provider selection: `AI_PROVIDER` env var (anthropic|openai|gemini|local)
- Structured output: Pydantic schema validation with auto-repair on validation failure
- Timeout: Configurable (default 5 seconds)
- Fallback: Primary → Fallback model on 404 error

## Third-Party Integrations (Non-API)

**ML Models:**
- Random Forest (scikit-learn)
  - Path: `ml/model.pkl`
  - Purpose: Win probability prediction (ML Guardian filter)
  - Training: On backtest data with historical trades
  - Encoders: Stored in `ml/encoders.pkl` (LabelEncoder for symbols/signals)

**Python Libraries (Data & Analysis):**
- backtesting.py - Python backtesting framework for strategy validation
- optuna - Bayesian hyperparameter optimization for strategy tuning
- numba - JIT compilation for fast backtest execution
- lightgbm - Alternative ML model for advanced gradient boosting

---

*Integration audit: 2026-03-18*
