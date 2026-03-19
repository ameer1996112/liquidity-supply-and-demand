# Coding Conventions

**Analysis Date:** 2026-03-19

## Naming Patterns

**Python Files:**
- API modules: `api_<domain>.py` (e.g., `src/api_positions.py`, `src/api_analytics.py`, `src/api_funding.py`)
- Service modules: snake_case noun (e.g., `src/services/execution_engine.py`, `src/services/account_orchestrator.py`)
- Core domain: snake_case (e.g., `src/core/risk_engine.py`, `src/core/consumer_validator.py`)

**Python Functions:**
- snake_case for all functions and methods
- Private helpers: `_prefix` (e.g., `_get_supabase()`, `_is_signal_closed()`, `_make_payload()`)
- Boolean predicates: `is_` or `has_` prefix (e.g., `_is_signal_closed()`, `_is_signal_open_strict()`, `is_supabase_connection_error()`)

**Python Classes:**
- PascalCase throughout (e.g., `RiskCheckResult`, `TradeRiskParams`, `ActivePosition`, `ReconciliationInfo`)
- Pydantic models: PascalCase, often suffixed with `Request`, `Response`, `Result`, `Config`
- Observer pattern classes: suffixed with `Observer` or `Subject` (e.g., `AuditorObserver`, `WorkerSubject`)

**Python Constants:**
- UPPER_SNAKE_CASE (e.g., `DEFAULT_MAX_DAILY_LOSS_PCT`, `_BALANCE_CACHE_TTL`, `GREEN`, `RED`)

**TypeScript/React Files:**
- React components: PascalCase `.tsx` (e.g., `RecentSignalsPanel.tsx`, `PositionCard.tsx`, `ReconciliationAlert.tsx`)
- Custom hooks: `use` prefix, camelCase (e.g., `useActivePositions`, `usePositions.ts`, `useTradingSignals`)
- Utility files: camelCase `.ts` (e.g., `format.ts`, `formatters.ts`, `exportCsv.ts`)
- Page files: `page.tsx` in Next.js app router directory

**TypeScript Types:**
- `interface` for object shapes (e.g., `ActivePosition`, `ReconciliationInfo`, `AccountStatus`)
- `type` for unions and aliases (e.g., `SignalSide`, `TradingMode`, `SignalStatus`, `EmptyWinRateBehavior`)
- Enums: PascalCase type names, string literal members (e.g., `'buy' | 'sell'`, `'LIVE' | 'PAPER'`)

**TypeScript Variables/Functions:**
- camelCase for variables and functions (e.g., `positionKeys`, `getApiUrl`, `formatSignedCurrency`)
- Query key objects: `<domain>Keys` pattern (e.g., `positionKeys.active`)

## Code Style

**Python Formatting:**
- No explicit formatter config detected (no `.ruff.toml`, `.black`, or `pyproject.toml`)
- 4-space indentation, lines generally under 100 chars
- Section separators with `# ── Label ──────────` pattern used throughout

**TypeScript Formatting:**
- ESLint with `eslint-config-next` (core-web-vitals + typescript presets)
- Several rules disabled: `@typescript-eslint/no-explicit-any`, `no-unused-vars`, `react-hooks/exhaustive-deps`, `react-hooks/rules-of-hooks`
- `strict: true` in `tsconfig.json` — enforces strict null checks and type safety
- `@/*` path alias maps to `frontend/src/*`

**CSS/Styling:**
- Tailwind CSS v4 with design tokens via CSS variables (`var(--to-text-dim)`, `var(--to-border)`)
- `cn()` utility (`clsx` + `tailwind-merge`) for conditional class merging
- Component variants use `cn(baseClasses, className)` spread pattern
- `data-slot` attributes on Radix UI wrappers for semantic targeting

## Import Organization

**Python Order:**
1. Standard library (`import logging`, `from datetime import`, `from typing import`)
2. Third-party (`from fastapi import`, `from pydantic import`)
3. Internal config (`from config import get_settings`)
4. Internal src (`from src.adapters...`, `from src.core...`, `from src.services...`)

**TypeScript Order:**
1. React and framework (`'use client'` directive first, then `import { useState } from 'react'`)
2. Third-party (`@tanstack/react-query`, `lucide-react`, `recharts`)
3. Internal hooks (`@/hooks/...`)
4. Internal components (`@/components/...`)
5. Internal types and lib (`@/types/...`, `@/lib/...`)

