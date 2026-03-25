# Coding Conventions

## Backend (Python)
- **Typing**: Strong use of Python type hints throughout the codebase.
- **Validation**: Pydantic schemas define API payloads, preventing malformed data handling.
- **Formatting & Linting**: Managed by `ruff`. The codebase enforces strict adherence to PEP 8 standards with automated formatting checks.
- **Async Pattern**: Heavy usage of `asyncio` (`async def` and `await`) for non-blocking I/O operations with FastAPI and HTTP requests (MetaApi, Supabase).
- **Environment Management**: Configuration is managed via `pydantic-settings` heavily centralized around a `.env` file (`get_settings()` with `@lru_cache`).
- **Error Handling**: Granular try-catch blocks logging structured errors into Supabase or external monitors.

## Frontend (TypeScript/Next.js)
- **TypeScript**: Strict typings enforced via `tsconfig.json`.
- **Linting**: Controlled via `eslint.config.mjs` ensuring consistent React/TS style.
- **Component Pattern**: Standard functional React components with Hooks. Server vs. Client components are separated based on Next.js 14+ paradigms.

## Version Control & Task Management
- Commits and pull requests are tethered to Jira tickets. Every feature/bug requires an auto-generated Jira ticket (via `AGENTS.md` rules) appended to the branch name/commit.
