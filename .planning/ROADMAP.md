# Roadmap — Prop Firm Page Overhaul

## Overview

**3 phases** | **12 requirements** | All v1 requirements covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Data Accuracy & Rules | Show only relevant metrics + firm rules table | DATA-01, DATA-02, DATA-03, RULES-01, RULES-02, RULES-03 | 6 |
| 2 | Performance | Instant account switching | PERF-01, PERF-02, PERF-03 | 3 |
| 3 | Design Polish | Richer visuals and better hierarchy | UI-01, UI-02, UI-03 | 3 |

---

## Phase 1: Data Accuracy & Rules Display

**Goal**: Only show metrics that apply to the selected firm. Add a rules summary section.

**Requirements**: DATA-01, DATA-02, DATA-03, RULES-01, RULES-02, RULES-03

**Success Criteria**:
1. ACG-DEMO does NOT show Consistency Rule gauge
2. Firms without profit target do NOT show profit target gauge  
3. A "Challenge Rules" section shows applicable rules with limits
4. Rules marked N/A are either hidden or clearly labeled
5. ChallengeMetrics component accepts optional flags for which gauges to show
6. Build passes with zero TypeScript errors

## Phase 2: Performance Optimization

**Goal**: Account switching feels instant — no blank screen, no multi-second wait.

**Requirements**: PERF-01, PERF-02, PERF-03

**Success Criteria**:
1. All account metrics prefetched on page load
2. Switching accounts shows cached data immediately (stale-while-revalidate)
3. Loading indicator shown while fresh data loads (no blank state)

## Phase 3: Design Polish

**Goal**: Elevate visual quality of the Prop Firm page.

**Requirements**: UI-01, UI-02, UI-03

**Success Criteria**:
1. Stat cards in Account Overview have larger values, trend arrows, and colored backgrounds
2. Primary metrics (balance, equity, P&L) visually distinct from secondary metrics
3. Consistent spacing and divider lines across all page sections
