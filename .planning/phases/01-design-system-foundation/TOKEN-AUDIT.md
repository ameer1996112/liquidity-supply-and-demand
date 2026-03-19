# TOKEN-AUDIT.md — Phase 1: Design System Foundation

**Generated:** 2026-03-19
**Source:** Direct inspection of `frontend/src/app/globals.css` (897 lines before Phase 1) + grep of 83 component files

---

## Existing Tokens (no action needed)

### Color — Backgrounds & Surfaces
| Token | Value |
|-------|-------|
| `--to-bg` | `#080b10` |
| `--to-surface` | `#0d1117` |
| `--to-surface-raised` | `#161b22` |
| `--to-surface-overlay` | `#1c2230` |

### Color — Text
| Token | Value |
|-------|-------|
| `--to-text-primary` | `#e6eaf0` |
| `--to-text-secondary` | `#8b95a5` |
| `--to-text-dim` | `#4d5666` |

### Color — Borders
| Token | Value |
|-------|-------|
| `--to-border` | `#21262d` |
| `--to-border-subtle` | `#161b22` |
| `--to-border-glow` | `rgba(240, 185, 11, 0.15)` |

### Color — Accents
| Token | Value |
|-------|-------|
| `--to-accent-blue` | `#3b82f6` |
| `--to-accent-green` | `#0ecb81` |
| `--to-accent-red` | `#f6465d` |
| `--to-accent-amber` | `#f0b90b` |
| `--to-accent-purple` | `#8b5cf6` |

### Color — Semantic (trading)
| Token | Value |
|-------|-------|
| `--to-long` | `#0ecb81` |
| `--to-short` | `#f6465d` |
| `--to-neutral` | `#8b95a5` |
| `--to-warning` | `#f0b90b` |

### Glow Shadows
| Token | Value |
|-------|-------|
| `--glow-green` | `0 0 12px rgba(14,203,129,0.35), 0 0 24px rgba(14,203,129,0.12)` |
| `--glow-red` | `0 0 12px rgba(246,70,93,0.35), 0 0 24px rgba(246,70,93,0.12)` |
| `--glow-amber` | `0 0 12px rgba(240,185,11,0.35), 0 0 24px rgba(240,185,11,0.12)` |
| `--glow-purple` | `0 0 12px rgba(139,92,246,0.35), 0 0 24px rgba(139,92,246,0.12)` |
| `--glow-blue` | `0 0 12px rgba(59,130,246,0.35), 0 0 24px rgba(59,130,246,0.12)` |

### Panel & Gradient (pre-Phase 1)
| Token | Value |
|-------|-------|
| `--panel-border-gradient` | `linear-gradient(135deg, amber/purple/blue rgba)` |

### Glass/Panel CSS Classes (pre-Phase 1)
- `.glass-panel` — blur(12px) saturate(150%), amber shimmer ::before
- `.to-panel` — flat surface card
- `.tv-card` — TradingView-style card
- `.sidebar-glass` — sidebar backdrop
- `.topbar-glass` — topbar backdrop

### Glow & Text Utility Classes (pre-Phase 1)
- `.glow-green/red/amber/purple/blue`
- `.text-glow-green/red/amber/purple`
- `.gradient-text-amber/green/red/purple`

---

## Gaps Filled in Phase 1

### Plan 01-01: Color & Typography

| Token | Type | Value |
|-------|------|-------|
| `--to-success` | Semantic alias | `var(--to-accent-green)` |
| `--to-info` | Semantic alias | `var(--to-accent-blue)` |
| `--to-error` | Semantic alias | `var(--to-accent-red)` |
| `--glow-success` | Glow alias | `var(--glow-green)` |
| `--glow-error` | Glow alias | `var(--glow-red)` |
| `--glow-info` | Glow alias | `var(--glow-blue)` |
| `--text-xs` | Font size | `0.6875rem` (11px) |
| `--text-sm` | Font size | `0.8125rem` (13px) |
| `--text-base` | Font size | `0.9375rem` (15px) |
| `--text-lg` | Font size | `1.0625rem` (17px) |
| `--text-xl` | Font size | `1.25rem` (20px) |
| `--text-2xl` | Font size | `1.5rem` (24px) |
| `--text-3xl` | Font size | `1.875rem` (30px) |
| `--text-4xl` | Font size | `2.25rem` (36px) |
| `--to-weight-normal` | Font weight | `400` |
| `--to-weight-medium` | Font weight | `500` |
| `--to-weight-semibold` | Font weight | `600` |
| `--to-weight-bold` | Font weight | `700` |
| `--to-label` | Role alias | `var(--text-xs)` |
| `--to-body` | Role alias | `var(--text-sm)` |
| `--to-heading` | Role alias | `var(--text-lg)` |
| `--to-mono` | Role alias | `var(--text-sm)` |

