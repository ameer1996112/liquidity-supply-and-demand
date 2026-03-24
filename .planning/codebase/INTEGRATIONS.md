# External Integrations

## Databases & Authentication
- **Supabase**: Primary database and authentication provider. Utilizes `supabase` Python client on the backend and `@supabase/supabase-js` on the frontend. Expects `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
- **Redis**: Fast key-value store used for state management, worker queues, and caching.

## Trading & Market Data
- **TradingView**: Webhook API integration for receiving trading signals. The backend exposes a `/webhook` endpoint (secured via `WEBHOOK_SECRET`).
- **yfinance**: Used for fetching historical or live market data.
- **Miscellaneous Scrapers**: `beautifulsoup4`, `youtube-transcript-api`, `scrapetube` used for sentiment analysis or data gathering.

## AI & Large Language Models
- **OpenAI**: Core AI provider, often used via LangChain.
- **Anthropic**: Alternative/Secondary LLM provider, likely used for complex reasoning or specialized internal debate (Trading Council).

## Notifications & Alerts
- **Discord**: Webhook integration (`DISCORD_WEBHOOK_URL`) for trading alerts and system health notifications.
- **Telegram**: Bot integration (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) for user notifications or command interfaces.

## Prop Firm & Broker Specific (Inferred from API structure)
- The codebase contains specific API modules (`api_prop_firm.py`, `api_prop_firm_v1.py`), suggesting integration with specific proprietary trading firm APIs or risk monitoring dashboards.
