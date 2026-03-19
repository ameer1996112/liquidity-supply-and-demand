---
phase: 01-design-system-foundation
plan: 02
subsystem: ui
tags: [css, design-tokens, spacing, radius, glass-panel, gradients]

# Dependency graph
requires: [01-01]
provides:
  - Spacing scale tokens (--to-space-1 through --to-space-16) on :root
  - Semantic spacing aliases (--to-card-padding, --to-section-gap, --to-row-gap) on :root
  - Radius aliases (--to-radius-card, --to-radius-badge, --to-radius-button) on :root
  - Gradient tokens (--gradient-surface, --gradient-card, --gradient-accent) on :root
  - .glass-panel-subtle CSS class with blur(6px) saturate(120%) and -webkit- prefix
  - .glass-panel-strong CSS class with blur(20px) saturate(180%) and -webkit- prefix
  - TOKEN-AUDIT.md — authoritative token inventory + hardcoded hex tech debt map
affects: [all UI phases 2-6, all components using spacing or glass panels]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Spacing scale follows 4px base: --to-space-N maps to N*4px as rem values"
    - "Spacing aliases reference scale steps: --to-card-padding: var(--to-space-4)"
    - "Glass variants use --to-radius-card token (not hardcoded 0.75rem)"
    - "Both backdrop-filter and -webkit-backdrop-filter required for every glass class (Safari)"

key-files:
  created:
    - .planning/phases/01-design-system-foundation/TOKEN-AUDIT.md
  modified:
    - frontend/src/app/globals.css

key-decisions:
  - "No @theme inline entries for spacing/radius tokens — components consume via var() directly or Tailwind arbitrary values like p-[var(--to-card-padding)]"
  - "Glass variants use --to-radius-card token reference, not the hardcoded 0.75rem, ensuring future radius changes propagate automatically"
  - "TOKEN-AUDIT.md documents TradingView color exceptions (#26a69a, #ef5350) as potentially intentional chart compatibility values, not accidental drift"

patterns-established:
  - "Glass variant hierarchy: glass-panel-subtle (6px blur) < glass-panel (12px) < glass-panel-strong (20px blur)"
  - "Spacing alias naming: --to-{role}-{property} (e.g. --to-card-padding, --to-section-gap)"

requirements-completed: [DSYS-03, DSYS-04]

# Metrics
duration: 3min
completed: 2026-03-19
---

# Phase 1 Plan 02: Design System Foundation — Spacing, Radius, Glass & Gradients Summary

**10-token 4px spacing scale, 3 radius aliases, 2 glass panel variants, 3 gradient tokens added to globals.css with TOKEN-AUDIT.md documenting full Phase 1 token inventory and 83-component hardcoded hex tech debt**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T18:33:02Z
- **Completed:** 2026-03-19T18:35:54Z
- **Tasks:** 2
- **Files modified:** 1
- **Files created:** 1

## Accomplishments

- Added 10 spacing scale tokens (`--to-space-1` through `--to-space-16`) on `:root`, each a 4px-base rem value
- Added 3 semantic spacing aliases (`--to-card-padding`, `--to-section-gap`, `--to-row-gap`) referencing scale steps via `var()`
- Added 3 radius aliases (`--to-radius-card: 0.75rem`, `--to-radius-badge: 0.375rem`, `--to-radius-button: 0.5rem`) on `:root`
- Added 3 gradient tokens (`--gradient-surface`, `--gradient-card`, `--gradient-accent`) on `:root`
- Added `.glass-panel-subtle` with `blur(6px) saturate(120%)`, `border-radius: var(--to-radius-card)`, and `-webkit-backdrop-filter`
- Added `.glass-panel-strong` with `blur(20px) saturate(180%)`, `border-radius: var(--to-radius-card)`, and `-webkit-backdrop-filter`
- Created `TOKEN-AUDIT.md` with 4 sections: existing tokens, Plan 01-01 additions, Plan 01-02 additions, hardcoded hex tech debt map
- Build verified: `npx next build` exits 0 with no CSS compilation errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add spacing scale, radius aliases, and gradient tokens to :root (DSYS-03, DSYS-04)** - `cc0f763` (feat)
2. **Task 2: Add glass-panel-subtle and glass-panel-strong CSS classes, then write TOKEN-AUDIT.md (DSYS-04)** - `4f90e42` (feat)

## Files Created/Modified

- `frontend/src/app/globals.css` - Added 27 new CSS custom property definitions and 2 new glass panel classes
- `.planning/phases/01-design-system-foundation/TOKEN-AUDIT.md` - Created authoritative token inventory with tech debt map

## Decisions Made

- No `@theme inline` entries for spacing or radius tokens — Phase 1 components consume these via `var(--to-card-padding)` directly or Tailwind arbitrary values. Phase 2 can add `@theme inline` spacing mappings if Tailwind utility classes are needed.
- Glass variants reference `--to-radius-card` token rather than hardcoding `0.75rem` — future radius changes propagate automatically to all glass panels.
- TOKEN-AUDIT.md flags `#26a69a` (TradingView teal-green) and `#ef5350` (TradingView pure-red) as potentially intentional chart compatibility values. Phase 2 must investigate before replacing with `--to-long`/`--to-short`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All DSYS-03 and DSYS-04 tokens are live and build-verified
- TOKEN-AUDIT.md is the locked deliverable proving Phase 1 complete
- Hardcoded hex tech debt is mapped and ready for Phases 2-6 to address
- Glass panel hierarchy (subtle / base / strong) is established and ready for component use
- No blockers for Phase 2

---

## Self-Check

Checking created files and commits exist...

- `frontend/src/app/globals.css` - FOUND (modified, contains --to-space-4, --to-radius-card, .glass-panel-subtle, .glass-panel-strong)
- `.planning/phases/01-design-system-foundation/TOKEN-AUDIT.md` - FOUND
- Commit `cc0f763` - FOUND (feat(01-02): spacing scale, radius aliases, gradient tokens)
- Commit `4f90e42` - FOUND (feat(01-02): glass-panel variants + TOKEN-AUDIT.md)

## Self-Check: PASSED

---
*Phase: 01-design-system-foundation*
*Completed: 2026-03-19*
