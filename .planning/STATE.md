# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Each connected MT5 account automatically shows its prop firm challenge status in real-time — trader sees exactly where they stand without leaving the accounts page
**Current focus:** Phase 1 — Data Foundation and Bug Fixes

## Current Position

Phase: 1 of 3 (Data Foundation and Bug Fixes)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-03-18 — Roadmap created

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Auto-detect firm from MetaAPI server name string — no user input for firm identity
- Internal rules DB (prop_firm_rules) instead of firm APIs — rules are stable, firms don't expose public APIs
- Embed metrics in account card — avoids page navigation to see challenge status
- FTMO-only at launch — same DB schema works for all firms; others deferred to v2

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 1 (reset timezone):** FTMO's exact reset timezone assumed to be New York midnight — must verify against current FTMO FAQ before seeding `reset_tz` in rules DB; web access was unavailable during research
- **Phase 1 (drawdown denominator):** PropFirmTracker currently uses trailing HWM for all phases; the initial-balance branch for Phase 1/2 does not yet exist — must be implemented
- **Unresolved UX decision:** Whether the one-time phase selector appears inline in the card or in a modal — decision needed before Phase 2 implementation begins

## Session Continuity

Last session: 2026-03-18
Stopped at: Roadmap created, STATE.md initialized — ready to begin /gsd:plan-phase 1
Resume file: None
