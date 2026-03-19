# Liquidity Supply & Demand — Trading Bot Dashboard

## What This Is

An institutional-grade algorithmic trading bot that receives TradingView webhook signals, filters them through an AI/ML guardrail pipeline (LLM ensemble + LightGBM), and executes trades on live MetaTrader 5 accounts via MetaAPI. A Next.js dashboard provides real-time monitoring of signals, positions, risk, analytics, and prop firm challenge tracking — used by a single trader operating multiple broker accounts.

## Core Value

**The trader must always know what the bot is doing in real-time** — signal flow, live positions, risk exposure, AI decisions, and prop firm limits — through a single premium dashboard.

## Requirements

### Validated

- ✓ Webhook signal ingestion from TradingView — existing
- ✓ AI/ML guardrail pipeline (AI Guardian + ML Guardian + Trinity) — existing
- ✓ Multi-broker execution via MetaAPI (Vantage Forex + FXCM/IC Markets metals) — existing
- ✓ Real-time signal feed via Supabase Realtime — existing
- ✓ Prop firm challenge tracking (FTMO phases + daily loss limits) — existing
- ✓ Risk monitoring (portfolio VaR, correlation, sector exposure) — existing
- ✓ Execution quality traces (TCA, slippage, latency) — existing
- ✓ Analytics dashboard (win rate, P&L, drawdown) — existing
- ✓ Account management (multi-account, prop firm auto-detection) — existing
- ✓ Next.js App Router frontend with Supabase auth — existing

### Active

- [ ] Complete visual redesign — premium dark pro trading terminal aesthetic across all pages
- [ ] Consistent design system — unified color palette, typography, spacing, component library
- [ ] Optimized data loading — React Query with smart caching, skeleton states, no layout shift
- [ ] Real-time indicators — live connection status, price streaming indicators, last-update timestamps
- [ ] Responsive layout — sidebar navigation with collapsible sections, consistent page structure
- [ ] Dashboard page — command-center layout with signal feed, live P&L, risk snapshot, AI status
- [ ] Signal Inspector — detailed signal card with guardrail pass/fail breakdown and AI rationale
- [ ] Positions page — live position table with unrealized P&L, heat-coloring, quick-close actions
- [ ] Risk page — visual risk meters (daily loss %, drawdown %, VaR), color-coded thresholds
- [ ] Analytics page — performance charts (equity curve, win rate by symbol/session), heatmaps
- [ ] Execution Quality page — trace timeline, latency breakdown, slippage chart
- [ ] Prop Firm page — challenge progress bars, daily limit gauge, consistency tracker
- [ ] Accounts page — account cards with balance, equity, prop firm phase badges
- [ ] Settings & Strategies — clean form layouts for bot configuration
- [ ] Navigation — persistent sidebar with status indicators, keyboard shortcuts

### Out of Scope

- Backend API changes — this milestone is frontend-only (backend stays as-is)
- Mobile app — desktop browser only (single user, trading desk context)
- New features — redesign existing pages, do not add new capabilities in this milestone
- Multi-tenant / client-facing redesign — built for solo operator use

## Context

### Current State
- 15+ pages built with Next.js App Router, Tailwind CSS, Radix UI / shadcn/ui
- Main dashboard (`app/page.tsx` — 22KB) is the heaviest page
- Data fetched via React Query + Supabase Realtime subscriptions
- Pre-existing ESLint warnings and 1 Vitest test failure (baseline, not regressions)
- Design is functional but inconsistent — colors, spacing, and component patterns vary across pages

### Target Aesthetic
- **Dark pro trading terminal** — deep dark backgrounds (`#0a0b0d`, `#0f1117`), not pure black
- **Accent:** Electric blue/cyan (`#00d2ff`, `#3a7bd5`) for active states, key metrics
- **Danger/profit:** Red (`#ff4757`) / Green (`#2ed573`) for P&L coloring
- **Typography:** Inter or Geist — clean, highly legible, monospace for prices/numbers
- **Cards:** Subtle glass-morphism — `bg-white/5 backdrop-blur border border-white/10`
- **Charts:** Dark-themed with glowing line/area fills
- **Motion:** Micro-animations on data updates, smooth page transitions, skeleton loading

## Constraints

- **Tech Stack:** Must stay on Next.js 15 + Tailwind CSS + shadcn/ui + Radix UI — no framework swap
- **API Contract:** All API calls to FastAPI backend remain identical — only presentation changes
- **Auth:** Supabase auth integration must remain intact
- **Tests:** Existing tests must not regress beyond current baseline
- **Build:** `npm run build` must pass without new errors

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dark terminal aesthetic | Single trader, trading desk context — high data density matters more than "friendly" | — Pending |
| Keep shadcn/ui + Tailwind | Already in codebase, avoid thrash, extend the system rather than replacing it | — Pending |
| Page-by-page redesign phases | Too risky to rewrite all pages at once — phase by feature area | — Pending |
| Monospace for prices/numbers | Industry standard for trading UIs — improves scan-ability | — Pending |

---
*Last updated: 2026-03-19 after project initialization*
