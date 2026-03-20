---
phase: 02-core-component-library
plan: 01
subsystem: ui
tags: [react, tailwind, cva, design-tokens, shadcn, button, badge, skeleton]

# Dependency graph
requires:
  - phase: 01-design-system-foundation
    provides: "--to-* CSS tokens, .skeleton-shimmer, --glow-amber/red in globals.css"
provides:
  - Token-native button component with gold primary, glow hover, and amber focus ring
  - Token-native badge component with 5 variants, font-semibold, py-1 spacing
  - Shimmer skeleton primitive using .skeleton-shimmer gradient animation
affects:
  - 02-02, 02-03 (all other component library plans that compose these primitives)
  - All pages using Button, Badge, Skeleton (24+ import sites for Skeleton alone)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "cva variant strings reference CSS custom properties via bg-[var(--to-*)] Tailwind arbitrary value syntax"
    - "Glow effects applied via shadow-[var(--glow-amber)] on hover/focus instead of ring utilities"
    - "Shimmer animation centralised in globals.css .skeleton-shimmer class; components just apply the class"

key-files:
  created: []
  modified:
    - frontend/src/components/ui/button.tsx
    - frontend/src/components/ui/badge.tsx
    - frontend/src/components/ui/skeleton.tsx

key-decisions:
  - "Button primary uses text-[#080b10] (near-black) for maximum contrast against gold --to-accent-amber"
  - "Badge link variant removed — not in UI-SPEC contract; callers using variant='link' fall back to default"
  - "Skeleton drops animate-pulse entirely; shimmer gradient class already in globals.css at line 966, no new CSS needed"
  - "focus-visible:ring-ring/50 and aria-invalid:border-destructive removed from both button and badge bases — shadcn defaults conflict with dark terminal aesthetic"

patterns-established:
  - "bg-[var(--to-*)] arbitrary value pattern: all component color classes reference CSS tokens, never Tailwind semantic tokens"
  - "Glow pattern: hover:shadow-[var(--glow-amber)] for primary interactive elements, focus-visible:shadow-[var(--glow-amber)]/50 for keyboard focus"
  - "Destructive pattern: bg-[var(--to-error)]/15 background with text-[var(--to-error)] and border-[var(--to-error)]/30 for badge; full bg-[var(--to-error)] for button"

requirements-completed: [COMP-01, COMP-04, COMP-06]

# Metrics
duration: 8min
completed: 2026-03-20
---

# Phase 02 Plan 01: Core Primitive Restyling Summary

**button, badge, and skeleton restyled to --to-* design tokens with gold glow hover, shimmer animation, and zero shadcn color class references**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-20T09:20:00Z
- **Completed:** 2026-03-20T09:28:00Z
- **Tasks:** 3 of 3
- **Files modified:** 3

## Accomplishments

- Button cva variants fully token-native: gold primary (--to-accent-amber) with glow-amber hover shadow, --to-error destructive, surface-token ghost/secondary/outline, amber link text
- Badge cva variants fully token-native: 5 variants using surface/text/error tokens, font-semibold upgrade, py-1 vertical padding, link variant removed per UI-SPEC
- Skeleton shimmer replaces bg-accent animate-pulse: .skeleton-shimmer class provides left-to-right gradient sweep at 1.6s ease-in-out infinite across all 24+ import sites

## Task Commits

Each task was committed atomically:

1. **Task 1: Restyle button.tsx** - `b64e47c` (feat)
2. **Task 2: Restyle badge.tsx** - `b5e309f` (feat)
3. **Task 3: Update skeleton.tsx shimmer** - `876a67e` (feat)

## Files Created/Modified

- `frontend/src/components/ui/button.tsx` - 6 variants replaced with --to-* tokens; base stripped of ring/aria-invalid classes
- `frontend/src/components/ui/badge.tsx` - 5 variants replaced (link removed); py-0.5->py-1, font-medium->font-semibold
- `frontend/src/components/ui/skeleton.tsx` - Single className change: bg-accent animate-pulse -> skeleton-shimmer

## Decisions Made

- Badge `link` variant removed — UI-SPEC does not define a link badge; existing callers (none found) would fall through to default, which is correct behavior
- Button `text-[#080b10]` chosen for primary button text (near-black) to meet WCAG contrast against #f0b90b gold background
- Shimmer CSS already existed in globals.css from Phase 01; skeleton.tsx needed only a class name swap, no new CSS required

## Deviations from Plan

None - plan executed exactly as written. All three files updated per the exact class strings specified in the PLAN.md action sections.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- button.tsx, badge.tsx, skeleton.tsx are token-native and ready to be composed into higher-level components (cards, tables, inputs) in Plans 02-02 and 02-03
- All 24+ skeleton import sites automatically inherit shimmer animation — no per-callsite changes needed
- No blockers

## Self-Check: PASSED

- FOUND: frontend/src/components/ui/button.tsx
- FOUND: frontend/src/components/ui/badge.tsx
- FOUND: frontend/src/components/ui/skeleton.tsx
- FOUND: .planning/phases/02-core-component-library/02-01-SUMMARY.md
- FOUND commit: b64e47c (button.tsx)
- FOUND commit: b5e309f (badge.tsx)
- FOUND commit: 876a67e (skeleton.tsx)

---
*Phase: 02-core-component-library*
*Completed: 2026-03-20*
