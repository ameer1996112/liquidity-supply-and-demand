# Concerns & Technical Debt

## Reliability & Execution Risk
- **Webhook Latency**: Since trading relies on fast execution, any latency between TradingView -> API -> Redis -> Worker -> MetaApi can cause slippage.
- **API Rate Limits**: Reliance on external endpoints (MetaApi, Supabase, LLMs). Hard limits or network issues there can cascade.
- **State Management Consistency**: Desyncs between actual position state on MetaTrader and the database state on Supabase.

## Architecture
- **In-Memory Caching vs Redis**: Mixing local memory (`@lru_cache`, globals) with Redis limits horizontal scalability. The worker instance handles memory models.
- **Multiple Sources of Truth**: Pine script holds rule logic, while the Python worker acts as a second enforcer (ML Guardrail). Logic divergence needs monitoring.

## Testing & Quality
- **Test Coverage**: While tests exist, complex AI decision branches (Trading Council debates) and non-deterministic ML models are notoriously hard to unit test reliably.
- **Frontend Refactoring Needed**: There are some lingering linter errors and test failures (e.g., `tradingMetrics.test.ts`) inside Next.js that need fixing.

## Security
- Handling webhook secrets properly per endpoint (`WEBHOOK_SECRET`). Supabase Anonymous keys vs Service Role keys. Ensuring the front-end never leaks sensitive LLM or MetaApi credentials.
