# Roadmap: Trade Journal v2

## Overview

This milestone extends the Trade Journal from a solid foundation (stats bar, equity curve, period filter) to a full-featured analysis tool. Five focused phases: per-account breakdown, symbol performance table, drawdown visualization, mobile optimization, and trade notes polish.

## Phases

- [ ] **Phase 1: Per-Account Breakdown** - Account filter + per-account stats + comparison table
- [ ] **Phase 2: Symbol Performance Table** - Symbol-level PnL/WR table + click-to-filter
- [ ] **Phase 3: Drawdown Visualization** - Max drawdown in stats bar + underwater chart
- [ ] **Phase 4: Mobile Optimization** - Responsive stats grid, scrollable table, mobile chart
- [ ] **Phase 5: Trade Notes Polish** - Notes indicator in row, notes in CSV export

## Phase Details

### Phase 1: Per-Account Breakdown
**Goal**: Filter the entire journal by account and see per-account performance side-by-side
**Depends on**: Nothing (first phase)
**Requirements**: ACCT-01, ACCT-02, ACCT-03
**Success Criteria** (what must be TRUE):
  1. Account dropdown filter appears in JournalFilters — selecting it narrows stats bar + equity curve + table to that account
  2. New `AccountBreakdown` component shows a table of all accounts with PnL, win rate, trade count
  3. `tsc --noEmit` returns zero errors
**Plans**: 3 plans

Plans:
- [ ] 01-01: Add account filter state + dropdown to JournalFilters
- [ ] 01-02: Wire account filter into useJournalSignals + page filtered array
- [ ] 01-03: Build AccountBreakdown component (table of account stats)

### Phase 2: Symbol Performance Table
**Goal**: See which symbols are performing best/worst at a glance
**Depends on**: Phase 1
**Requirements**: SYM-01, SYM-02
**Success Criteria** (what must be TRUE):
  1. Symbol performance table shows symbol, trade count, win rate, total PnL, avg PnL — sortable
  2. Clicking a symbol in the table OR in the trade table applies a symbol search filter
  3. `tsc --noEmit` returns zero errors
**Plans**: 2 plans

Plans:
- [ ] 02-01: Build SymbolBreakdown component (stats table computed from filtered signals)
- [ ] 02-02: Wire symbol click → search filter in journal page

### Phase 3: Drawdown Visualization
**Goal**: Surface risk profile visually — how deep did we go and how long did it take to recover?
**Depends on**: Phase 1
**Requirements**: DD-01, DD-02
**Success Criteria** (what must be TRUE):
  1. Stats bar shows max drawdown cell (absolute $ + %)
  2. Underwater chart shows depth of each drawdown period below equity peak
  3. `tsc --noEmit` returns zero errors
**Plans**: 2 plans

Plans:
- [ ] 03-01: Add max drawdown metric to JournalStats
- [ ] 03-02: Build DrawdownChart component (area chart showing -ve from peak)

### Phase 4: Mobile Optimization
**Goal**: Journal usable on phone without horizontal overflow or tiny unreadable text
**Depends on**: Phase 1
**Requirements**: MOB-01, MOB-02, MOB-03
**Success Criteria** (what must be TRUE):
  1. Stats bar wraps to 2×3 grid on screens < 640px
  2. Trade table is horizontally scrollable with sticky date + symbol columns
  3. Equity curve chart fits and is readable at 375px width
**Plans**: 2 plans

Plans:
- [ ] 04-01: Fix stats bar, equity curve, and filter bar for mobile
- [ ] 04-02: Add sticky first columns + horizontal scroll wrapper to trade table

### Phase 5: Trade Notes Polish
**Goal**: Notes are discoverable in the table and included in data exports
**Depends on**: Phase 4
**Requirements**: NOTE-01, NOTE-02
**Success Criteria** (what must be TRUE):
  1. Trade rows with notes show a visible ink/pen icon in the main row (not just expanded)
  2. CSV export includes notes column populated from localStorage
  3. `tsc --noEmit` returns zero errors
**Plans**: 2 plans

Plans:
- [ ] 05-01: Add notes indicator icon to main ExpandableTradeRow cell (always visible)
- [ ] 05-02: Pull localStorage notes into CSV export function
