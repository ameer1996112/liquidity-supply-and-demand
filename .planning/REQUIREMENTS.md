# Requirements: Trade Journal v2

**Defined:** 2026-03-21
**Core Value:** Every closed trade is visible, analyzable, and actionable directly from the journal.

## v1 Requirements (Complete)

### Journal Foundation
- ✓ **JOUR-01**: Trade table with sortable columns (date, symbol, side, status, account, zone, model, session, entry, exit, AI score, R:R, PnL)
- ✓ **JOUR-02**: Expandable row detail (technical setup, AI analysis, execution section, trade notes)
- ✓ **JOUR-03**: Calendar heatmap view (PnL by day)
- ✓ **JOUR-04**: Pattern insights panel (best/worst day, session, symbol, emotional trade detection)
- ✓ **JOUR-05**: CSV export of filtered signals
- ✓ **JOUR-06**: Search + status + mode filter bar

### Journal v1.1 (Complete)
- ✓ **JOUR-07**: Stats summary bar (total PnL, win rate, profit factor, avg R:R, expectancy)
- ✓ **JOUR-08**: Equity curve chart (cumulative PnL over closed trades)
- ✓ **JOUR-09**: Period filter (7D / 30D / 90D / All)
- ✓ **JOUR-10**: Duration column in trade table

## v2 Requirements (Active — this milestone)

### Per-Account Breakdown
- [ ] **ACCT-01**: Account-level performance summary (win rate, total PnL, trade count per account)
- [ ] **ACCT-02**: Account filter in journal (filter table + stats by specific account_name)
- [ ] **ACCT-03**: Account comparison table (side-by-side account stats)

### Symbol Breakdown
- [ ] **SYM-01**: Symbol performance table (PnL, win rate, trade count per symbol)
- [ ] **SYM-02**: Symbol filter quick-select (click symbol in table to filter)

### Drawdown Visualization
- [ ] **DD-01**: Max drawdown shown in stats bar (absolute + percentage)
- [ ] **DD-02**: Underwater / drawdown chart below equity curve (shows depth and recovery)

### Mobile Optimization
- [ ] **MOB-01**: Journal stats bar stacks to 2x3 grid on mobile (not 1x6)
- [ ] **MOB-02**: Trade table horizontally scrollable and usable on mobile
- [ ] **MOB-03**: Equity curve chart visible and readable on mobile

### Trade Notes Enhancement
- [ ] **NOTE-01**: Notes indicator visible in main table row (currently only shown in expanded row)
- [ ] **NOTE-02**: Bulk notes export included in CSV (currently missing from export)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Migrate notes to Supabase | DB schema change; risky for v2 |
| TradingView chart thumbnails | External API dependency |
| Backtesting replay | Separate feature, not journal |
| Multi-timeframe breakdown | Out of scope for this milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ACCT-01 | Phase 1 | Pending |
| ACCT-02 | Phase 1 | Pending |
| ACCT-03 | Phase 1 | Pending |
| SYM-01 | Phase 2 | Pending |
| SYM-02 | Phase 2 | Pending |
| DD-01 | Phase 3 | Pending |
| DD-02 | Phase 3 | Pending |
| MOB-01 | Phase 4 | Pending |
| MOB-02 | Phase 4 | Pending |
| MOB-03 | Phase 4 | Pending |
| NOTE-01 | Phase 5 | Pending |
| NOTE-02 | Phase 5 | Pending |

**Coverage:**
- v2 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after initial definition*
