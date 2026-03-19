# CONVENTIONS

## Backend (Python/FastAPI)
- **Architecture**: Domain-Driven Design (DDD).
- **Type Safety**: Pydantic models used extensively for request/response validation and settings management (`pydantic-settings`).
- **Linting & Formatting**: `ruff` is the standard linter (`ruff check src/ config/ tests/`). Currently has 98 pre-existing warnings.
- **Dependency Management**: Standard `requirements.txt`.
- **Environment**: Managed via `.env` files, loaded primarily in `config/settings.py`. Note that settings use `@lru_cache`, so any changes to the `.env` file require a full process restart to take effect.

## Frontend (Next.js/React)
- **Styling**: Tailwind CSS v4 with standard utility classes.
- **Component System**: Radix UI primitives as the base for the design system.
- **Linting**: Standard ESLint (`npx eslint`). Currently has pre-existing warnings/errors.
