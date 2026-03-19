# Phase 2: Core Component Library - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Restyle all base UI components (buttons, cards, tables, badges, inputs, skeleton loaders) to use design system tokens exclusively. No new functionality — visual consistency only. StatusBadge and SideBadge are already correct and untouched. Coverage: button.tsx, card.tsx, badge.tsx, table.tsx, skeleton.tsx, and form inputs across the codebase.

</domain>

<decisions>
## Implementation Decisions

### Button Styling
- Primary button gets var(--glow-amber) box-shadow on hover — premium gold glow effect
- Destructive variant uses --to-error/--to-accent-red token instead of shadcn 'destructive'
- Ghost button hover uses bg-[var(--to-surface-raised)] — matches dark surface hierarchy
- Button border-radius stays rounded-md (6px) — panel radius (12px) is for cards/panels only

### Card, Table & Skeleton
- Card default variant: glass-panel — frosted glass for elevated surfaces
- Card border: 1px solid var(--to-border) — existing token, no additional glow
- Table row hover: bg-[var(--to-surface-raised)] — subtle lift replacing muted/50
- Skeleton: gradient shimmer left-to-right (from --to-surface to --to-surface-raised and back) replacing animate-pulse solid

### Badge & Input Styling
- Badge base variants (default/secondary/outline) updated to use --to-surface-raised, --to-text-secondary tokens
- StatusBadge and SideBadge unchanged — already correctly use --to-* tokens
- Form inputs: bg-[var(--to-surface)] border-[var(--to-border)]
- Input focus ring: var(--glow-amber) — gold glow ring on focus consistent with primary accent

### Loading States & Coverage
- Skeleton loading applied to: Dashboard, Positions, Analytics, Risk, PropFirm (top 5 data pages)
- Skeleton shapes match layout exactly (card skeletons for card grids, row skeletons for tables)
- No global page spinner — per-section skeletons only
- Shimmer direction: left-to-right (standard fintech pattern)

### Claude's Discretion
- Specific Tailwind class updates within each component file
- Exact shimmer keyframe animation values
- Input component file selection (direct shadcn input or globals.css override)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StatusBadge` (shared/StatusBadge.tsx) — already uses --to-* tokens correctly, no changes needed
- `SideBadge` (shared/SideBadge.tsx) — already uses --to-long/--to-short correctly, no changes needed
- `PnLDisplay` (shared/PnLDisplay.tsx) — delegates to PnLText typography primitive, already correct
- `AnimatedNumber` (ui/AnimatedNumber.tsx) — exists, used in Phase 8 for number animations
- `skeleton.tsx` — exists, uses bg-accent animate-pulse (to be upgraded to shimmer)

### Established Patterns
- `cva` + `VariantProps` pattern used in button.tsx and badge.tsx for variant management
- `cn()` utility for conditional class merging — used consistently across all components
- `var(--to-*)` token references via inline Tailwind arbitrary values e.g. `bg-[var(--to-surface-raised)]`
- Glass panel: `.glass-panel` class defined in globals.css with backdrop-filter and border
- Token prefix: `--to-*` for TradeOps design system tokens
- Glow utilities: `--glow-amber`, `--glow-green`, `--glow-red`, `--glow-blue` defined in :root
- Section divider format: `/* ── Label ─────────────────────────── */`

### Integration Points
- `globals.css` — shimmer keyframe animation to be added here
- `button.tsx` — update variant classes in buttonVariants cva
- `card.tsx` — update base className to use glass-panel
- `badge.tsx` — update variant classes in badgeVariants cva
- `table.tsx` — update TableRow and TableHead classes
- `skeleton.tsx` — update to use shimmer gradient animation
- Form inputs: check if shadcn `input.tsx` exists or if inputs are styled via globals.css

</code_context>

<specifics>
## Specific Ideas

- Gold glow on primary button hover mirrors the existing glow-card pattern used elsewhere
- Shimmer animation should be defined as a @keyframes in globals.css and referenced in skeleton.tsx
- Card glass-panel wrapping keeps card.tsx generic — pages can override with to-panel via className prop for flat secondary panels

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
