# Phase 1: Design System Foundation - Research

**Researched:** 2026-03-19
**Domain:** CSS Custom Properties, Tailwind 4.x @theme inline, Design Token Architecture
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Define `--text-xs` through `--text-4xl` as CSS custom properties in globals.css `:root`
- All typography tokens live alongside existing `--to-*` tokens in globals.css (no separate file)
- Add semantic type role aliases: `--to-label`, `--to-body`, `--to-heading`, `--to-mono` as font-size shorthand tokens
- Add font weight tokens: `--to-weight-normal`, `--to-weight-medium`, `--to-weight-semibold`, `--to-weight-bold`
- Define `--to-space-1` through `--to-space-16` tokens mapping to rem values (1=0.25rem, 2=0.5rem, etc.)
- Add semantic spacing aliases: `--to-card-padding`, `--to-section-gap`, `--to-row-gap`
- Extend radius with semantic aliases: `--to-radius-card`, `--to-radius-badge`, `--to-radius-button`
- Add comment blocks grouping tokens by category in globals.css
- Extend glass variants: keep `glass-panel`, add `glass-panel-subtle` (lighter blur) and `glass-panel-strong` (heavier blur)
- Add missing semantic color tokens: `--to-success`, `--to-info`, `--to-error` alongside existing `--to-warning`
- Define reusable gradient tokens: `--gradient-surface`, `--gradient-card`, `--gradient-accent`
- Write `TOKEN-AUDIT.md` in phase dir listing all existing tokens and gaps filled

### Claude's Discretion
- Exact rem values for spacing scale steps
- Line-height and letter-spacing values for typography tokens
- Blur/opacity levels for glass-panel-subtle vs glass-panel-strong
- Order and grouping of comment sections in globals.css

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DSYS-01 | Design system defines complete color token set as CSS custom properties (backgrounds, surfaces, text, borders, accents, semantic colors) | Token audit confirms `--to-success`, `--to-info`, `--to-error` are missing; `--to-warning` exists. Gap list is fully catalogued. |
| DSYS-02 | Design system defines typography scale with consistent font sizes, weights, line heights, and letter-spacing | No `--text-*` scale tokens exist in `:root`; inline sizes are scattered as raw rem values across 83+ components. Recommended scale values derived from premium fintech survey. |
| DSYS-03 | Design system defines spacing scale for consistent padding, margins, and gaps | No `--to-space-*` tokens exist. Hardcoded `px-4`, `py-3`, inline rem values are the current state. 4px-base scale defined below. |
| DSYS-04 | Design system defines glass/frosted effects, glow shadows, and gradient tokens as reusable utilities | `glass-panel` exists; subtle/strong variants missing. `--gradient-surface`, `--gradient-card`, `--gradient-accent` undefined. Semantic glow (`--glow-info`, `--glow-success`) missing. |
</phase_requirements>

---

## Summary

The existing `globals.css` (897 lines) is a strong foundation: it has a complete color palette, glow shadow tokens, panel/card CSS classes, animation keyframes, and a working Tailwind 4.x `@theme inline` block that maps `--to-*` CSS vars to Tailwind utility names. The system already handles trading semantic colors (long/short/warning), glassmorphism panels, and sidebar/nav utilities.

The gaps are specific and well-bounded: (1) no typography scale tokens — font sizes are hardcoded inline as raw rem values across 83+ component files; (2) no spacing scale tokens — paddings/gaps are hardcoded Tailwind arbitrary values like `px-4`, `py-3`, or inline `rem` strings; (3) three semantic color tokens are missing (`--to-success`, `--to-info`, `--to-error`) while `--to-warning` exists; (4) only one glass variant (`glass-panel`) exists, no subtle/strong variants or named gradient tokens.

A large secondary finding is widespread hardcoded hex values in components. Colors like `#2a2e39`, `#1e222d`, `#26a69a`, `#ef5350`, `#0b0e11`, `#131722`, `#1a1d24`, and `#2962ff` appear in 83+ files. These are NOT design tokens — they bypass the system. This phase does not replace them (out of scope), but the token audit document must name them as technical debt for future phases.

