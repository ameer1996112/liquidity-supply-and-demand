---
created: 2026-03-25T12:48:57.818Z
title: Add configurable per-trade PnL display mode on dashboard
area: ui
ticket_id: "DEV-43"
files:
  - frontend/src/components/SignalsTable.tsx
  - frontend/src/components/Dashboard.tsx
---

## Problem

The dashboard signals table shows per-trade PnL as **true net** (profit minus all commissions). MetaTrader shows profit-per-deal only with commission as a separate line item. This causes a visible mismatch between the dashboard and MT, even though the **Total PnL** is correct (e.g., USDJPY 9.22 lots shows +41.09 on dashboard vs +87.19 in MT — the $46.10 difference is the commission).

User was asked to decide between two modes and did not yet respond:
1. **Current (net per trade)** — correct total, looks different from MT per-trade numbers
2. **MT-style (gross profit per trade)** — matches MT per-trade, but total PnL won't match balance change

## Solution

Add a toggle or setting on the signals/trades table to switch between:
- **Net mode**: `pnl = profit - commission` (current behavior, total is correct)
- **Gross mode**: `pnl = profit only` (matches MetaTrader display, commission shown separately or in tooltip)

Ideally expose this as a small UI toggle (e.g., "Net / Gross" pill button) near the PnL column header, persisted in localStorage. The total PnL card should always show net regardless of mode.
