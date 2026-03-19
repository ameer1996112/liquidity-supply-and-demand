# INTEGRATIONS.md — External Services & APIs

## Supabase (Primary Data Layer)

**Purpose:** PostgreSQL database, authentication, and realtime push  
**Adapter:** `src/adapters/supabase.py` (41KB — largest adapter file)  
**Client:** `supabase-py` ==2.10.0  

### Usage
- **Database:** All signal, trade, account, and analytics records
- **Auth:** User authentication (frontend uses anon key; backend uses service role key)
- **Realtime:** Supabase channels for live signal feed to frontend
- **Row Level Security:** Enforced — backend bypasses with service role key only
- **Frontend client:** `@supabase/supabase-js` — direct browser subscriptions

### Env vars
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...   # ⚠️ Backend only, never expose to frontend
NEXT_PUBLIC_SUPABASE_URL=...    # Frontend (baked at build)
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

---

## Redis (Signal Queue + Cache)

**Purpose:** Decoupled message queue between API and Worker, plus caching  
**Adapter:** `src/adapters/redis_queue.py`  
**Client:** `redis-py` ≥5.0.0  

### Usage
- **Queue:** API pushes signals; Worker pops and processes them
- **Caching:** Account balances, broker name lookups (permanent cache)
- **Signal transport mode:** Configurable via `SIGNAL_TRANSPORT=redis` (default) or `memory` (tests)
- **Fail-fast:** API checks Redis on startup and refuses to start if unavailable

### Env vars
```
REDIS_URL=redis://localhost:6379
SIGNAL_TRANSPORT=redis   # or 'memory' for tests
```

---

## MetaAPI (Broker Execution)

**Purpose:** Connect to MetaTrader 5 accounts via cloud SDK for live order execution  
**Adapter:** `src/adapters/execution/meta_api_adapter.py`  
**Client:** MetaApi cloud SDK (Python)  

### Usage
- **Supported brokers:** Vantage (Forex), FXCM/IC Markets (Metals/Indices)
- **Operations:** Open/close positions, fetch account balance, get open positions, price quotes
- **Multi-account:** Two separate broker configs (VANTAGE for FX, FXCM for metals/indices)
- **Symbol mapping:** `src/core/broker_profiles.py` — maps TradingView symbols to broker-specific symbols (e.g., `GBPUSD` → `GBPUSD.raw`)
- **Background reconciliation:** Periodic sync of broker positions with Supabase records (APScheduler)
- **Timeout settings:** Fast path (trade execution) vs background path (reconciliation)

### Env vars
```
META_API_TOKEN=...               # Default/Vantage token
META_API_ACCOUNT_ID=...
META_API_REGION=new-york
META_API_TOKEN_VANTAGE=...
META_API_ACCOUNT_ID_VANTAGE=...
META_API_TOKEN_FXCM=...          # FXCM/IC Markets
META_API_ACCOUNT_ID_FXCM=...
```

---

## AI Providers (LLM Guardrails)

**Purpose:** Multi-LLM ensemble for trade signal validation  
**Adapters:** `src/ai/` directory, `src/core/guard_rails/`  

### OpenAI / Groq (via OpenAI-compatible API)
- **Primary model:** `llama-3.3-70b-versatile` (Groq)
- **Fallback model:** `llama-3.1-8b-instant` (Groq)
- **Base URL:** `https://api.groq.com/openai/v1`
- **Usage:** Fast quick-check tier; AI Guardian confidence scoring

### Anthropic (Claude)
- **Provider:** `anthropic` library ≥0.18.0
- **Usage:** Deep analysis tier; Trading Council debates

### Two-Tier AI Architecture
- **Quick:** `AI_QUICK_MODEL=llama-3.1-8b-instant` — fast first pass
- **Deep:** `AI_DEEP_MODEL=llama-3.3-70b-versatile` — escalation on borderline signals
- **AI Mode:** `shadow` (log only, no block) or `enforce` (block failing signals)

### Env vars
```
AI_FILTER_ENABLED=true
AI_PROVIDER=anthropic
OPENAI_API_KEY=...
AI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=llama-3.3-70b-versatile
ANTHROPIC_API_KEY=...
AI_MIN_CONFIDENCE=75
AI_TIMEOUT_SECONDS=5
```

---

## TradingView (Signal Source)

**Purpose:** Incoming webhook signals from TradingView Pine Script strategy  
**Entry point:** `POST /webhook` (in `src/api.py`)  

### Webhook Payload
```json
{
  "symbol": "GBPUSD",
  "side": "BUY",
  "entry": 1.2500,
  "sl": 1.2450,
  "tp": 1.2600,
  "size": 0.1
}
```

### Security
- Optional `WEBHOOK_SECRET` header validation
- Rate limited via slowapi
- Staleness guard: rejects signals >5 seconds old (`STALENESS_MAX_AGE_SECONDS=5`)

---

## Discord / Telegram (Notifications)

**Purpose:** Trade execution notifications and alerts  
**Adapters:** `src/adapters/discord.py`  

### Usage
- Signal received, trade executed, risk limit hit, error alerts
- Discord webhook (HTTP POST)
- Telegram bot (Bot Token + Chat ID)

### Env vars
```
DISCORD_WEBHOOK_URL=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

---

## Yahoo Finance (Market Data)

**Purpose:** Historical OHLCV data for ML model features  
**Adapter:** `src/adapters/market_data.py`  
**Client:** `yfinance` ≥0.2.36  

### Usage
- Technical indicator calculation (RSI, ATR, MACD, Bollinger Bands)
- ML Guardian feature engineering
- Symbol mapping required: TradingView symbols → Yahoo Finance format

### Known Issue
- HTTP 404 errors for some symbols (e.g., GBPJPY) — symbol mapping may need tuning

---

## YouTube / Web Scraping (Strategy Research)

**Purpose:** Automated strategy research from YouTube content  
**Libraries:** `youtube-transcript-api`, `scrapetube`, `beautifulsoup4`, `lxml`  

### Usage
- Transcript extraction from YouTube strategy videos
- Part of AI Copilot / strategy analysis features
- `src/api_copilot.py` exposes endpoints for this

---

## Paper Trader (Internal Simulation)

**Purpose:** Simulated execution without real broker  
**Adapter:** `src/adapters/paper_trader.py`  

### Usage
- Enabled via `PAPER_TRADING_ENABLED=true`
- In-memory position tracking
- Useful for testing guardrail pipeline without MetaAPI
