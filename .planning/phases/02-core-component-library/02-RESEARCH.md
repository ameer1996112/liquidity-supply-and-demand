# Phase 2: Core Component Library - Research

**Researched:** 2026-03-20
**Domain:** shadcn/ui component restyling with CSS custom property tokens (Tailwind 4.x + cva)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Button Styling**
- Primary button gets var(--glow-amber) box-shadow on hover — premium gold glow effect
- Destructive variant uses --to-error/--to-accent-red token instead of shadcn 'destructive'
- Ghost button hover uses bg-[var(--to-surface-raised)] — matches dark surface hierarchy
- Button border-radius stays rounded-md (6px) — panel radius (12px) is for cards/panels only

**Card, Table & Skeleton**
- Card default variant: glass-panel — frosted glass for elevated surfaces
- Card border: 1px solid var(--to-border) — existing token, no additional glow
- Table row hover: bg-[var(--to-surface-raised)] — subtle lift replacing muted/50
- Skeleton: gradient shimmer left-to-right (from --to-surface to --to-surface-raised and back) replacing animate-pulse solid

**Badge & Input Styling**
- Badge base variants (default/secondary/outline) updated to use --to-surface-raised, --to-text-secondary tokens
- StatusBadge and SideBadge unchanged — already correctly use --to-* tokens
- Form inputs: bg-[var(--to-surface)] border-[var(--to-border)]
- Input focus ring: var(--glow-amber) — gold glow ring on focus consistent with primary accent

**Loading States & Coverage**
- Skeleton loading applied to: Dashboard, Positions, Analytics, Risk, PropFirm (top 5 data pages)
- Skeleton shapes match layout exactly (card skeletons for card grids, row skeletons for tables)
- No global page spinner — per-section skeletons only
- Shimmer direction: left-to-right (standard fintech pattern)

### Claude's Discretion
- Specific Tailwind class updates within each component file
- Exact shimmer keyframe animation values
- Input component file selection (direct shadcn input or globals.css override)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COMP-01 | Button component has consistent styling across all variants (primary, secondary, ghost, destructive) using design system tokens | buttonVariants cva strings fully mapped; exact class replacements documented per variant |
| COMP-02 | Card/Panel components use consistent glass-panel or to-panel styling with proper token usage | glass-panel class verified in globals.css lines 290-317; Card sub-component diff table provided |
| COMP-03 | Table component has consistent header, row, cell styling with hover states and dense/comfortable modes | All 6 TableXxx sub-components audited; exact class replacements identified |
| COMP-04 | Badge component has consistent styling for status indicators (live/paper, long/short, trigger types) | badgeVariants cva strings audited; StatusBadge/SideBadge confirmed untouched |
| COMP-05 | Form inputs (text, select, checkbox, toggle) have consistent dark-theme styling | input.tsx confirmed MISSING — must be created; token contract from UI-SPEC documented |
| COMP-06 | Loading states use consistent skeleton/shimmer patterns across all pages | skeleton-shimmer keyframe confirmed at globals.css:958-974; 20 Skeleton importers mapped; 5 target pages identified |
</phase_requirements>

---

## Summary

Phase 2 is a pure restyling pass on 5 existing shadcn/ui component files plus creation of one new file (input.tsx). No new functionality, no API changes, no backend work. Every token needed already exists in globals.css :root under the `--to-*` prefix. The skeleton-shimmer keyframe and .skeleton-shimmer CSS class are already defined in globals.css lines 957-975 — skeleton.tsx just needs its class string updated, no CSS additions required.

The most impactful file is card.tsx: replacing `bg-card text-card-foreground ... rounded-xl border ... shadow-sm` with `glass-panel` cascades visual change to every page that imports Card (7 confirmed import sites). The glass-panel class carries its own border, border-radius, and backdrop-filter, so the removal of those Tailwind classes from Card is correct and intentional. Secondary/flat card usage can be restored caller-side via `className="to-panel"`.

The input.tsx gap is the only truly new file. It must be created as a proper shadcn component (not a globals.css override) to participate in the cva/cn() pattern used everywhere else and to be importable from `@/components/ui/input`.

