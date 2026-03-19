# CONCERNS

## Technical Debt & Bugs
- **MetaAPI Timeouts**: The system is prone to intermittent "Read timed out" errors during background MetaAPI operations (like broker reconciliation) due to strict 5-second timeouts.
- **Production API CORS Issues**: There are known CORS policy violations blocking API requests in the production environment.
- **Frontend Crashes**: Intermittent JavaScript errors (e.g., `l.map is not a function`) crashing the frontend when processing account data.
- **Market Data Errors**: `yfinance` occasionally throws HTTP 404 errors when fetching specific market data (like GBPJPY).
- **Execution Latency**: Trade execution pipeline suffers from latency due to serial price pre-fetching before order submissions.

## Tooling & Linting Warnings
- Backend has 98 `ruff` linting warnings.
- Frontend has multiple ESLint warnings/errors and 1 failing Vitest test (`tradingMetrics.test.ts`).

## Configuration Gotchas
- `config/settings.py` aggressively caches `.env` values using `@lru_cache`. The backend process must be restarted for environment changes to take effect.
- Local development requires a local Redis server running on `localhost:6379`. The backend fails-fast if Redis is not detected.
