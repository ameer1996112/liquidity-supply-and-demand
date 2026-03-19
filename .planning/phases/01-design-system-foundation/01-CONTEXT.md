# Phase 1: Design System Foundation - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Consolidate and formalize the design system in `globals.css` — fill gaps in typography scale, spacing scale, and effect tokens. Deliver a complete, documented token set as CSS custom properties that all subsequent phases can reference. No visual component changes in this phase — tokens only.

</domain>

<decisions>
## Implementation Decisions

### Typography Scale
- Define `--text-xs` through `--text-4xl` as CSS custom properties in globals.css `:root`
- All typography tokens live alongside existing `--to-*` tokens in globals.css (no separate file)
- Add semantic type role aliases: `--to-label`, `--to-body`, `--to-heading`, `--to-mono` as font-size shorthand tokens
- Add font weight tokens: `--to-weight-normal`, `--to-weight-medium`, `--to-weight-semibold`, `--to-weight-bold`

### Spacing Scale
- Define `--to-space-1` through `--to-space-16` tokens mapping to rem values (1=0.25rem, 2=0.5rem, etc.)
- Add semantic spacing aliases: `--to-card-padding`, `--to-section-gap`, `--to-row-gap`
- Extend radius with semantic aliases: `--to-radius-card`, `--to-radius-badge`, `--to-radius-button`
- Add comment blocks grouping tokens by category in globals.css

### Glass Effects & Token Completeness
- Extend glass variants: keep `glass-panel`, add `glass-panel-subtle` (lighter blur) and `glass-panel-strong` (heavier blur)
- Add missing semantic color tokens: `--to-success`, `--to-info`, `--to-error` alongside existing `--to-warning`
- Define reusable gradient tokens: `--gradient-surface`, `--gradient-card`, `--gradient-accent`
- Write `TOKEN-AUDIT.md` in phase dir listing all existing tokens and gaps filled

### Claude's Discretion
- Exact rem values for spacing scale steps
- Line-height and letter-spacing values for typography tokens
- Blur/opacity levels for glass-panel-subtle vs glass-panel-strong
- Order and grouping of comment sections in globals.css

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `globals.css` (896 lines) — comprehensive existing token system with `--to-*` prefix
- `glass-panel` CSS class with backdrop-filter, shimmer ::before pseudo-element
- `to-panel`, `tv-card` panel classes already defined
- `glow-green/red/amber/purple/blue` utility classes
- `text-glow-*` text shadow utilities
- Font stack: Inter (sans) + JetBrains Mono (mono) — already defined in `:root`
- `cn()` utility at `@/lib/utils` for conditional class merging

### Established Patterns
- Token naming: `--to-{category}-{variant}` (e.g., `--to-text-primary`, `--to-accent-amber`)
- Tailwind 4.x `@theme inline` block maps CSS vars to Tailwind color utilities
- Design tokens are CSS custom properties on `:root`, consumed via `var(--to-*)`
- Semantic trading colors: `--to-long` (green), `--to-short` (red), `--to-neutral` (gray)
- Glow shadows defined as CSS custom properties (`--glow-green`, etc.), applied via utility class

### Integration Points
- All new tokens added to `:root` in `globals.css`
- New Tailwind color mappings added to `@theme inline` block
- `globals.css` is imported at app root (`frontend/src/app/layout.tsx`)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for token values within the established `--to-*` naming convention.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