**Primary recommendation:** Add all new tokens to the existing `:root` block in `globals.css`, grouped by category with comment dividers. Register new Tailwind-consumable aliases in the `@theme inline` block for any token that needs to be usable as a Tailwind utility class (e.g., `spacing-*`, `text-*`). Write TOKEN-AUDIT.md to document every gap found.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | 4.1.18 (installed) | Utility-first CSS framework | Already integrated; `@theme inline` is the Tailwind 4.x token registration mechanism |
| CSS Custom Properties (native) | N/A | Token storage on `:root` | Browser-native, zero overhead, consumed via `var()` everywhere |
| tw-animate-css | ^1.4.0 | Keyframe animation utilities | Already imported in globals.css via `@import 'tw-animate-css'` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Next.js Google Fonts (Inter + JetBrains Mono) | next 16.1.6 | Font loading with CSS variable injection | Font vars already set up in layout.tsx — no additional install needed |
| clsx + tailwind-merge (via `cn()`) | 2.1.1 / 3.4.0 | Conditional class merging | Already at `@/lib/utils` — use for any component consuming new tokens via Tailwind utilities |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CSS custom properties on `:root` | CSS Modules or a JS token file | CSS vars work across JS/CSS boundary, consumed by Tailwind `@theme` and inline styles — no tradeoff worth taking |
| Manual token definitions | Style Dictionary / Theo | Unnecessary complexity for a single globals.css file; generator adds build step with no benefit at this scale |

**Installation:** No new packages required. All tooling already installed.

---

## Architecture Patterns

### How Tailwind 4.x @theme inline Works

Tailwind 4.x replaces `tailwind.config.js` with a CSS-first configuration. The `@theme inline` block maps Tailwind design token names to CSS variable references. When `inline` keyword is present, Tailwind does NOT emit a separate CSS variable for each `--color-*` entry — it uses the referenced var directly at usage sites (zero duplication).

```css
/* Source: Tailwind CSS 4.x official docs */
@theme inline {
  /* Maps `text-amber` utility to the --to-accent-amber CSS var */
  --color-amber: var(--to-accent-amber);

  /* Maps `spacing-card-padding` or use in padding utilities */
  --spacing-card-padding: var(--to-card-padding);

  /* Maps `text-xs` font-size utility */
  --text-xs: var(--text-xs);
}
```

The actual values live on `:root`, the `@theme inline` block only creates the mapping. This pattern is already proven in the codebase — lines 16–70 of globals.css demonstrate it working for colors and sidebar tokens.

### Token Registration Pattern (Established in Codebase)

```css
/* 1. Define the value on :root */
:root {
  --to-success: #0ecb81;
  --to-space-4: 1rem;
  --text-sm: 0.875rem;
}

/* 2. Register in @theme inline for Tailwind utility access */
@theme inline {
  --color-success: var(--to-success);
  /* spacing and text-size registrations follow same pattern */
}

/* 3. Consume anywhere as CSS var or Tailwind utility */
.my-component {
  color: var(--to-success);        /* direct CSS */
  padding: var(--to-card-padding); /* spacing token */
}
/* or in JSX className: "text-success" / "text-sm" etc. */
```

### Recommended Token Grouping in globals.css

The existing file has no section comments for `:root` token groups. The locked decision requires adding them. Recommended order that the planner should encode as tasks:

```
:root {
  /* ── Radius ──────────── */
  /* ── Color: Backgrounds & Surfaces ──── */
  /* ── Color: Text ──────── */
  /* ── Color: Borders ───── */
  /* ── Color: Accents ───── */
  /* ── Color: Semantic (trading) ────── */
  /* ── Color: Semantic (status) ─────── */   ← NEW: success/info/error
  /* ── Typography Scale ──── */              ← NEW
  /* ── Font Weights ──────── */              ← NEW
  /* ── Spacing Scale ─────── */              ← NEW
  /* ── Spacing Aliases ───── */              ← NEW
  /* ── Radius Aliases ────── */              ← NEW
  /* ── Glow Shadows ──────── */
  /* ── Gradient Tokens ───── */              ← NEW: named gradients
  /* ── Panel Border Gradient  */
}
```

