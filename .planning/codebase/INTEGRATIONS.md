# External Integrations

## Trading & Brokerage
- **TradingView**: Inbound webhooks for trade signals / alerts.
- **MetaApi**: Outbound API for executing trades on MT4/MT5 accounts. Supports real-time push-based trade events.

## Artificial Intelligence
- **OpenAI / Anthropic**: Used via Langchain for AI filtering and Trading Council (multi-agent debate).

## Data Storage & Caching
- **Supabase**: Primary database (PostgreSQL), real-time subscriptions, and authentication mapping.
- **Redis**: Used as a message queue between the FastAPI webhook receiver and the Python Worker. Also stores rate limits and caching states.

## Notifications & Alerts
- **Discord**: Webhook integration for trade signals and system health alerts.
- **Telegram**: Bot integration for notifications (via bot token and chat ID).

## External Services
- **yfinance**: Market data fetching inside Python backend.
- **YouTube Transcripts**: Used for RAG/Information extraction on trading concepts.
