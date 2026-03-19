# Trinity Trading System — UI Redesign

## What This Is

A complete UI overhaul of an existing AI-powered prop firm trading bot dashboard. The system is fully functional (signals, execution, risk management, analytics all work) but the frontend is visually inconsistent, non-responsive, and lacks professional polish. This milestone redesigns the entire frontend from a new design system foundation.

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

### Active

- [ ] New design system: CSS custom properties for color tokens, typography scale, spacing scale
- [ ] Premium dark theme: deep backgrounds, subtle gradients, glass/frosted effects on cards
- [ ] Mobile-first responsive layout: all pages fully usable on phone (full control, not read-only)
- [ ] Cohesive color palette: strong accent color, semantic colors (profit/loss/warning/neutral)
- [ ] Consistent typography: clear hierarchy, readable at small sizes
- [ ] Polished component library: buttons, cards, tables, badges, inputs — all consistent
- [ ] Dashboard redesign: eye-catching hero section, live data that feels alive
- [ ] Risk/Prop Firm redesign: high-priority pages with clear metric hierarchy
- [ ] Navigation redesign: mobile-friendly nav (bottom nav bar on mobile)
- [ ] Smooth micro-interactions: loading states, transitions, number animations

### Out of Scope

- Backend changes — this is frontend-only
- New features or data — redesign existing screens, no new functionality
- Light mode — dark only by design decision
- Third-party component library swap — extend shadcn/ui + Tailwind 4.x (already in stack)

## Context

**Stack:** Next.js 16 + React 19 + Tailwind CSS 4.x + shadcn/ui (Radix UI primitives)

**Current state:** Frontend exists and works. Colors are inconsistent (mix of hardcoded hex values, some CSS variables). No unified spacing or typography system. Components look inconsistent across pages. Does not work well on mobile — layout breaks on small screens.

**Previous design work:** A token standardization pass was done (commits reference 950 hardcoded colors replaced with design tokens), but the tokens themselves were not redesigned — just moved. The visual output is still inconsistent.

**Usage pattern:** Owner monitors and controls the bot on mobile while away from desk. Dashboard and Risk/Prop Firm are the most-used pages. Full control (not just read-only) required on mobile.

## Constraints

- **Tech stack:** Must stay with Next.js + Tailwind CSS 4.x + shadcn/ui — no framework changes
- **Backend contract:** No API shape changes — frontend only
- **Functional parity:** All existing functionality must be preserved through the redesign

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dark theme only | Trader preference, fits domain, faster to build well | — Pending |
| Extend shadcn/ui rather than replace | Already in stack, Radix primitives are accessible | — Pending |
| Mobile-first approach | Owner needs full control on phone | — Pending |
| Design system first, then pages | Ensures coherence across all pages | — Pending |
| Premium fintech aesthetic (glass/gradients) | User wants eye-catching, not minimal | — Pending |

---
*Last updated: 2026-03-19 after initialization*
