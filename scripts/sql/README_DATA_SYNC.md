# Data Sync and Account Name Fix

## Problem

If you see:
- History tab shows trades but Performance shows 0% win rate / 1 total trade
- Analytics shows "No trade data yet"
- Overview shows incorrect metrics

This usually means your `trading_signals` table has trades with `broker_profile_id` but no `account_name` set.

## Quick Fix (Automatic Fallback)

**The backend now automatically queries by `broker_profile_id` if no trades are found by `account_name`.**

After restarting your backend, the UI should show correct data even without running SQL scripts.

## Permanent Fix (Recommended)

To permanently fix your data and improve query performance:

### Step 0: Run Missing Migration (if you see "column does not exist" errors)

If you get errors like `ERROR: column "mae" does not exist`, you need to run this migration first:

```sql
-- Run migrations/020_add_execution_telemetry_columns.sql in Supabase SQL Editor
```

This adds columns the backend expects: `exit_time`, `exit_price`, `entry_time`, `pnl_usd`, `mae`, `mfe`, `exit_reason`.

### Step 1: Diagnose

Run `diagnose_account_data.sql` in Supabase SQL Editor to see:
- What `account_name` values exist
- How many trades have NULL `account_name`
- Which accounts are configured

### Step 2: Backfill

Run `backfill_account_name.sql` in Supabase SQL Editor to:
- Set `account_name` on all trades that have `broker_profile_id` but NULL `account_name`
- This permanently fixes the data so future queries are faster

### Step 3: Verify

Refresh your UI and check:
- Overview shows correct Total Trades count
- Performance Summary shows accurate Win Rate, Profit Factor
- Analytics tabs show per-pair data and charts
- History tab shows MAE, Exit Time, etc.

## Files

- `diagnose_account_data.sql` - Query to inspect current data state
- `backfill_account_name.sql` - Script to permanently fix NULL account_names
- `reset_database.sql` - Wipe all data and start from scratch (nuclear option)

## When to Use Each Script

| Script | When to Use | Effect |
|--------|-------------|--------|
| `diagnose_account_data.sql` | Any time you suspect data issues | Read-only, shows what's in your DB |
| `backfill_account_name.sql` | After adding new accounts or migrating data | Updates NULL account_name values |
| `reset_database.sql` | Starting bot testing from scratch | **DESTRUCTIVE**: Deletes all trade/position data |