**Primary recommendation:** Work through files in dependency order — globals.css (no changes needed), skeleton.tsx, badge.tsx, button.tsx, card.tsx, table.tsx, then create input.tsx. Pages get skeleton components added last, after the Skeleton primitive itself is correct.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| class-variance-authority (cva) | already installed | Variant string management for button.tsx, badge.tsx | Existing pattern in codebase; provides type-safe variant props |
| shadcn/ui | already installed | Component primitives | Project decision — no library swap |
| Tailwind CSS | 4.x | Utility classes + arbitrary value syntax `bg-[var(--to-*)]` | Existing stack |
| @radix-ui/react-slot | already installed | asChild pattern in Button and Badge | Required by existing shadcn components |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | already installed | Icons inside buttons | Button icon sizes already handled by size variants |
| tw-animate-css | already installed (globals.css line 2) | CSS animation utilities | Already imported; skeleton-shimmer is custom @keyframes, not from this library |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Creating input.tsx as component file | Adding input selectors to globals.css | globals.css approach loses importability and cva composability — component file is correct |
| glass-panel class on Card | Inline arbitrary values in Card className | Class approach is maintainable and consistent; arbitrary values would duplicate glass logic |

**No new installations required.** All dependencies are already present.

---

## Architecture Patterns

### Recommended Project Structure

No structural changes. All files stay in their existing locations:

```
frontend/src/
├── app/globals.css               # skeleton-shimmer already defined (line 957) — NO CHANGES
├── components/ui/
│   ├── button.tsx                # update buttonVariants cva strings
│   ├── card.tsx                  # update Card className + CardTitle/CardDescription text tokens
│   ├── badge.tsx                 # update badgeVariants cva strings
│   ├── table.tsx                 # update TableHeader/Head/Row/Footer/Cell/Caption classes
│   ├── skeleton.tsx              # swap bg-accent animate-pulse → skeleton-shimmer rounded-md
│   └── input.tsx                 # CREATE NEW — shadcn Input component with --to-* tokens
└── app/
    ├── page.tsx (Dashboard)      # add skeleton wrappers to data sections
    ├── positions/page.tsx        # add row skeleton to table
    ├── analytics/page.tsx        # add chart + stat card skeletons
    ├── risk/page.tsx             # add metric skeleton
    └── prop-firm/page.tsx        # add progress bar + stat card skeletons
```

### Pattern 1: cva variant string replacement

**What:** Replace shadcn default color tokens (bg-primary, bg-destructive, text-muted-foreground, etc.) with --to-* arbitrary values inside existing cva() calls. No structural change to the component.

**When to use:** For button.tsx and badge.tsx where variant management is already cva-based.

**Example (button.tsx default variant):**
```typescript
// Before (shadcn default):
default: "bg-primary text-primary-foreground hover:bg-primary/90",

// After (--to-* tokens):
default: "bg-[var(--to-accent-amber)] text-[#080b10] hover:shadow-[var(--glow-amber)] focus-visible:shadow-[var(--glow-amber)]/50",
```

### Pattern 2: Direct className replacement on non-cva components

**What:** For Card and Table sub-components, replace the className string directly since they use plain function components, not cva.

**When to use:** card.tsx, table.tsx — no cva in these files.

**Example (card.tsx Card component):**
```typescript
// Before:
"bg-card text-card-foreground flex flex-col gap-6 rounded-xl border py-6 shadow-sm"

// After:
"glass-panel flex flex-col gap-6 py-6"
```

Note: `rounded-xl`, `border`, and `shadow-sm` are REMOVED because `glass-panel` provides `border-radius: 0.75rem`, `border: 1px solid var(--to-border)`, and no shadow by design.

### Pattern 3: New input.tsx as shadcn component

**What:** Create input.tsx following the exact shadcn "new-york" style pattern used by other ui/ components. Single function component, no cva (single variant), accepts React.ComponentProps<"input">.

**When to use:** input.tsx creation only.

**Example structure:**
```typescript
import * as React from "react"
import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-sm text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] transition-all outline-none",
        "focus-visible:border-[var(--to-accent-amber)] focus-visible:shadow-[var(--glow-amber)]/40",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        "aria-invalid:border-[var(--to-error)] aria-invalid:shadow-[var(--glow-red)]/30",
        className
      )}
      {...props}
    />
  )
}

export { Input }
```

### Anti-Patterns to Avoid

