---
created: 2026-03-23T17:16:20.551Z
title: Fix the signal dashboard display bug
area: frontend
ticket_id: ""
files:
  - frontend/src/components/LatestSignals.tsx
---

## Problem

The "Latest Signals" component on the trading dashboard is not displaying any signals. The component renders an empty state even though trading signals exist in the database. This was identified during earlier debugging (conversation b3e62cc1) — the signals fetch may have a broken query, wrong status filter, or a rendering condition that causes the list to appear empty.

## Solution

1. Inspect the Supabase query in `LatestSignals.tsx` — check the status filter and date range
2. Verify the API response contains signals (compare with `/api/signals` endpoint)
3. Fix any rendering condition guards that prevent signals from displaying
4. Validate PNL data alignment with MetaTrader positions