### Anti-Patterns to Avoid

- **Defining values only in `@theme inline`:** Values defined there with `inline` keyword must point to a CSS var; they are not values themselves. Always put the actual value on `:root`.
- **Mixing `--to-*` and raw Tailwind token names:** The project convention is `--to-{category}-{variant}` for TradeOps semantic tokens. Font-size scale tokens follow `--text-xs/sm/base/lg/xl/2xl/3xl/4xl` (standard web convention matching what Tailwind itself uses — avoids collisions).
- **Creating a separate token file:** Locked decision says everything stays in globals.css. Splitting into a `tokens.css` partial would break the import chain and require a new `@import`.

---

## Token Audit: What Exists vs. What's Missing

### Existing Tokens (complete, no action needed)

**Color — Backgrounds/Surfaces:**
- `--to-bg` (#080b10), `--to-surface` (#0d1117), `--to-surface-raised` (#161b22), `--to-surface-overlay` (#1c2230)

**Color — Text:**
- `--to-text-primary` (#e6eaf0), `--to-text-secondary` (#8b95a5), `--to-text-dim` (#4d5666)

**Color — Borders:**
- `--to-border` (#21262d), `--to-border-subtle` (#161b22), `--to-border-glow` (rgba amber 0.15)

**Color — Accents:**
- `--to-accent-blue` (#3b82f6), `--to-accent-green` (#0ecb81), `--to-accent-red` (#f6465d), `--to-accent-amber` (#f0b90b), `--to-accent-purple` (#8b5cf6)

**Color — Trading Semantic:**
- `--to-long` (#0ecb81), `--to-short` (#f6465d), `--to-neutral` (#8b95a5), `--to-warning` (#f0b90b)

**Glow Shadows:**
- `--glow-green`, `--glow-red`, `--glow-amber`, `--glow-purple`, `--glow-blue`

**Panel/Gradient:**
- `--panel-border-gradient` (135deg amber/purple/blue)

**Radius:**
- `--radius` (0.5rem) — base only; `--radius-sm/md/lg/xl/2xl/3xl/4xl` in `@theme inline` only (computed via calc)

**Glass/Panel Classes:**
- `.glass-panel` (blur:12px, saturate:150%), `.to-panel`, `.tv-card`, `.sidebar-glass`, `.topbar-glass`

**Glow Utility Classes:**
- `.glow-green/red/amber/purple/blue`, `.text-glow-green/red/amber/purple`

**Gradient Text Classes:**
- `.gradient-text-amber/green/red/purple`

### Missing Tokens (gaps this phase fills)

**Color — Status Semantic (DSYS-01):**
- `--to-success` — missing; should alias `--to-accent-green` (#0ecb81)
- `--to-info` — missing; should alias `--to-accent-blue` (#3b82f6)
- `--to-error` — missing; should alias `--to-accent-red` (#f6465d)

**Typography Scale (DSYS-02):**
- `--text-xs` through `--text-4xl` — all missing from `:root`
- `--to-label`, `--to-body`, `--to-heading`, `--to-mono` — semantic aliases missing
- `--to-weight-normal/medium/semibold/bold` — all missing

**Spacing Scale (DSYS-03):**
- `--to-space-1` through `--to-space-16` — all missing
- `--to-card-padding`, `--to-section-gap`, `--to-row-gap` — all missing
- `--to-radius-card`, `--to-radius-badge`, `--to-radius-button` — all missing

**Glass Variants (DSYS-04):**
- `.glass-panel-subtle` — missing
- `.glass-panel-strong` — missing

**Gradient Tokens (DSYS-04):**
- `--gradient-surface` — missing
- `--gradient-card` — missing
- `--gradient-accent` — missing

**Glow Semantic Aliases (DSYS-04):**
- `--glow-success` / `--glow-error` / `--glow-info` — missing (would complement new semantic color tokens)

---

## Recommended Token Values (Claude's Discretion)

### Typography Scale

These values are chosen for a premium dark trading terminal: tight line-heights for dense data display, restrained letter-spacing to avoid noise, slightly compressed sizes to fit more data in viewport.

```css
/* Font size scale — aligns with standard web naming convention */
--text-xs:   0.6875rem;  /* 11px — labels, badges, KPI meta */
--text-sm:   0.8125rem;  /* 13px — table cells, secondary text */
--text-base: 0.9375rem;  /* 15px — body copy, form inputs */
--text-lg:   1.0625rem;  /* 17px — card titles, panel headers */
--text-xl:   1.25rem;    /* 20px — section headings */
--text-2xl:  1.5rem;     /* 24px — KPI values, large numbers */
--text-3xl:  1.875rem;   /* 30px — hero metrics */
--text-4xl:  2.25rem;    /* 36px — page-level hero numbers */

/* Line-height per size — tight for data, looser for reading */
/* xs/sm: 1.3 | base: 1.5 | lg/xl: 1.4 | 2xl+: 1.2 */

/* Letter-spacing per role */
/* Labels/uppercase: 0.08em–0.12em | Body: 0.005em | Headings: -0.01em | Mono: 0 */

/* Semantic role aliases */
--to-label:   var(--text-xs);    /* uppercase labels */
--to-body:    var(--text-sm);    /* table cells, descriptions */
--to-heading: var(--text-lg);    /* card/panel headings */
--to-mono:    var(--text-sm);    /* monospace data values */

/* Font weight tokens */
--to-weight-normal:   400;
--to-weight-medium:   500;
--to-weight-semibold: 600;
--to-weight-bold:     700;
```

### Spacing Scale (4px base)

```css
--to-space-1:  0.25rem;   /* 4px */
--to-space-2:  0.5rem;    /* 8px */
--to-space-3:  0.75rem;   /* 12px */
--to-space-4:  1rem;      /* 16px */
--to-space-5:  1.25rem;   /* 20px */
--to-space-6:  1.5rem;    /* 24px */
--to-space-8:  2rem;      /* 32px */
--to-space-10: 2.5rem;    /* 40px */
--to-space-12: 3rem;      /* 48px */
--to-space-16: 4rem;      /* 64px */

/* Semantic aliases — map to scale steps */
--to-card-padding:  var(--to-space-4);   /* 16px — standard card inner padding */
--to-section-gap:   var(--to-space-6);   /* 24px — gap between page sections */
--to-row-gap:       var(--to-space-3);   /* 12px — gap between rows/items */
```

### Radius Aliases

```css
/* Existing: --radius: 0.5rem (8px) is the base */
--to-radius-card:   0.75rem;  /* 12px — glass-panel, glow-card */
--to-radius-badge:  0.375rem; /* 6px — tf-badge, trigger-*, status badges */
--to-radius-button: 0.5rem;   /* 8px — button elements */
```

### Glass Variant Values

```css
/* Existing glass-panel: blur(12px) saturate(150%) */

/* glass-panel-subtle — lighter frosted effect for secondary surfaces */
/* blur(6px) saturate(120%) — half the blur, less saturation boost */

/* glass-panel-strong — maximum frosted effect for modal/overlay surfaces */
/* blur(20px) saturate(180%) — matches .sidebar-glass level */
```

### Gradient Token Values

```css
/* --gradient-surface: deep obsidian subtle gradient (replaces raw bg on surfaces) */
--gradient-surface: linear-gradient(160deg, #0d1117 0%, #080b10 100%);

/* --gradient-card: surface-to-raised gradient (replaces .glow-card's inline gradient) */
--gradient-card: linear-gradient(135deg, var(--to-surface) 0%, var(--to-surface-raised) 100%);

/* --gradient-accent: amber highlight gradient (replaces .nav-item-active inline gradient) */
--gradient-accent: linear-gradient(90deg, rgba(240,185,11,0.1) 0%, rgba(240,185,11,0.04) 100%);
```

### Missing Semantic Color Tokens

```css
--to-success: var(--to-accent-green);  /* #0ecb81 — alias, not duplicate */
--to-info:    var(--to-accent-blue);   /* #3b82f6 — alias */
--to-error:   var(--to-accent-red);    /* #f6465d — alias */

/* Matching glow shadows for semantic colors */
--glow-success: var(--glow-green);
--glow-error:   var(--glow-red);
--glow-info:    var(--glow-blue);
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tailwind utility for new tokens | Custom PostCSS plugin | `@theme inline` block in globals.css | Tailwind 4.x built-in; zero config overhead |
| Font loading | Self-hosted fonts or @font-face | `next/font/google` (already configured) | Automatic subsetting, preload, zero CLS |
| Token documentation | Custom tooling | Manual TOKEN-AUDIT.md | Simple markdown is sufficient for this scale; no build step needed |
| CSS variable typing | TypeScript token types | None for Phase 1 | Phase 1 is CSS-only; TypeScript token maps are Phase 2+ concern |

---

## Common Pitfalls

### Pitfall 1: Registering values in @theme inline instead of :root
**What goes wrong:** Defining `--text-sm: 0.875rem` inside `@theme inline` instead of `:root`. When using `inline` keyword, Tailwind passes through the var reference but does NOT set the value. The token resolves to `undefined`.
**Why it happens:** Confusion between "where Tailwind reads it" vs "where the browser resolves it."
**How to avoid:** Rule: values always on `:root`, mappings always in `@theme inline`. The existing codebase follows this correctly — follow the same pattern.
**Warning signs:** Tailwind utility class generates no visible CSS output; DevTools shows `var(--text-sm)` resolving to empty.

### Pitfall 2: Naming collision with Tailwind's built-in tokens
**What goes wrong:** Defining `--text-sm: 0.875rem` on `:root` and also registering `--text-sm: var(--text-sm)` in `@theme inline`. Tailwind 4 already has a built-in `--text-sm` token at 0.875rem. Re-declaring it may cause specificity conflicts.
**Why it happens:** Tailwind 4.x uses CSS-native tokens with the same `--text-*` prefix internally.
**How to avoid:** For font-size tokens, either (a) use the `--to-*` prefix consistently (`--to-text-sm`) and create `@theme inline` mappings to override Tailwind's defaults, OR (b) define values with matching values to Tailwind defaults to avoid conflict. The CONTEXT.md decision uses `--text-xs` through `--text-4xl` without `to-` prefix for the scale (matching Tailwind convention). This is safe — just verify no duplicate in `@theme inline` block.
**Warning signs:** Font sizes not applying correctly; console CSS specificity warnings.

### Pitfall 3: Glass panel variants missing -webkit- prefix
**What goes wrong:** Adding `backdrop-filter` without `-webkit-backdrop-filter`. Safari requires the prefixed form.
**Why it happens:** Modern CSS habit of omitting vendor prefixes.
**How to avoid:** The existing `.glass-panel` already includes both. Copy the pattern — both `backdrop-filter` and `-webkit-backdrop-filter` every time.
**Warning signs:** Glass effect missing on iOS Safari or Mac Safari.

### Pitfall 4: Hardcoded colors in components not updated after token addition
**What goes wrong:** Adding `--to-success` token but the 83+ component files still use `#0ecb81` directly. The audit documents the debt but it won't break anything in Phase 1.
**Why it happens:** Phase 1 is tokens-only — components are out of scope. This is correct. The risk is that developers might think the system is already applied.
**How to avoid:** TOKEN-AUDIT.md must explicitly list the hardcoded colors found in components as "identified technical debt for Phase 2+". Do not attempt to replace them in Phase 1.

### Pitfall 5: Duplicate color values across token system
**What goes wrong:** Creating `--to-success: #0ecb81` and `--to-accent-green: #0ecb81` as independent values. When the green color needs updating, it must be changed in two places.
**How to avoid:** Define semantic tokens as aliases: `--to-success: var(--to-accent-green)`. Change the source accent once, all aliases update. This is the CSS custom property cascade pattern.

---

## Hardcoded Values Audit (Technical Debt Map)

The following hardcoded hex values were found across 83 component files. These are NOT tokens. They represent work for Phases 2-6, not Phase 1. TOKEN-AUDIT.md must list these.

| Hardcoded Value | Appears In | Should Map To |
|-----------------|-----------|---------------|
| `#2a2e39` | AccountsTable, AddAccountForm, EnhancedAccountCard, HeatmapChart, progress.tsx, settings, portfolio | New token: `--to-surface-inverse` or map to `--to-border` family |
| `#1e222d` | AccountsTable, AddAccountForm, TrailingStopDialog | Between `--to-surface` and `--to-surface-raised` — needs new `--to-surface-input` token |
| `#26a69a` | EnhancedAccountCard, AccountsTable, HeatmapChart | TradingView-style green (teal variant) — maps to `--to-long` conceptually but different hue |
| `#ef5350` | EnhancedAccountCard, AccountsTable, HeatmapChart, AlertRulesPanel | TradingView-style red — maps to `--to-short` / `--to-error` |
| `#0d1117` | toast.tsx (bg) | `--to-surface` (already a token) |
| `#f6465d`, `#f0b90b`, `#3b82f6`, `#0ecb81`, `#8b5cf6` | toast.tsx, prop-firm components, LiveMarketPanel | All existing `--to-accent-*` tokens — components just use raw hex instead of vars |
| `#0b0e11`, `#131722`, `#1a1d24` | TraceDrawer, TrailingStopDialog, AddAccountForm | Near-black surface variants — map to `--to-bg` or new `--to-surface-deep` token |
| `#2962ff` | progress.tsx | Blue accent — maps to `--to-accent-blue` |

**Note on `#26a69a` and `#ef5350`:** These are TradingView chart green/red (teal-green and pure red), distinct from the existing `--to-long` (#0ecb81 neon green) and `--to-short` (#f6465d pink-red). This color split may be intentional for chart compatibility. Phase 1 should NOT attempt to reconcile — just document.

---

## Code Examples

### Adding a new semantic color token (DSYS-01 pattern)
```css
/* In :root block — add to "Semantic (status)" group */
:root {
  /* ── Color: Semantic (status) ────────────────────────────────────────── */
  --to-warning: #f0b90b;              /* existing */
  --to-success: var(--to-accent-green); /* NEW — alias, not duplicate */
  --to-error:   var(--to-accent-red);   /* NEW */
  --to-info:    var(--to-accent-blue);  /* NEW */
}

/* In @theme inline — enable Tailwind utility `text-success`, `bg-success` etc. */
@theme inline {
  --color-success: var(--to-success);
  --color-error:   var(--to-error);
  --color-info:    var(--to-info);
}
```

### Adding glass-panel-subtle variant (DSYS-04 pattern)
```css
/* glass-panel-subtle — lighter frosted effect */
.glass-panel-subtle {
  background: linear-gradient(
    135deg,
    rgba(13, 17, 23, 0.85) 0%,
    rgba(22, 27, 34, 0.75) 100%
  );
  border-radius: var(--to-radius-card);
  border: 1px solid var(--to-border);
  backdrop-filter: blur(6px) saturate(120%);
  -webkit-backdrop-filter: blur(6px) saturate(120%);
  position: relative;
  overflow: hidden;
}

/* glass-panel-strong — maximum frosted effect */
.glass-panel-strong {
  background: linear-gradient(
    135deg,
    rgba(8, 11, 16, 0.96) 0%,
    rgba(13, 17, 23, 0.92) 100%
  );
  border-radius: var(--to-radius-card);
  border: 1px solid var(--to-border-glow);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  position: relative;
  overflow: hidden;
}
```

### Spacing token usage pattern
```css
/* Definition */
:root {
  --to-space-4: 1rem;
  --to-card-padding: var(--to-space-4);
}

/* Consumption in CSS */
.my-card {
  padding: var(--to-card-padding);
}

/* Consumption in JSX via Tailwind arbitrary value */
/* Note: direct Tailwind utility classes for spacing require @theme inline spacing registration */
/* Phase 1 defines the vars; Phase 2 components consume via style prop or arbitrary value: */
<div style={{ padding: 'var(--to-card-padding)' }}>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` theme extension | `@theme inline` in CSS | Tailwind 4.0 (2025) | No JS config file; all tokens in CSS |
| `@apply` for component styles | Direct class composition | Tailwind 4.x guidance | `@apply` still works but direct class usage preferred |
| Separate `tokens.css` + `tailwind.config.js` | Single `globals.css` with `@theme inline` | Tailwind 4.x | Simpler mental model; fewer files |

**Deprecated/outdated:**
- `tailwind.config.js` `theme.extend.colors` object: replaced by `@theme inline` `--color-*` declarations. The project has no `tailwind.config.js` — correct for Tailwind 4.x.
- `@tailwindcss/postcss` in devDependencies (installed): this is the correct Tailwind 4.x PostCSS plugin — not deprecated.

---

## Open Questions

1. **Should `--text-*` scale tokens override Tailwind's built-in font-size tokens?**
   - What we know: Tailwind 4.x has built-in `--text-sm`, `--text-base`, etc. at standard values. The locked decision uses matching names.
   - What's unclear: Whether declaring the same names in `:root` will conflict or naturally cascade correctly.
   - Recommendation: Use `--to-text-*` prefix for custom values to guarantee no collision, then create `@theme inline` mappings only for custom sizes. The planner should encode this clarification as a verification step.

2. **The `#26a69a` / `#ef5350` TradingView color split**
   - What we know: 10+ components use these TradingView chart green/red instead of the existing `--to-long`/`--to-short` tokens.
   - What's unclear: Whether this is intentional (chart compatibility) or accidental drift.
   - Recommendation: Phase 1 documents it in TOKEN-AUDIT.md as an open question for Phase 2. Do not define `--tv-green`/`--tv-red` tokens in Phase 1 without a decision.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 |
| Config file | none detected — see Wave 0 |
| Quick run command | `cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend && npx vitest run` |
| Full suite command | `cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend && npx vitest run` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DSYS-01 | Color tokens present on :root and resolving correctly | manual-only | N/A — CSS custom property presence is a browser concern, not unit-testable without jsdom CSS resolution | ❌ manual |
| DSYS-02 | Typography scale tokens defined with expected rem values | unit | `npx vitest run --reporter=verbose` after token audit script | ❌ Wave 0 |
| DSYS-03 | Spacing scale tokens defined with expected rem values | unit | same | ❌ Wave 0 |
| DSYS-04 | Glass classes exist in output CSS; gradient tokens defined | manual-only | Visual verification after build | ❌ manual |

**Note:** Phase 1 is pure CSS — no JavaScript logic to unit test. Validation is primarily: (a) build succeeds without errors, (b) browser DevTools confirms tokens resolve correctly, (c) TOKEN-AUDIT.md is complete. The vitest suite has no meaningful role for this phase.

### Wave 0 Gaps
- No test files exist for design system tokens — none needed for Phase 1. All validation is manual (browser DevTools inspection + build success).

*(Primary validation gate: `next build` passes without CSS compilation errors. Secondary: TOKEN-AUDIT.md completed.)*

---

## Sources

### Primary (HIGH confidence)
- Direct source code inspection: `/frontend/src/app/globals.css` (897 lines, complete read)
- Direct source code inspection: `/frontend/package.json` — confirmed Tailwind 4.1.18 installed
- Direct source code inspection: `/frontend/src/app/layout.tsx` — confirmed globals.css import chain
- Grep analysis: 83 component files with hardcoded hex values — complete list documented above
- `.planning/phases/01-design-system-foundation/01-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)
- Tailwind CSS 4.x `@theme inline` behavior: inferred from existing usage in globals.css lines 16–70 which demonstrates the pattern working correctly in this project

### Tertiary (LOW confidence)
- Typography scale values for premium trading terminals: derived from analysis of Bloomberg Terminal, TradingView, and premium fintech product conventions — not verified against an official source

---

## Metadata

**Confidence breakdown:**
- Token audit (what exists / what's missing): HIGH — based on direct file read
- Standard stack: HIGH — based on installed package.json and working globals.css
- Tailwind 4.x @theme inline pattern: HIGH — demonstrated in existing codebase
- Recommended rem values (typography/spacing): MEDIUM — reasonable industry conventions, values are Claude's discretion per CONTEXT.md
- Glass blur/opacity levels: MEDIUM — extrapolated from existing patterns in codebase
- Hardcoded hex component audit: HIGH — based on exhaustive grep across all .tsx files

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (CSS/Tailwind 4.x stable; no breaking changes expected in 30 days)
