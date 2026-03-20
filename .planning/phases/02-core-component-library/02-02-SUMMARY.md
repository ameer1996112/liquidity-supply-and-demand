---
phase: 02-core-component-library
plan: "02"
subsystem: ui
tags: [react, tailwind, shadcn, design-tokens, glass-panel, css-variables]

# Dependency graph
requires:
  - phase: 01-design-system-foundation
    provides: --to-* CSS token system, glass-panel class, glow-amber/glow-red utilities
provides:
  - Glass-panel frosted-glass Card component (7 import sites auto-upgraded)
  - Token-correct Table sub-components with uppercase semibold headers
  - New Input component with amber focus glow and red error glow
affects: [all pages using Card, all pages using Table, future form pages using Input]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "glass-panel class applied to Card root — callers override with className='to-panel' when flat panel needed"
    - "Tailwind arbitrary value syntax var(--token) for CSS custom properties in className strings"
    - "text-[length:var(--text-xs)] type hint pattern for font-size CSS custom properties in Tailwind"
    - "aria-invalid attribute-based error state styling (not className-driven)"

key-files:
  created:
    - frontend/src/components/ui/input.tsx
  modified:
    - frontend/src/components/ui/card.tsx
    - frontend/src/components/ui/table.tsx

key-decisions:
  - "Card uses glass-panel class directly (not a variant prop) — flat override via className='to-panel' per CONTEXT.md pattern"
  - "TableHeader border uses [&_tr]:border-[var(--to-border)] child selector approach (not direct border on thead)"
  - "Input height is h-9 (36px) to align with button default height in form rows"
  - "focus-visible used for keyboard-only focus ring (not focus) to avoid ring showing on mouse click"

patterns-established:
  - "Pattern: glass-panel class replaces bg-card/rounded-xl/border/shadow-sm on Card — single class carries all surface styling"
  - "Pattern: shadcn shadowed tokens (text-foreground, text-muted-foreground, bg-muted) fully replaced by --to-* token direct references"
  - "Pattern: Input error state uses aria-invalid attribute to align with HTML5 form validation semantics"

requirements-completed: [COMP-02, COMP-03, COMP-05]

# Metrics
duration: 15min
completed: 2026-03-20
---

# Phase 02 Plan 02: Core Component Token Restyling Summary

**Glass-panel Card, token-correct Table sub-components, and new dark-themed Input with amber/red glow states — all shadcn muted/foreground defaults replaced by --to-* CSS tokens**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-20T09:42:50Z
- **Completed:** 2026-03-20T09:58:10Z
- **Tasks:** 3
- **Files modified:** 3 (2 updated, 1 created)

## Accomplishments

- Restyled Card component to use `glass-panel` class — frosted glass effect now applied automatically across all 7 Card import sites (OptimizerPanel, CapitalAllocator, CopyConfigurator, PropFirmWidget, BacktestPerformanceTab, backtest/page, execution-quality/page)
- Replaced all 5 shadcn default color classes in table.tsx (text-foreground, text-muted-foreground, hover:bg-muted/50, data-[state=selected]:bg-muted, bg-muted/50) with exact --to-* token references; TableHead now uppercase semibold with wider tracking
- Created new input.tsx from scratch as a proper shadcn component with amber focus glow and red error glow states for form validation feedback

## Task Commits

Each task was committed atomically:

1. **Task 1: Restyle card.tsx to glass-panel + --to-* tokens (COMP-02)** - `8b470a4` (feat)
2. **Task 2: Restyle table.tsx sub-components to --to-* tokens (COMP-03)** - `5a6a0c2` (feat)
3. **Task 3: Create input.tsx with dark-theme --to-* token styling (COMP-05)** - `d7ce77b` (feat)

## Files Created/Modified

- `frontend/src/components/ui/card.tsx` - Card now uses `glass-panel` class; CardTitle has `--to-text-primary`; CardDescription has `--to-text-secondary`
- `frontend/src/components/ui/table.tsx` - 5 sub-components updated: TableHeader, TableHead, TableRow, TableCell, TableFooter, TableCaption all use `--to-*` tokens
- `frontend/src/components/ui/input.tsx` - New file: dark-theme input with amber focus glow (`--glow-amber`), red error state (`--glow-red`, `aria-invalid`), h-9 height

## Decisions Made

- Card uses `glass-panel` class directly rather than a `variant` prop — callers needing a flat panel pass `className="to-panel"` to override, per the established CONTEXT.md pattern. No cva added.
- `text-[length:var(--text-xs)]` type hint used in TableHead to ensure the `--text-xs` CSS custom property is interpreted as `font-size`, not `color`, by Tailwind's arbitrary value parser.
- Input uses `focus-visible` (not `focus`) for the amber glow ring so it only appears on keyboard navigation, not mouse clicks.
- TableRow border uses `border-[var(--to-border-subtle)]` (subtle) while TableHeader/TableFooter use `border-[var(--to-border)]` (standard) — intentional contrast hierarchy from UI-SPEC.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all three tasks applied cleanly. Build passed without errors after all changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Card, Table, and Input components are now token-correct and ready for use in Phase 03 page rebuilds
- All 7 Card import sites will automatically render frosted glass — no per-site changes needed
- Input component is importable from `@/components/ui/input` for any form fields in upcoming pages
- No blockers for Phase 02 Plan 03

---
*Phase: 02-core-component-library*
*Completed: 2026-03-20*