- **Keeping `rounded-xl` on Card after adding glass-panel:** glass-panel hardcodes `border-radius: 0.75rem` (12px). Tailwind `rounded-xl` = 12px so they match, but having both is redundant and the Tailwind one will add specificity noise. Remove it.
- **Adding a `variant` prop to Card:** The UI-SPEC is explicit — callers override with `className="to-panel"` for flat panels. Do not add a shadcn-style variant cva to card.tsx in this phase.
- **Modifying StatusBadge or SideBadge:** These are in `components/shared/`, not `components/ui/`. They already use --to-* tokens correctly. Touching them is out of scope.
- **Adding skeleton wrappers before skeleton.tsx is updated:** The shimmer class only exists in globals.css. If Skeleton is still emitting `bg-accent animate-pulse`, page-level skeleton wrappers will look wrong. Update the primitive first.
- **Using font-medium instead of font-semibold for badge text:** The UI-SPEC specifies semibold (600). Current badge.tsx base uses `font-medium` (500). This must change to `font-semibold` to match the typography contract. The base class string, not variant strings, must be updated.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Shimmer animation | Custom @keyframes in component | .skeleton-shimmer class from globals.css | Already defined at globals.css:966-975 with correct gradient and timing |
| Glass panel styling | Inline backdrop-filter/gradient in JSX | .glass-panel class from globals.css | Already defined at globals.css:290-317 with ::before shimmer layer |
| Variant management | if/else or ternary class strings | cva() already in button.tsx and badge.tsx | Type-safe, already established pattern |
| Token values | Hardcoded hex strings in className | var(--to-*) references | Tokens are in :root; hardcoded hex bypasses the design system |

**Key insight:** The entire CSS infrastructure for this phase was built in Phase 1. The work is wiring component class strings to already-existing tokens and classes — not building new CSS.

---

## Common Pitfalls

### Pitfall 1: glass-panel overflow:hidden clips content
**What goes wrong:** glass-panel sets `overflow: hidden` (globals.css:301). Dropdown menus, tooltips, or absolutely-positioned children inside a Card will be clipped.
**Why it happens:** Overflow hidden is needed for the ::before pseudo-element shimmer layer to respect border-radius.
**How to avoid:** Callers that need overflow visible should use `className="to-panel"` instead of the default glass-panel Card. Do not remove overflow:hidden from glass-panel itself.
**Warning signs:** Popovers or dropdowns anchored inside a Card disappear at the card boundary.

### Pitfall 2: focus-visible vs focus ring class conflict
**What goes wrong:** The existing button.tsx base string has `focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]`. After restyling, these shadcn ring classes may conflict with the --glow-amber box-shadow approach.
**Why it happens:** Tailwind's `ring-*` utilities generate `box-shadow` with a ring offset; adding a second box-shadow via variant class can cause one to override the other depending on specificity.
**How to avoid:** Remove `focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]` from the base class string and replace with `focus-visible:shadow-[var(--glow-amber)]/50 focus-visible:outline-none` in each variant.
**Warning signs:** Focus ring appears in gold (correct) on some variants but shows the default blue ring on others.

### Pitfall 3: Badge base class has font-medium, spec requires font-semibold
**What goes wrong:** Current badge.tsx base: `... font-medium ...`. UI-SPEC (Typography section, line 70): "Button and badge text use weight 600 (Semibold)."
**Why it happens:** shadcn default uses medium for badges; the design system upgrade requires semibold.
**How to avoid:** Change `font-medium` to `font-semibold` in the badgeVariants base string. Also change `py-0.5` to `py-1` per UI-SPEC spacing contract.
**Warning signs:** Badge text appears slightly lighter than expected; audit reports font weight mismatch.

### Pitfall 4: Card importers may have explicit bg/border overrides that now fight glass-panel
**What goes wrong:** Some of the 7 Card import sites may pass `className="bg-card border-..."` to override the base Card. After the base switches to glass-panel, those manual overrides may produce unexpected layering.
**Why it happens:** Callers wrote defensively against the old shadcn defaults.
**How to avoid:** After updating card.tsx, visually check all 7 import sites: execution-quality/page.tsx, backtest/page.tsx, BacktestPerformanceTab.tsx, PropFirmWidget.tsx, CopyConfigurator.tsx, CapitalAllocator.tsx, OptimizerPanel.tsx.
**Warning signs:** Cards appear with double borders or unexpected opaque backgrounds overriding the glass effect.

### Pitfall 5: Skeleton used in 20 sites — regression risk is high
**What goes wrong:** Skeleton is imported in 20 files (pages and components). If the new skeleton-shimmer class is not in the CSS bundle when these components render, skeletons appear invisible or unstyled.
**Why it happens:** .skeleton-shimmer is defined in globals.css; this is always loaded, so there is no CSS split risk. However, the actual concern is that some Skeleton usages pass explicit `className` that includes `animate-pulse` or `bg-accent`. These would override the new shimmer.
**How to avoid:** After updating skeleton.tsx, search for `<Skeleton className=` across all 20 import sites and remove any `animate-pulse` or `bg-accent` references passed by callers.
**Warning signs:** Some skeletons shimmer (from updated default), others still pulse solid (from caller-supplied className).

