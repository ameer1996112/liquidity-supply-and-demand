# INTEGRATIONS

## Primary Database & Auth
- **Supabase**: Used for data persistence, alerts, and authentication. Handled via `supabase` python client and `@supabase/supabase-js` React client.

## Message Broker & State
- **Redis**: Acts as the message queue between the FastAPI webhook receiver and the Python Worker. Requires `localhost:6379`.

## External APIs & Services
- **TradingView**: System receives TradingView webhook signals on the `POST /webhook` FastAPI route.
- **LLM Providers**: OpenAi and Anthropic used for AI/ML guardrails and agentic behaviors (Trading Council).
- **Market Data**: yfinance for market data.
- **Other Inputs**: youtube-transcript-api, scrapetube for external data ingestion.