Also added to `@theme inline`:
- `--color-success: var(--to-success)`
- `--color-error: var(--to-error)`
- `--color-info: var(--to-info)`

### Plan 01-02: Spacing, Radius, Glass, Gradients

| Token | Type | Value |
|-------|------|-------|
| `--to-space-1` | Spacing | `0.25rem` (4px) |
| `--to-space-2` | Spacing | `0.5rem` (8px) |
| `--to-space-3` | Spacing | `0.75rem` (12px) |
| `--to-space-4` | Spacing | `1rem` (16px) |
| `--to-space-5` | Spacing | `1.25rem` (20px) |
| `--to-space-6` | Spacing | `1.5rem` (24px) |
| `--to-space-8` | Spacing | `2rem` (32px) |
| `--to-space-10` | Spacing | `2.5rem` (40px) |
| `--to-space-12` | Spacing | `3rem` (48px) |
| `--to-space-16` | Spacing | `4rem` (64px) |
| `--to-card-padding` | Spacing alias | `var(--to-space-4)` |
| `--to-section-gap` | Spacing alias | `var(--to-space-6)` |
| `--to-row-gap` | Spacing alias | `var(--to-space-3)` |
| `--to-radius-card` | Radius alias | `0.75rem` |
| `--to-radius-badge` | Radius alias | `0.375rem` |
| `--to-radius-button` | Radius alias | `0.5rem` |
| `--gradient-surface` | Gradient | `linear-gradient(160deg, #0d1117 0%, #080b10 100%)` |
| `--gradient-card` | Gradient | `linear-gradient(135deg, --to-surface → --to-surface-raised)` |
| `--gradient-accent` | Gradient | `linear-gradient(90deg, amber rgba 0.1 → 0.04)` |

New CSS classes:
- `.glass-panel-subtle` — blur(6px) saturate(120%), lighter frosted secondary surfaces
- `.glass-panel-strong` — blur(20px) saturate(180%), maximum frosted modals/overlays

---

## Technical Debt: Hardcoded Hex Values in Components

**Scope:** 83+ component files bypass the design token system with raw hex values.
**Impact:** Color changes require multi-file search-and-replace instead of single token update.
**Priority:** Fix in Phases 2-6 during component redesign.

| Hardcoded Value | Appears In | Should Map To | Phase |
|-----------------|------------|---------------|-------|
| `#2a2e39` | AccountsTable, AddAccountForm, EnhancedAccountCard, HeatmapChart, progress.tsx, settings, portfolio | `--to-border` family or new `--to-surface-inverse` | 2-6 |
| `#1e222d` | AccountsTable, AddAccountForm, TrailingStopDialog | Needs new `--to-surface-input` token (between surface and surface-raised) | 2 |
| `#26a69a` | EnhancedAccountCard, AccountsTable, HeatmapChart | TradingView teal-green — distinct from `--to-long` (#0ecb81). May be intentional for chart compatibility. Investigate in Phase 2. | 2 |
| `#ef5350` | EnhancedAccountCard, AccountsTable, HeatmapChart, AlertRulesPanel | TradingView pure-red — distinct from `--to-short` (#f6465d). Same chart compatibility question. | 2 |
| `#0d1117` | toast.tsx (background) | `--to-surface` — already a token, component not consuming it | 2 |
| `#f6465d` | toast.tsx, prop-firm components | `--to-accent-red` / `--to-error` | 2-6 |
| `#f0b90b` | toast.tsx, various | `--to-accent-amber` / `--to-warning` | 2-6 |
| `#3b82f6` | LiveMarketPanel, various | `--to-accent-blue` / `--to-info` | 2-6 |
| `#0ecb81` | Various | `--to-accent-green` / `--to-success` | 2-6 |
| `#8b5cf6` | Various | `--to-accent-purple` | 2-6 |
| `#2962ff` | progress.tsx | Blue accent — `--to-accent-blue` (different shade, verify intent) | 2 |
| `#0b0e11`, `#131722`, `#1a1d24` | TraceDrawer, TrailingStopDialog, AddAccountForm | Near-black variants — `--to-bg` or new `--to-surface-deep` | 2 |

### Open Question for Phase 2
`#26a69a` (TradingView teal-green) and `#ef5350` (TradingView pure-red) may be intentional for
chart/DOM compatibility with TradingView widget color conventions. Phase 2 should investigate whether
these should become `--tv-green` / `--tv-red` tokens or be replaced with `--to-long` / `--to-short`.
Do not assume they are accidental drift.

---

## Validation

- Build: `cd frontend && npx next build` — must exit 0 after Phase 1
- Token presence: `grep -c "^  --" frontend/src/app/globals.css` — count increased vs. pre-Phase 1
- No values in @theme inline: all `--color-*` entries in @theme inline block must contain `var()` references, never raw values

---
*Phase 1 complete. Next: Phase 2 — Core Component Library will replace hardcoded hex values listed above.*
