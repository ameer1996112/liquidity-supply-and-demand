# Trading Bot — Institutional Liquidity Journal

## What This Is

An institutional-grade algorithmic trading bot for MetaTrader accounts via MetaAPI. The system receives TradingView webhook signals, runs AI/ML guardrails, executes trades, and persists results to Supabase. The Next.js frontend provides a real-time dashboard for monitoring signals, risk, and trade outcomes — including a Trade Journal for post-trade analysis.

## Core Value

Every closed trade is visible, analyzable, and actionable directly from the journal — giving the trader total clarity on performance without external tools.

## Requirements

### Validated

- ✓ Webhook signal reception, validation, and queuing — v1
- ✓ AI/ML guardrail pipeline (LLM Guardian, ML Guardian, Trinity) — v1
- ✓ MetaAPI trade execution (LIVE + PAPER modes) — v1
- ✓ Real-time dashboard with signal feed and risk monitoring — v1
- ✓ Basic Trade Journal (table view, calendar view, CSV export, pattern insights) — v1
- ✓ Journal stats bar (PnL, win rate, profit factor, avg R:R, expectancy) — v1.1
- ✓ Equity curve chart in journal — v1.1
- ✓ Period filter (7D / 30D / 90D / All) in journal — v1.1
- ✓ Duration column in trade table — v1.1

### Active

- [ ] Per-account performance breakdown in journal
- [ ] Trade annotations / inline notes improvement
- [ ] Journal mobile view optimization
- [ ] Symbol-level performance breakdown table
- [ ] Max drawdown visualization (underwater chart)

### Out of Scope

- Mobile native app — web-first, mobile-responsive later
- Multi-user auth / team accounts — single operator system
- TradingView chart embedding — external tool, not in scope
- Manual trade entry without a signal — bot-only workflow

## Context

- Codebase is brownfield — full architecture documented in `.planning/codebase/`
- Frontend: Next.js 16, React 19, Tailwind v4, recharts for charts
- `TradingSignal` type has ~60 fields; journal must handle `null` gracefully
- PnL/exit_price only populated for closed trades — `status: closed | executed`
- Trade notes stored in `localStorage` via `TradeNoteEditor` (not Supabase yet)
- Pattern analysis and calendar view already working; equity curve just added

## Constraints

- **Tech stack**: No new npm packages without strong justification — recharts + @tanstack already present
- **Data**: All data from Supabase `trading_signals` table via existing `fetchSignals`
- **Performance**: Journal fetches up to 1000 signals; client-side filtering only
- **Compatibility**: Must compile clean (`tsc --noEmit` zero errors)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Client-side period filter (not DB query) | Avoids extra round-trips; 1000 signals is fast enough | ✓ Good |
| Trade notes in localStorage | Avoids DB schema change; acceptable for single-user | — Pending revisit |
| recharts for equity curve | Already a dependency; no new packages needed | ✓ Good |

---
*Last updated: 2026-03-21 after v1.1 journal overhaul*
