---
created: 2026-03-25T17:41:30Z
title: Support dynamic MetaAPI regions per broker profile
area: api
ticket_id: ""
files:
  - src/services/account_sync_service.py
  - src/adapters/execution/meta_api_adapter.py
  - migrations/XXX_add_meta_api_region.sql
---

## Problem

ALL accounts currently use the `META_API_REGION` env var (defaulting to london). This causes HTTP 504 timeouts when querying `/account-information` for accounts hosted on `new-york` or `singapore` regions via MetaApi. The `AccountSyncService` fails to fetch live balances for these cross-region accounts because it does not know their region to fetch correctly.

## Solution

1. Add a `meta_api_region` column to the `broker_profiles` table via a SQL migration.
2. Update `AccountSyncService._get_adapter_for_account` to query this column.
3. Pass the extracted region explicitly to `MetaApiAdapter` so it routes to the correct MetaApi cluster.
