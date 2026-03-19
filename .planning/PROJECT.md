# Trading System Optimization & Refactor

## What This Is

A full-scale cleanup and professionalization of the institutional liquidity-based algorithmic trading system. This includes removing dead/redundant code, enforcing Domain-Driven Design (DDD) boundaries, resolving all linting and testing errors, and fixing critical bugs (CORS, MetaAPI timeouts). 

## Core Value

Achieve a robust, highly reliable, clear, and maintainable trading system codebase that meets professional enterprise standards.

## Requirements

### Validated

- ✓ Fully functional Next.js real-time trading dashboard (Frontend)
- ✓ FastAPI webhook receiver (Backend API)
- ✓ Redis-based asynchronous signal processing queue
- ✓ Python Worker for AI/ML guardrails and trade execution
- ✓ Supabase integration for DB and Auth

### Active

- [ ] Remove all dead code, unused scripts, and deprecated feature branches.
- [ ] Deduplicate functionality and standardise helper methods across the stack.
- [ ] Refactor architecture to strictly adhere to Domain-Driven Design (DDD) component boundaries.
- [ ] Fix all existing `ruff` lint warnings in the backend (currently ~98).
- [ ] Fix all ESLint warnings and the failing Vitest test (`tradingMetrics.test.ts`) in the frontend.
- [ ] Resolve production API CORS policy violations.
- [ ] Fix MetaAPI "Read timed out" errors during background reconciliation tasks.
- [ ] Fix `yfinance` HTTP 404 errors for market data fetching.
- [ ] Optimize MetaAPI execution speed to reduce trade latency.

### Out of Scope

- [Adding new algorithmic trading strategies] — Focus is entirely on refactoring, stabilizing, and professionalizing the existing logic, not adding new market behaviors right now.

## Context

- The system relies on a FastAPI backend, a Python worker, and a Next.js frontend.
- Local development heavily depends on Redis `localhost:6379`.
- Codebase mapping (`.planning/codebase/`) surfaced multiple technical debt items and specific crash/latency issues reported by the user.

## Constraints

- **Architecture**: Must preserve the existing 3-tier decoupling (Frontend, API, Worker).
- **Timeouts**: MetaAPI operations require careful timeout tuning to separate real-time critical path execution from slower background reconciliation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full scale refactor | Codebase had accumulated redundant files and technical debt affecting reliability | — Pending |

---
*Last updated: 2026-03-19 after initialization*
