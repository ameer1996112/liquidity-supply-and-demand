# Roadmap: Refactoring & Professionalization

## Overview

A full-scale cleanup and professionalization of the institutional liquidity-based algorithmic trading system.

## Phases

- [ ] **Phase 1: Codebase Cleanup & DDD Unification** - Delete dead code and unify boundaries
- [ ] **Phase 2: Backend Stability & Bug Fixes** - Ruff warnings, MetaAPI, yfinance bugs
- [x] **Phase 3: Frontend Integrity & Latency** - ESLint, Vitest, CORS, latency

## Phase Details

### Phase 1: Codebase Cleanup & DDD Unification
**Goal**: Safely delete all dead code, unused scripts, and deprecated branches; deduplicate existing routines; strictly define Domain-Driven Design (DDD) boundaries across frontend, backend, and worker.
**Depends on**: Nothing
**Requirements**: REQ-01, REQ-02, REQ-03
**Success Criteria** (what must be TRUE):
  1. No unused files exist in the repository
  2. DDD layer structure is strictly enforced
**Plans**: TBD

Plans:

### Phase 2: Backend Stability & Bug Fixes
**Goal**: Attain zero `ruff` warnings, maintain 100% backend test passage, resolve MetaAPI background timeouts (5s), and fix `yfinance` HTTP 404 errors.
**Depends on**: Phase 1
**Requirements**: REQ-04, REQ-07, REQ-08
**Success Criteria** (what must be TRUE):
  1. `ruff check src/ config/ tests/` returns zero errors
  2. 11 pytest backend tests pass
  3. MetaAPI operations complete without 5s timeout exceptions
**Plans**: TBD

Plans:

### Phase 3: Frontend Integrity & Latency
**Goal**: Reach zero `eslint` warnings, fix the failing Vitest in `tradingMetrics.test.ts`, resolve production CORS policy errors, and implement latency optimizations for trade execution.
**Depends on**: Phase 2
**Requirements**: REQ-05, REQ-06, REQ-09
**Success Criteria** (what must be TRUE):
  1. `eslint` returns zero warnings/errors
  2. All frontend Vitest tests pass
  3. API responds with correct CORS headers to Next.js
**Plans**: TBD

Plans:

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Codebase Cleanup | 0/0 | Not started | - |
| 2. Backend Stability | 0/0 | Not started | - |
| 3. Frontend Integrity | 1/1 | Complete | Yes |
