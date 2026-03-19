# ROADMAP

## Milestone v1.0: Refactoring & Professionalization

### 1. Codebase Cleanup & DDD Unification
- **Goal**: Safely delete all dead code, unused scripts, and deprecated branches; deduplicate existing routines; strictly define Domain-Driven Design (DDD) boundaries across frontend, backend, and worker.
- **Depends on**: None

### 2. Backend Stability & Bug Fixes
- **Goal**: Attain zero `ruff` warnings, maintain 100% backend test passage, resolve MetaAPI background timeouts (5s), and fix `yfinance` HTTP 404 errors.
- **Depends on**: 1

### 3. Frontend Integrity & Latency Optimization
- **Goal**: Reach zero `eslint` warnings, fix the failing Vitest in `tradingMetrics.test.ts`, resolve production CORS policy errors, and implement latency optimizations for trade execution.
- **Depends on**: 2
