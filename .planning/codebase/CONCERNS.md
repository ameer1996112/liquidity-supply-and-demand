# Known Concerns & Technical Debt

## Backend Issues
- **Linting Warnings**: There are currently around 98 pre-existing warnings when running `ruff check src/ config/ tests/` that need to be addressed to ensure clean CI/CD pipelines.
- **Worker Logs**: There are known warnings in the worker logs, specifically `"No bar_time in payload"` in the `StalenessGuard` and `"Symbol subscription returned HTTP 404"` in the `MetaApiAdapter` that can cause unnecessary noise.
- **Infrastructure Dependency**: The system heavily relies on Redis being available on `localhost:6379`. The backend fails-fast if Redis is not running prior to startup.
- **Environment Caching**: `config/settings.py` uses `@lru_cache` for `get_settings()`. Modifying `.env` requires a full backend restart for changes to apply.

## Frontend Issues
- **Test Failures**: There is a known pre-existing failure in `tradingMetrics.test.ts` when running `vitest run`, which needs fixing.
- **Linting Errors**: The frontend has pre-existing warnings and errors when running `npx eslint`.
- **Complexity**: The migration towards a Next.js App Router for the dashboard and the standalone Jira app introduces potential state management complexities if not strictly typed.