---

## Code Examples

### button.tsx — complete variant replacements
```typescript
// Source: 02-UI-SPEC.md component contract, globals.css :root tokens
const buttonVariants = cva(
  // Base: keep layout, keep rounded-md, change font-medium→font-semibold, remove ring classes, add outline-none
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:outline-none",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--to-accent-amber)] text-[#080b10] hover:shadow-[var(--glow-amber)] focus-visible:shadow-[var(--glow-amber)]/50",
        secondary:
          "bg-[var(--to-surface-raised)] text-[var(--to-text-primary)] border border-[var(--to-border)] hover:bg-[var(--to-surface-overlay)] focus-visible:shadow-[var(--glow-amber)]/50",
        ghost:
          "text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] focus-visible:shadow-[var(--glow-amber)]/50",
        outline:
          "border border-[var(--to-border)] text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] focus-visible:shadow-[var(--glow-amber)]/50",
        destructive:
          "bg-[var(--to-error)] text-white hover:bg-[var(--to-error)]/90 focus-visible:shadow-[var(--glow-red)]/50",
        link:
          "text-[var(--to-accent-amber)] underline-offset-4 hover:underline",
      },
      size: {
        // All size variants kept exactly as-is per UI-SPEC
      },
    },
  }
)
```

### badge.tsx — base + variant replacements
```typescript
// Source: 02-UI-SPEC.md badge contract
// Base: change font-medium→font-semibold, py-0.5→py-1
const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-full border border-transparent px-2 py-1 text-xs font-semibold w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none transition-[color,box-shadow] overflow-hidden",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--to-surface-raised)] text-[var(--to-text-primary)]",
        secondary:
          "bg-[var(--to-surface)] text-[var(--to-text-secondary)] border border-[var(--to-border)]",
        outline:
          "text-[var(--to-text-secondary)] border border-[var(--to-border)]",
        destructive:
          "bg-[var(--to-error)]/15 text-[var(--to-error)] border border-[var(--to-error)]/30",
        ghost:
          "text-[var(--to-text-dim)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
)
```

### skeleton.tsx — one-line change
```typescript
// Source: 02-UI-SPEC.md skeleton contract; .skeleton-shimmer verified at globals.css:966-974
// Before: className={cn("bg-accent animate-pulse rounded-md", className)}
// After:
className={cn("skeleton-shimmer rounded-md", className)}
```

### table.tsx — TableRow and TableHead (most impactful changes)
```typescript
// TableRow: replace hover:bg-muted/50 and border-b
className={cn(
  "hover:bg-[var(--to-surface-raised)] border-b border-[var(--to-border-subtle)] data-[state=selected]:bg-[var(--to-surface-raised)] transition-colors",
  className
)}

// TableHead: replace text-foreground and font-medium, add uppercase/tracking
className={cn(
  "text-[var(--to-text-secondary)] h-10 px-2 text-left align-middle font-semibold whitespace-nowrap uppercase tracking-wider text-[length:var(--text-xs)] [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
  className
)}
```

