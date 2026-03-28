# Design: Dashboard & Accounts Page Cleanup

**Date:** 2026-03-28  
**Status:** Approved by user

---

## Problem

The main dashboard is crowded because it tries to be everything:
- Full account cards (balance, equity, drawdown, sparkline)
- Open positions table
- Signals table
- Live log
- **AccountDrawer** — a slide-out that duplicates the entire `/accounts/[name]` detail page (same 6 tabs: Overview, Positions, History, Analytics, Journal, Challenge, Settings)

The Accounts page (`/accounts`) shows only the credential manager (`BrokerProfilesPanel`), with no overview of account performance.

This creates **two identical paths** to account detail data, and a dashboard that is impossible to scan at a glance.

---

## Approved Design

### 3-Level Hierarchy

| Level | Page | Purpose |
|-------|------|---------|
| 1 | Dashboard `/` | Live trading monitor — signals, positions, compact account strip |
| 2 | Accounts `/accounts` | Account overview — rich cards with key metrics, navigate to detail |
| 3 | Account Detail `/accounts/[name]` | Full deep-dive — 6 tabs, unchanged |

---

### Main Dashboard (simplified)

**Remove:** `AccountGrid` (full cards with sparklines, drawdown bars, etc.)  
**Remove:** `AccountDrawer` (entire component and all its wiring)  
**Add:** `AccountStrip` — a compact table-like list of accounts showing:
  - Account name (monospace, bold)
  - Connection dot (green = connected, yellow = disconnected, red = error)
  - Status label (Connected / Disconnected / Error)
  - Balance (single number, dim colour)
  - Clicking a row navigates to `/accounts/[name]`

Layout: the strip sits where the AccountGrid was, between the status banners and the OpenPositionsTable. It is intentionally minimal — scan and move on.

---

### Accounts Page (enriched)

**Remove:** the lone `BrokerProfilesPanel` as the only content  
**Add:** `AccountOverviewList` — rich cards per account showing:
  - Account name + type badge (Personal / Eval / Funded)
  - Connection status dot + label
  - Balance, Equity, Daily P&L (with colour)
  - Open positions count
  - Prop firm name (if applicable)
  - "Manage Credentials" button → opens the existing `BrokerProfilesPanel` in a modal/collapsible below
  - Clicking the card → navigates to `/accounts/[name]`

The `BrokerProfilesPanel` (credential management) is demoted from "the whole page" to "a secondary action" on this page. It can live in a collapsible section at the bottom, or be triggered via a button.

---

### AccountDrawer — Deleted

The `AccountDrawer` component and all its parent wiring in `page.tsx` is removed entirely. Account detail is now accessed via `/accounts/[name]` only.

---

## Data Sources

- Account strip + account overview cards both use `useAccountsComparison()` hook (already returns `account_name`, `connection_status`, `balance`, `equity`, `daily_pnl`, `daily_pnl_pct`, `account_type`, `prop_firm_name`)
- No new API endpoints needed

---

## Files Changed

| File | Change |
|------|--------|
| `src/app/page.tsx` | Remove AccountGrid, AccountDrawer wiring; add AccountStrip |
| `src/components/dashboard/AccountStrip.tsx` | **NEW** — compact account list |
| `src/components/dashboard/AccountGrid.tsx` | Keep (still used elsewhere? If not, deprecate) |
| `src/components/dashboard/AccountDrawer.tsx` | **DELETE** |
| `src/app/accounts/page.tsx` | Replace BrokerProfilesPanel-only layout with AccountOverviewList |
| `src/components/accounts/AccountOverviewList.tsx` | **NEW** — rich account cards |
