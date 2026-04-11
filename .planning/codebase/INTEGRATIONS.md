# External Integrations

## Trading & Execution

**MetaApi Cloud**
- Purpose: Real-time trade execution on MetaTrader 4/5 brokers
- SDK: metaapi-cloud-sdk v29+
- Features:
  - WebSocket streaming (`METAAPI_STREAMING_ENABLED`)
  - Multi-broker support (Vantage for Forex, FXCM/IC Markets for metals/indices)
  - Multi-account broadcasting capability
  - Realtime event streaming for PnL updates
- Implementation: `src/adapters/metaapi.py`, `src/services/metaapi_streaming_service.py`
- Auth: API token via env var

**TradingView**
- Purpose: Webhook signal ingestion
- Direction: Inbound only
- Endpoint: `POST /webhook`
- Fields: `symbol`, `side`, `entry`, `sl`, `tp`, `size`
- Security: `WEBHOOK_SECRET` (optional)
- Implementation: `src/api.py` webhook handler

## AI & LLM Services

**Groq (Primary Provider)**
- Purpose: High-performance LLM inference for Trading Council
- Models: llama-3.3-70b-versatile (deep analysis), llama-3.1-8b-instant (quick screening)
- Pattern: Two-tier allocation - Quick for fast screening, Deep for complex analysis
- SDK: langchain-groq
- Implementation: `src/ai/llm_client.py`, `src/ai/trading_council.py`

**OpenAI**
- Purpose: Alternative LLM provider
- Models: GPT-4, GPT-3.5-turbo
- SDK: langchain-openai
- Fallback when Groq unavailable

**Anthropic**
- Purpose: Claude models for analysis
- SDK: langchain-anthropic
- Alternative provider option

**Google Gemini**
- Purpose: Additional AI capabilities
- Model: gemini-2.0-flash-exp
- SDK: langchain-google-genai

## Data & Storage

**Supabase**
- Purpose: Database, authentication, and realtime subscriptions
- Backend Client: supabase-py 2.12.0
- Frontend Client: @supabase/supabase-js 2.49.1 + @supabase/ssr 0.5.2
- Features:
  - PostgreSQL database
  - Realtime subscriptions (used in dashboard)
  - Row Level Security (RLS)
  - Auth with JWT
- Tables: signals, trades, accounts, system_config, pnl, risk_events
- Implementation: 
  - Backend: `src/adapters/supabase.py`, `src/adapters/supabase_api.py`
  - Frontend: `frontend/src/lib/supabase.ts`, various hooks

**Redis**
- Purpose: Task queue and rate limiting cache
- Client: redis-py 5.2.1
- Queue Library: RQ (Redis Queue)
- Usage:
  - Signal queue between API and Worker
  - Rate limit cache for webhook endpoints
  - Job scheduling with APScheduler
- Docker: Redis 7 Alpine

**Yahoo Finance**
- Purpose: Market data retrieval
- Library: yfinance 0.2.52
- Usage: Market context for trading decisions, backtesting data

## Notifications & Communication

**Discord**
- Purpose: Trade notifications and system alerts
- Features:
  - Webhook notifications (`DISCORD_WEBHOOK_URL`)
  - Bot thread creation (`DISCORD_BOT_TOKEN`)
  - Slash command verification (`DISCORD_PUBLIC_KEY`)
- Implementation: `src/adapters/discord.py`
- Channels: Trade alerts, system health, error notifications

**Telegram**
- Purpose: Trade notifications
- Bot Token: `TELEGRAM_BOT_TOKEN`
- Chat ID: `TELEGRAM_CHAT_ID`
- Usage: Trade execution confirmations, alerts

## Project Management

**Jira**
- Purpose: Issue tracking and project management
- Integration: REST API + custom automation scripts
- Scripts: `scripts/jira-agent.js`, `scripts/jira-sync.js`
- Config: `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`
- Implementation: `src/adapters/jira.py`
- Requirement: Every non-trivial task must have DEV-XX ticket

## Deployment & Infrastructure

**Railway**
- Purpose: Primary deployment platform
- Configuration:
  - `railway.json` - API service with Docker builder
  - `railway.json` (frontend) - Nixpacks builder, standalone server.js
  - `nixpacks.toml` - API Nixpacks config (venv + uvicorn)
  - `nixpacks.worker.toml` - Worker Nixpacks config (venv + python -m src.worker)
- Watch patterns: src/**/*.py, config/**/*.py

**Docker**
- Purpose: Local development and production containerization
- Services:
  - API (FastAPI + uvicorn)
  - Worker (Python RQ consumer)
  - Redis (queue + cache)
  - Frontend (Next.js standalone)
- Files: `docker-compose.yml`, `Dockerfile`, `Dockerfile.api`, `Dockerfile.worker`, `frontend/Dockerfile`

## WebSocket & Real-time

**MetaApi Streaming**
- Purpose: Real-time trade events and PnL updates
- Protocol: WebSocket
- Events: Order updates, position changes, account balance updates
- Flow: MetaApi → Worker → Supabase → Supabase Realtime → Frontend
- Implementation: `src/services/metaapi_streaming_service.py`

**Supabase Realtime**
- Purpose: Live data subscriptions for dashboard
- Tables watched: signals, trades, pnl, risk_status, accounts
- Frontend hooks: `useRiskStatus.ts`, `usePositions.ts`, `useSignals.ts`

## Browser Automation

**Playwright**
- Purpose: Automated browser testing and data extraction
- Version: 1.52.0
- Usage: Web scraping, automated testing
- Browsers: Chromium, Firefox, WebKit

## Environment Configuration

**Required Environment Variables:**

**Trading & Risk:**
- `AI_FILTER_ENABLED` - Toggle AI validation
- `ML_GUARDIAN_ENABLED` - Toggle ML model validation
- `TRINITY_ENABLED` - Toggle Trinity risk engine
- `PAPER_TRADING` - Paper vs live trading mode
- `PROP_FIRM_EVAL_MODE` - Enable FTMO-style evaluation tracking

**API Keys:**
- `METAAPI_TOKEN` - MetaApi Cloud authentication
- `SUPABASE_URL`, `SUPABASE_KEY` - Database connection
- `GROQ_API_KEY` - Primary LLM provider
- `OPENAI_API_KEY` - Alternative LLM
- `ANTHROPIC_API_KEY` - Claude access
- `GEMINI_API_KEY` - Google AI access

**Infrastructure:**
- `REDIS_URL` - Redis connection string
- `WEBHOOK_SECRET` - TradingView webhook validation
- `DISCORD_WEBHOOK_URL`, `DISCORD_BOT_TOKEN` - Discord integration
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Telegram integration

**Jira:**
- `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`, `JIRA_EMAIL`

---

*Integration audit: 2025-01-09*