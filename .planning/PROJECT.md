# Trinity Trading System — UI Redesign

## What This Is

A fully redesigned AI-powered prop firm trading bot dashboard. The system is production-ready with signals, execution, risk management, and analytics — now with a premium dark fintech frontend applied uniformly from a custom design system.

## Core Value

Every screen must look and feel like a premium fintech product — premium dark aesthetic, mobile-first responsive layout, cohesive design language applied uniformly from a single design system.

## Requirements

### Validated

- ✓ Dashboard with live signal feed and WebSocket status — existing
- ✓ Positions page with open trades and PnL tracking — existing
- ✓ Analytics page with trade history and performance metrics — existing
- ✓ Risk monitor with daily PnL, drawdown, circuit breakers — existing
- ✓ Prop firm challenge tracking (FTMO-style metrics) — existing
- ✓ Alerts system — existing
- ✓ Execution quality / TCA metrics — existing
- ✓ Backtest lab — existing
- ✓ Rules engine UI — existing
- ✓ AI Copilot chat interface — existing
- ✓ Settings page — existing
- ✓ Kanban board for agent tasks — existing
- ✓ New design system: CSS custom properties for color tokens, typography scale, spacing scale — v1.0
- ✓ Premium dark theme: deep backgrounds, subtle gradients, glass/frosted effects on cards — v1.0
- ✓ Mobile-first responsive layout: all pages fully usable on phone (full control, not read-only) — v1.0
- ✓ Cohesive color palette: strong accent color, semantic colors (profit/loss/warning/neutral) — v1.0
- ✓ Consistent typography: clear hierarchy, readable at small sizes — v1.0
- ✓ Polished component library: buttons, cards, tables, badges, inputs — all consistent — v1.0
- ✓ Dashboard redesign: eye-catching hero section, live data that feels alive — v1.0
- ✓ Risk/Prop Firm redesign: high-priority pages with clear metric hierarchy — v1.0
- ✓ Navigation redesign: mobile-friendly nav (bottom nav bar on mobile) — v1.0
- ✓ Smooth micro-interactions: loading states, transitions, number animations — v1.0

### Active

*(Fresh milestone — add v1.1 requirements with `/gsd-new-milestone`)*

### Out of Scope

- Backend changes — frontend-only
- New features or data — redesign existing screens, no new functionality
- Light mode — dark only by design decision
- Third-party component library swap — extend shadcn/ui + Tailwind 4.x (already in stack)

## Context

**Stack:** Next.js 16 + React 19 + Tailwind CSS 4.x + shadcn/ui (Radix UI primitives)

**Current state (v1.0 shipped):** Full design system deployed. 98 `tv-card` → `glow-card` replacements across 49 files (pages + components). Zero legacy card classes remaining. DataTable mobile scroll (min-w-max). All 14 pages have animate-fade-in-up entry animations. TypeScript: 0 errors throughout entire redesign.

**Timeline:** 2026-02-19 → 2026-03-20 (29 days) · 471 files changed · 84,778 insertions · 8 phases · 12 plans

**Usage pattern:** Owner monitors and controls the bot on mobile while away from desk. Dashboard and Risk/Prop Firm are the most-used pages.

## Constraints

- **Tech stack:** Must stay with Next.js + Tailwind CSS 4.x + shadcn/ui — no framework changes
- **Backend contract:** No API shape changes — frontend only
- **Functional parity:** All existing functionality must be preserved through the redesign

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------| 
| Dark theme only | Trader preference, fits domain, faster to build well | ✓ Confirmed |
| Extend shadcn/ui rather than replace | Already in stack, Radix primitives are accessible | ✓ Confirmed |
| Mobile-first approach | Owner needs full control on phone | ✓ Confirmed |
| Design system first, then pages | Ensures coherence across all pages | ✓ Confirmed |
| Premium fintech aesthetic (glass/gradients) | User wants eye-catching, not minimal | ✓ Confirmed |
| `glow-card` system-wide (not mixed) | Consistency > nuance at this scale | ✓ Good — clean result |
| Hero CompositeRiskScore (A) over side column | Full-width hero with severity theming is far more impactful | ✓ Good |
| Class-swap only for large pages (A) | Pages 613-928 lines — low risk, high speed, correct call | ✓ Good |
| DataTable min-w-max for mobile scroll | overflow-auto exists but needs min-w-max to trigger at 360px | ✓ Confirmed pattern |
| Phase 6+7 caught component gap | Phase 6 only swept pages — 40 components still had tv-card; Phase 7 found and swept them | ⚠️ Lesson: sweep components AND pages together next time |

---
*Last updated: 2026-03-20 after v1.0 milestone complete*
