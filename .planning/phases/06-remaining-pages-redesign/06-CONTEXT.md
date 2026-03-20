# Phase 6: Remaining Pages Redesign — Context

**Phase:** 06
**Date:** 2026-03-20
**Status:** CONTEXT CAPTURED

## Phase Goal
Apply design system consistently to all remaining pages by replacing legacy `tv-card` with `glow-card`.

## User Decisions

### Area 1: Replacement card class → **A (glow-card everywhere)**
All `tv-card` occurrences replaced with `glow-card` — consistent with dashboard, risk, and prop-firm.

### Area 2: Large files approach → **A (class swap only)**
Replace `tv-card` with `glow-card` only, no JSX restructuring.

## Pages Modified (9 files)
- `accounts/page.tsx` — 1 tv-card
- `accounts/[account_name]/page.tsx` — 1 tv-card
- `analytics/page.tsx` — 6 tv-cards
- `positions/page.tsx` — 3 tv-cards
- `journal/page.tsx` — 2 tv-cards
- `backtest/page.tsx` — 7 tv-cards
- `execution-quality/page.tsx` — 8 tv-cards
- `scanner/page.tsx` — 1 tv-card
- `strategies/page.tsx` — 2 tv-cards

## No-Change Pages (4 files)
- `alerts/page.tsx`, `board/page.tsx`, `rules/page.tsx`, `settings/page.tsx` — 0 tv-card, already using design tokens
