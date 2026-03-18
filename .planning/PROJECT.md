# Trading Bot — Prop Firm Dashboard Upgrade

## What This Is

A production trading bot that receives signals from TradingView Pine Script, validates them through an AI council, executes trades on MT5 via MetaAPI, and tracks positions in Supabase. The current milestone upgrades the Accounts page to show real-time prop firm challenge progress — auto-detected from the MT5 account's broker server name, with no manual rule configuration required.

## Core Value

Each connected MT5 account automatically shows its prop firm challenge status (drawdown consumed, profit progress, days traded) in real-time — the trader sees exactly where they stand against the rules without leaving the dashboard.

## Requirements

### Validated

- ✓ Signal reception from TradingView webhooks — existing
- ✓ AI council validation before execution — existing
- ✓ MT5 trade execution via MetaAPI — existing
- ✓ Position tracking with broker reconciliation — existing
- ✓ Analytics page with trade breakdown and session metrics — existing
- ✓ Risk engine: VaR, sector limits, position sizing, drawdown guard — existing
- ✓ Accounts page showing balance, PnL, and strategy allocation — existing
- ✓ Basic prop firm page (daily PnL, equity curve, aggregate stats) — existing (`api_funding.py`)

### Active

- [ ] Auto-detect prop firm from MT5 account broker server name (e.g., `FTMO-Server3` → FTMO)
- [ ] One-time challenge type setup per account (Phase 1 / Phase 2 / Funded) — saved to DB, never asked again
- [ ] Internal prop firm rules database (daily DD %, total DD %, profit target %, min trading days)
- [ ] FTMO rules seeded at launch; architecture supports adding more firms without code changes
- [ ] Real-time prop firm metrics embedded in each account card (auto-refresh)
- [ ] Daily drawdown progress bar with current % vs limit
- [ ] Total drawdown progress bar with current % vs limit
- [ ] Profit target progress bar with current % vs target
- [ ] Trading days counter with minimum required
- [ ] Alert/warning banner when any metric reaches 80% of its limit

### Out of Scope

- Other prop firms at launch (The5ers, FundedNext, E8) — deferred; architecture supports them, data not seeded yet
- Prop firm dashboard API integration — most firms don't expose public APIs; rules sourced from internal DB
- Email/push notifications — dashboard banner only for 80% alerts
- Auto-pause trading on rule breach — risk engine handles this separately

## Context

- MetaAPI already fetches full account metadata on connection, including `server` field (e.g., `FTMO-Server2`)
- Daily PnL data already tracked via `portfolio_snapshots` and `api_funding.py` — metrics computation can build on this
- The existing prop firm page (`/api/v1/funding/*`) is a candidate for merge/consolidation
- Account cards already exist in the frontend — prop firm metrics will be embedded inside existing card layout
- DB: Supabase (PostgreSQL); new table needed for `prop_firm_rules` (firm + challenge_type → rules JSON)

## Constraints

- **MetaAPI dependency**: Prop firm detection relies on server name strings — must handle unknown/unrecognized servers gracefully (show "Unknown firm", don't crash)
- **Real-time polling**: Match existing positions page pattern (5s interval) — no new WebSocket infrastructure
- **DB migrations**: Follow existing numbered migration pattern (`migrations/0XX_*.sql`)
- **Frontend**: React + existing design system — match current card styling, no new UI libraries

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Auto-detect firm from server name | No user input needed; MetaAPI already has this data | — Pending |
| Internal rules DB instead of firm APIs | Firms don't expose public APIs; rules are stable, rarely change | — Pending |
| Embed metrics in account card | User chose this layout — avoids page navigation to see challenge status | — Pending |
| FTMO-only at launch | Scope control; same DB schema works for all firms | — Pending |
| Alert at 80% threshold | Gives early warning without being noise; standard risk practice | — Pending |

---
*Last updated: 2026-03-18 after initialization*
