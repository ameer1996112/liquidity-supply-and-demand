# PnL & Metrics Sync Fix

## What This Is

A data synchronization project for the Next.js trading dashboard to ensure that Live PnL, Historical PnL, Account Balance, Margin, and Daily Drawdown perfectly match the real data from MetaTrader (via MetaApi). The fix will correct both past existing signals and future active signals so the dashboard provides an accurate source of truth reflecting the broker's numbers.

## Core Value

The dashboard metrics must be 100% accurate and perfectly synchronized with MetaTrader's actual numbers. A trading dashboard with incorrect PnL cannot be trusted by traders.

## Requirements

### Validated

- ✓ Ingest TradingView webhook signals
- ✓ Execute trades via MetaApi worker
- ✓ Display signals and trade state on the dashboard
- ✓ Sync basic position state to Supabase

### Active

- [ ] Fix Live PnL showing `0.00` on the dashboard for active trades
- [ ] Fix the calculation/sync logic for Historical PnL so it exactly matches MetaTrader (including swaps, commissions, slippage)
- [ ] Synchronize other account metrics (Account Balance, Margin, Daily Drawdown) with MetaTrader
- [ ] Build a retroactive script/process to repair the discrepancies in historical signal data already existing in Supabase

### Out of Scope

- [New trading logic/strategies] — This project is strictly about data accuracy, UI display, and backend sync logic, not changing the algorithms making the trades.

## Context

The current system has existing logic to sync positions to Supabase and show them in Next.js. However, Live PnL is currently broken (showing 0.00) and historical PnL frequently has mismatches (dashboard vs MT), often due to partial closes or uncaptured swap/commission numbers. Since the system is brownfield, several scripts already exist (e.g. `verify_pnl_db.py`, `cleanup_stale_positions.py`) indicating prior sync work that needs to be unified or fully debugged.

## Constraints

- **Accuracy**: Data must exactly match MetaTrader 1:1.
- **Tech Stack**: Must use the existing Next.js, FastAPI, and MetaApi Worker structure. 

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Include overall metrics (Balance, Drawdown) alongside PnL | If PnL is wrong, account-level metrics are usually affected too | — Pending |

---
*Last updated: 2026-03-25 after initialization*
