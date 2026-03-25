# Design Spec: Multi-Account Dashboard Upgrade

## Overview
Currently, the main trading dashboard displays global metrics, and the Accounts manager page lists accounts but doesn't show rich charts/KPIs. This upgrade implements a unified multi-account interface. The dashboard will gain the ability to filter by account, and the dedicated Account detail page will reuse the rich dashboard components.

## Goals
- Allow filtering by account (Global vs Specific Account) directly on the main dashboard using quick-switch tabs.
- Re-use the complex dashboard layout (Signal Table, StatCards, KPIs, Active Trades) on the `/accounts/[account_name]` detail pages.

## Architecture
### 1. DashboardView Component Extraction
- The contents of `frontend/src/app/page.tsx` will be extracted into a reusable `<DashboardView accountId={accountId} />` component.
- This prevents duplicating 700 lines of complex UI state, hooks, and responsive grids into the Accounts page.
- `page.tsx` will be refactored to mount the new account picker tabs above the `<DashboardView>`.

### 2. Accounts Overview Integration
- In `frontend/src/app/accounts/[account_name]/page.tsx`, the existing `OverviewTab` will be completely replaced.
- It will simply mount `<DashboardView accountId={accountName} />`.
- This ensures the dedicated account page always perfectly matches the main Dashboard's visual fidelity and capabilities.

### 3. Data Fetching Layer (Hooks & API)
- React Query hooks (`useSignalStats`, `useTradingSignals`, `useActivePositions`, `useRiskStatus`, `useRiskMonitor`) will be updated to accept an optional `accountId` string parameter.
- The hooks will append `?account_id=${accountId}` (or `?account_name=${accountId}`) to their backend API requests.
- The FastAPI backend endpoints must support this filter parameter. If they do not natively filter by account already, that capability must be explicitly implemented so that stats (Win Rate, Daily DD, Live PnL) are accurately scoped to the given account rather than the global state.

## Security & Error Handling
- The `<DashboardView>` must fail gracefully when switching to an account that has no recent signals, showing the familiar "Bot is waiting for..." banner.
- Filtering by account must ensure no mixing of sensitive Prop Firm vs Personal account metrics on the backend.
