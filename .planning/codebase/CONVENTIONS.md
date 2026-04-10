# Coding Conventions

This document describes the conventions used across the trading system codebase. All contributors (human and agent) must follow these rules.

---

## General Principles

- **Minimal safe patches over rewrites.** Change only what is needed to fix the problem or add the feature.
- **No silent failures.** Every error path must log and either raise or return a structured failure.
- **Idempotent handlers.** HTTP endpoints and worker consumers must be safe to replay (duplicate signals must not double-execute).
- **Typed contracts everywhere.** Use Pydantic models for all data entering or leaving a service boundary.

---

## Project Structure

```
src/           Backend API, services, worker, core domain logic
frontend/      React/Next.js UI
tests/         Automated test suite (pytest)
scripts/       One-off utilities, diagnostics, backfills
migrations/    Database schema changes (numbered, sequential)
config/        Settings, logging configuration
docs/          Plans, decisions, worklog, bugs, conventions
ml/            Local model files and ML assets
data/          Datasets and exports (do not scan unless requested)
```

**Rules:**
- Frontend-only work stays in `frontend/`.
- Backend/domain work stays in `src/`, `tests/`, `migrations/`.
- Utility/debug scripts stay in `scripts/`.

---

## Python Backend

### Module structure

- `src/api.py` — FastAPI entrypoint. Receives webhooks, validates, pushes to transport. No business logic.
- `src/worker.py` — Consumer/orchestrator. Runs guards then executes trades.
- `src/logic.py` — Trade execution logic (open, close, update positions).
- `src/core/` — Pure domain: risk engine, guard rails, observers, signal validation.
- `src/services/` — External integrations: MetaAPI, watchdog, trailing stops, analytics.
- `src/adapters/` — Infrastructure adapters: Redis, Supabase, execution adapters.
- `src/ai/` — ML brain, debate agents, ensemble.

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- API routers: prefix file with `api_` (e.g. `api_positions.py`)

### Imports

- Standard library first, then third-party, then local (`src.*`, `config.*`).
- Use absolute imports from the project root. Never use relative imports across packages.
- Guard optional imports with `try/except ImportError` and log a warning when a non-critical dependency is missing.

### Settings and configuration

- All configuration lives in `config/settings.py` via Pydantic `Settings`.
- Access settings via `get_settings()` — never construct `Settings()` directly in application code.
- New fields must have a default or be documented in `.env.example`.
- Do not hardcode credentials, tokens, or environment-specific values anywhere in `src/`.

### Logging

- Use `get_logger("trinity.<module>")` from `config.logging_config`.
- Log at decision points: signal received, guard passed/rejected, trade submitted, error caught.
- Include `symbol`, `trade_key`, and `correlation_id` in log context wherever available.
- Never log raw credentials or API tokens.

### Error handling

- Raise domain-specific exceptions where appropriate; catch at the boundary (API handler or worker loop).
- Worker observers must never raise — swallow exceptions internally and log.
- Auditor observer calls must be wrapped so a DB failure never breaks the pipeline.

### Risk and execution changes

Any change to `src/core/risk_engine.py`, `src/worker.py` guard logic, or `src/logic.py` execution flow **must**:
1. Identify all affected modules.
2. Add or update tests covering the changed path.
3. Write a short note in `docs/decisions.md`.

---

## API Contract Rules

- Never change an API response shape without updating:
  - The Pydantic model in `src/`
  - The TypeScript type in `frontend/src/types/`
  - The relevant test(s) in `tests/`
  - `docs/` if the endpoint is documented
- Endpoint paths follow `kebab-case` (e.g. `/positions/cleanup-stale`).
- All list responses include at minimum: the data array and a count or total.
- Status filters in database queries must include both uppercase and lowercase variants (e.g. `["CLOSED", "closed"]`) until the DB is normalised.

---

## Database / Migrations

- Migration files are numbered sequentially: `001_`, `002_`, etc.
- Each migration file is a standalone SQL file in `migrations/`.
- Never modify an already-applied migration — create a new one.
- Migrations must be idempotent where possible (use `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`).

---

## Frontend (React / Next.js / TypeScript)

### File and folder conventions

- Pages live in `frontend/src/app/` following Next.js App Router conventions.
- Shared components in `frontend/src/components/`.
- Domain types in `frontend/src/types/` — one file per domain area.
- API calls in `frontend/src/lib/` or co-located `api/` folders under the feature.
- Hooks in `frontend/src/hooks/`.

### Component standards

- Every data-fetching page or component must handle three states: **loading**, **error**, **empty**.
- No duplicate windows or panels for the same data.
- Labels must be unambiguous — avoid "N/A", "Unknown", or blank values without explanation.
- Prefer reusable shared components over one-off patches inside a single page.

### Typing

- All API response shapes must have a corresponding TypeScript interface or type in `frontend/src/types/`.
- Never use `any` for API response data. Use explicit types or `unknown` with a type guard.

### Styling

- Use Tailwind CSS utility classes.
- Follow existing spacing and typography scale — do not introduce arbitrary pixel values.
- Dark mode is the default; ensure contrast ratios meet accessibility standards.

---

## Observer / Event Pipeline

The worker pipeline uses an Observer pattern (`src/core/observers/`):

- `WorkerSubject` emits `SIGNAL_RECEIVED`, `ORDER_SUBMITTED`, or `ERROR` events.
- Each observer's `on_event()` must never raise — exceptions are swallowed so the pipeline continues.
- `TradeEvent` is a frozen dataclass — do not attempt to mutate fields after creation.
- Every signal gets a unique `correlation_id` (UUID4 hex) injected before processing; all events for a signal share the same ID.
- Attach order in `worker.py`: Auditor → Risk → Executor → Metrics → AccountRouter.

---

## Tracking and Documentation

After any meaningful work session, update:
- `docs/worklog.md` — what was done and why
- `docs/bugs.md` — if a bug was found or fixed
- `docs/decisions.md` — if architecture or risk logic changed

Board tickets (Kanban) are the canonical source of truth for in-flight bugs and features across sessions. Use `TodoWrite` only for ephemeral sub-steps within a single session.