### Skeleton page usage pattern (Dashboard example)
```typescript
// Source: 02-UI-SPEC.md skeleton shape guide
// Wrap data sections — shape must match rendered component dimensions
{isLoading ? (
  <div aria-label="Loading dashboard metrics" className="space-y-4">
    <Skeleton className="h-24 w-full" />       {/* card skeleton */}
    <Skeleton className="h-8 w-32" />           {/* metric value */}
    <Skeleton className="h-48 w-full" />        {/* chart */}
  </div>
) : (
  <ActualContent />
)}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| shadcn default bg-primary tokens | --to-* custom property tokens via arbitrary values | Phase 1 (token system) | Component restyling now possible without changing CSS var values |
| animate-pulse solid background on Skeleton | gradient shimmer .skeleton-shimmer class | Phase 1 (keyframe added to globals.css) | Skeleton just needs class update, no new CSS |
| bg-card / text-card-foreground on Card | glass-panel class | This phase | Single class carries all glass styling |

**No deprecated patterns introduced.** This phase removes shadcn defaults and replaces them with the Phase 1 token system.

---

## Open Questions

1. **font-semibold on button base vs existing callers**
   - What we know: current button base is `font-medium`; UI-SPEC requires `font-semibold`
   - What's unclear: Whether any caller deliberately passes `font-normal` or `font-medium` via `className` to override — those would still work due to cn() specificity
   - Recommendation: Make the change to font-semibold in base; it is correct per spec. Caller overrides continue to work.

2. **TableHeader `[&_tr]:border-b` vs explicit border-b on TableHeader**
   - What we know: Current TableHeader uses the Tailwind selector `[&_tr]:border-b`. UI-SPEC says "Add: border-b border-[var(--to-border)]" to TableHeader itself.
   - What's unclear: Whether adding it to `<thead>` directly vs via child selector `[&_tr]` produces the right visual result
   - Recommendation: Keep the existing `[&_tr]:border-b` selector approach but replace the borderless default with `[&_tr]:border-b [&_tr]:border-[var(--to-border)]` for token-correct color. Both approaches produce the same visual line.

3. **Positions page skeleton — no existing Skeleton import**
   - What we know: `app/positions/` is not in the list of current Skeleton importers, but it is a target page per UI-SPEC
   - What's unclear: Whether positions/page.tsx has its own loading state already (via different mechanism) or has none
   - Recommendation: Planner should include a task to inspect positions/page.tsx loading state and add Skeleton import + usage.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected in frontend — visual/snapshot testing not configured |
| Config file | No jest.config.*, no vitest.config.*, no playwright.config.* found in frontend/ |
| Quick run command | Manual: `npm run dev` in frontend/ and visual inspection |
| Full suite command | Manual: visual inspection across 5 target pages |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-01 | All 6 button variants render with correct token-based colors and hover glow | visual-manual | N/A | N/A |
| COMP-02 | Card renders as glass-panel with correct border, radius, backdrop-filter | visual-manual | N/A | N/A |
| COMP-03 | Table rows hover bg-[--to-surface-raised], head text is --to-text-secondary | visual-manual | N/A | N/A |
| COMP-04 | Badge variants render correct bg/text/border token combos | visual-manual | N/A | N/A |
| COMP-05 | Input renders with dark bg, amber focus glow, disabled/error states | visual-manual | N/A | N/A |
| COMP-06 | Skeleton emits shimmer (not pulse) on Dashboard, Positions, Analytics, Risk, PropFirm | visual-manual | N/A | N/A |

### Sampling Rate
- **Per task commit:** `cd frontend && npm run build` — catches TypeScript errors and class string regressions at compile time
- **Per wave merge:** Visual inspection of all 5 target pages in browser
- **Phase gate:** All 6 component files verified visually before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `frontend/src/components/ui/input.tsx` — new file (COMP-05), does not exist
- [ ] No automated test infrastructure exists for frontend — all validation is build-time (tsc/tailwind) + manual visual review

*(No existing test infrastructure covers component visual regressions — this is expected and pre-existing. Phase 2 does not introduce a test framework; that is v2.0 scope.)*

---

## Sources

### Primary (HIGH confidence)
- Direct file reads: `frontend/src/components/ui/button.tsx`, `card.tsx`, `badge.tsx`, `table.tsx`, `skeleton.tsx` — current class strings extracted verbatim
- Direct file reads: `frontend/src/app/globals.css` lines 280-356 (panel system), 957-975 (skeleton-shimmer), 200-226 (spacing/radius/gradient tokens), 76-100 (color tokens)
- `02-UI-SPEC.md` — component-by-component class change contracts (pre-verified by gsd-ui-checker)
- `02-CONTEXT.md` — locked decisions verbatim

### Secondary (MEDIUM confidence)
- `grep` audit of all Card, Button, Badge, Table, Skeleton import sites — 7 Card, 15 Button, 12 Badge, 3 Table, 20 Skeleton consumers identified

### Tertiary (LOW confidence)
- None — all findings verified from direct codebase inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed installed, no new deps required
- Current class strings: HIGH — read directly from source files
- Token availability: HIGH — verified in globals.css :root
- skeleton-shimmer availability: HIGH — confirmed at globals.css:958-974, `.skeleton-shimmer` class at line 966
- input.tsx absence: HIGH — confirmed MISSING via ls check
- Architecture: HIGH — patterns confirmed from existing codebase conventions
- Pitfalls: HIGH — derived from direct code reading, not speculation

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable stack — no fast-moving dependencies)