**Path Aliases:**
- `@/` maps to `frontend/src/` (configured in `tsconfig.json` and `vitest.config.ts`)

## Error Handling

**Python Backend Pattern:**
- FastAPI endpoints catch broad `except Exception as exc` and re-raise as `HTTPException`
- Supabase connection errors detected with `is_supabase_connection_error()` helper, then client is reset
- Internal helpers swallow non-critical errors silently with `except Exception: pass` (used for non-blocking operations like notes)
- Logging at error/warning level before re-raise: `logger.error("...", exc)`
- Risk/execution paths use explicit typed return objects (`RiskCheckResult`, `ExecutionResult`) rather than exceptions

**TypeScript Frontend Pattern:**
- React Query error states handled via `isLoading`, `isError`, `error` from `useQuery`
- `apiFetch()` throws `Error` with message `API Error (${status}): ${text}` on non-OK responses
- Null-safe display helpers: `safeFloat()` returns `'--'` for null/undefined, `formatSignedCurrency()` returns `'—'`
- `getApiUrl()` returns empty string when not configured; callers guard with `if (!base) throw new Error(...)`

## Logging

**Python Framework:**
- Standard `logging` module via `config.logging_config.get_logger(name)`
- Named loggers: `"trinity.api"`, `"trinity.logic"` (application namespace prefix)
- Simple modules use: `logger = logging.getLogger(__name__)`

**Python Patterns:**
- `logger.debug(...)` for cache hits, verbose trace data
- `logger.info(...)` at key decision points (trade opened, closed, balance fetched)
- `logger.warning(...)` for non-fatal degraded states (fetch failed, latency exceeded)
- `logger.error(...)` for failures that need attention but don't crash
- `%s` string formatting used (not f-strings) in logger calls

**TypeScript:**
- No structured logging framework — `console.error` / `console.warn` only for developer warnings
- React Query handles loading/error state visibility without logging

## Comments

**Python Docstrings:**
- Module-level: short triple-quoted summary (1-3 lines describing purpose)
- Functions: Google-style docstrings with `Args:`, `Returns:` sections on public/shared functions
- Private helpers: inline comment or brief docstring

**Python Inline Comments:**
- Section headers: `# ── Section Name ───` with em-dash box drawing for visual grouping
- Optimization notes: `# OPT-2 (latency): ...` prefix for performance decisions
- Workaround notes: describe the "why" (e.g., `# macOS Python 3.x doesn't bundle root certs`)

**TypeScript/TSDoc:**
- JSDoc blocks (`/** ... */`) used on utility functions in `lib/format.ts` and `lib/api.ts`
- `@param`, `@returns` tags used for public helper functions
- In-component: inline `{/* Section comment */}` JSX comments for layout sections
- Type files: `// CRITICAL: ...` for contract-sensitive fields in `types/trading.ts`

## Function Design

**Python:**
- Private helpers prefixed with `_` and kept short (10-30 lines)
- Functions that access external services accept injected clients or call lazy getters internally
- Pure domain functions (no I/O) in `src/core/` (e.g., `calculate_max_position_size`)
- Settings accessed via `get_settings()` call (not global state at module load)

**TypeScript:**
- Custom hooks encapsulate all data fetching and return typed query results
- `useMemo` for filtered/derived state in page components
- Page components use named sub-functions for complex sections (e.g., `PositionsPageContent`)
- Utility functions are pure: receive explicit arguments, no side effects

## Module Design

**Python Exports:**
- No `__all__` in most modules — all public names are accessible
- FastAPI routers exported as `router` (e.g., `router = APIRouter(...)`)
- Service singletons initialized lazily via getter functions (e.g., `get_api_supabase()`)

**TypeScript Exports:**
- Named exports preferred (e.g., `export function cn(...)`, `export const positionKeys`)
- Default export reserved for page components (`export default function PositionsPage()`)
- Barrel files not used — each module imports directly from source

**Lazy Initialization Pattern (Python):**
- Module-level singleton `_client = None`, initialized on first call
- Pattern: `if _client is not None and (now - _created_at) < MAX_AGE: return _client`
- Used for: Supabase client (`src/adapters/supabase_api.py`), Redis client, balance cache in `src/logic.py`

---

*Convention analysis: 2026-03-19*
