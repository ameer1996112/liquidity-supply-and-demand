# Coding Conventions

## General Principles
- **Domain-Driven Design**: Code is grouped by business domain or feature rather than strictly by technical concern, keeping related logic together.
- **Strict Typing**: Both the Python backend and Next.js frontend rely on strict typing.

## Backend (Python)
- **Typing**: Use of Python type hints (`typing`), enforced via tools like `mypy` (when available) and `ruff`.
- **Validation**: Strict schema validation using **Pydantic** models. All data entering the boundaries of the system (APIs, Webhooks, DB results) must be validated.
- **Async First**: Use of `async def` for FastAPI routes and I/O-bound operations (Supabase calls, LLM api calls) to ensure high concurrency.
- **Linting & Formatting**: `ruff` is the primary linter (`ruff check backend tests`). Code must conform to standard Python `PEP 8` conventions with strict formatting.
- **Error Handling**: Use of appropriate FastAPI `HTTPException`s and custom domain errors. Standardize API responses using consistent structures.

## Frontend (Next.js / React)
- **TypeScript**: Strict TypeScript configuration. Avoid `any`.
- **Next.js App Router**: Leverage Server Components by default for better performance and SEO. Use `'use client'` strategically for interactive components that require state.
- **Tailwind with `cn()` utility**: Component styling is done via Tailwind CSS utility classes. The `cn()` helper (a wrapper around `clsx` and `tailwind-merge`) is conventionally used for dynamically combining class names without conflicts.
- **State Management**: Client-side async state, data fetching, and caching should primarily be handled via **TanStack React Query**.
- **Linting**: Conforms to standard Next.js `eslint` rules.

## Git & Workflow
- **Jira Automation**: Heavily integrated with Jira for issue tracking. Branch naming and commits are linked to Jira tickets automatically via custom workflow scripts (e.g. `scripts/jira-sync.js`).
