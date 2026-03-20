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

## Current Milestone: v1.0 Premium Dark Trading Terminal

**Goal:** Complete UI overhaul — premium dark fintech aesthetic, mobile-first responsive layout, cohesive design system applied uniformly across all pages.

**Target features:**
- Design system foundation (tokens, typography, spacing)
- Core component library (buttons, cards, tables, badges, inputs)
- Navigation redesign (desktop sidebar + mobile bottom nav)
- Dashboard redesign (hero metrics, live signal feed)
- Risk & Prop Firm redesign (metric hierarchy, visual gauges)
- Remaining pages redesign (positions, analytics, accounts, etc.)
- Responsive polish (all pages usable on 320px-480px)
- Micro-interactions (skeletons, transitions, number animations)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dark theme only | Trader preference, fits domain, faster to build well | ✓ Confirmed |
| Extend shadcn/ui rather than replace | Already in stack, Radix primitives are accessible | ✓ Confirmed |
| Mobile-first approach | Owner needs full control on phone | ✓ Confirmed |
| Design system first, then pages | Ensures coherence across all pages | ✓ Confirmed |
| Premium fintech aesthetic (glass/gradients) | User wants eye-catching, not minimal | ✓ Confirmed |
| Skip research for v1.0 | Redesign of existing screens, no new domain | ✓ Confirmed |

---
*Last updated: 2026-03-19 after milestone v1.0 initialization*
