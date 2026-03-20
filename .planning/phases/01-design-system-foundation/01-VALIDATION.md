---
phase: 1
slug: design-system-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | next build (CSS compilation) + manual browser DevTools |
| **Config file** | frontend/next.config.ts |
| **Quick run command** | `cd frontend && npx next build 2>&1 | tail -20` |
| **Full suite command** | `cd frontend && npx next build` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx next build 2>&1 | tail -5` (confirm no CSS errors)

---

## Validation Gates

### Wave 1: Token Definitions
- `globals.css` contains `--text-xs` through `--text-4xl` in `:root`
- `globals.css` contains `--to-space-1` through `--to-space-16` in `:root`
- `globals.css` contains `--to-success`, `--to-info`, `--to-error` in `:root`
- `@theme inline` block maps all new tokens to Tailwind utilities
- `npx next build` exits 0 with no CSS errors

### Wave 2: Glass & Effect Tokens
- `glass-panel-subtle` and `glass-panel-strong` CSS classes defined in globals.css
- `--gradient-surface`, `--gradient-card`, `--gradient-accent` defined in `:root`
- All glow tokens (`--glow-*`) present and referenced by utility classes

### Wave 3: Documentation
- `TOKEN-AUDIT.md` exists at `.planning/phases/01-design-system-foundation/TOKEN-AUDIT.md`
- TOKEN-AUDIT.md lists all `--to-*` tokens with descriptions
- TOKEN-AUDIT.md documents 83+ hardcoded hex values as technical debt for Phases 2-6

---

## Human Verification Items

1. Open browser DevTools on the running frontend — confirm `var(--text-base)` resolves to a pixel value (not empty string)
2. Confirm `var(--to-space-4)` resolves to `1rem` (16px)
3. Confirm `var(--to-success)` resolves to a green color value
4. Verify `glass-panel-subtle` applies a visually lighter blur than `glass-panel`
