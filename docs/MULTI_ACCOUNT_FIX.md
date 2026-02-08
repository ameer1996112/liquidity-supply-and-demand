# Multi-Account Trade Association Fix

## Problem
All MetaTrader trades are being associated with the FTMO demo account instead of their correct respective accounts.

## Root Cause
The code logic is **correct** - the issue is in database configuration. One of these scenarios is occurring:

1. All `account_strategies` rows point to the same `broker_profile_id`
2. All `broker_profiles` have the same `meta_api_account_id` (meaning you're actually trading one account)
3. Missing or NULL `broker_profile_id` linkages

## Diagnostic Steps

### 1. Run Diagnostic SQL

Execute the queries in `diagnose_accounts.sql` to identify the issue:

```bash
# Copy the SQL file to your clipboard, then run in Supabase SQL Editor
cat diagnose_accounts.sql
```

### 2. Analyze Results

**Query 5 is CRITICAL** - if it returns any rows, you have multiple profiles using the same MetaApi account!

Expected result (CORRECT):
```
meta_api_account_id | profile_count | profile_names
--------------------+--------------+--------------
(empty - no duplicates)
```

If you see duplicates:
```
meta_api_account_id      | profile_count | profile_names
-------------------------+--------------+--------------------------------
abc123-def456-ghi789     | 3            | FTMO Demo, Personal, Eval
```

**This means all three "accounts" are actually the SAME MetaApi account!**

---

## Fix Option 1: You Have Multiple REAL Broker Accounts

If you have multiple separate MetaTrader accounts (different broker logins):

### Step 1: Create separate broker profiles

```sql
-- Create a profile for each REAL broker account
INSERT INTO broker_profiles (name, meta_api_account_id, token_env_key, risk_pct, max_positions, run_mode, is_active)
VALUES
  ('FTMO Demo 50K', 'your-ftmo-metaapi-account-id', 'META_API_TOKEN', 0.5, 3, 'LIVE', true),
  ('Personal Account', 'your-personal-metaapi-account-id', 'META_API_TOKEN_PERSONAL', 0.5, 3, 'LIVE', true),
  ('Eval Challenge', 'your-eval-metaapi-account-id', 'META_API_TOKEN_EVAL', 0.5, 3, 'LIVE', true);
```

**CRITICAL:** Each row must have a **unique** `meta_api_account_id` (from MetaApi dashboard)

### Step 2: Update account_strategies linkage

```sql
-- Link each account strategy to its correct broker profile
UPDATE account_strategies
SET broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'FTMO Demo 50K' LIMIT 1)
WHERE account_name = 'FTMO - Demo - 50K';

UPDATE account_strategies
SET broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'Personal Account' LIMIT 1)
WHERE account_name = 'Personal Trading';

UPDATE account_strategies
SET broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'Eval Challenge' LIMIT 1)
WHERE account_name = 'Eval - Challenge';
```

### Step 3: Set environment variables

In your `.env` file:

```bash
# FTMO account
META_API_TOKEN=your-ftmo-token

# Personal account (different token or same token if sharing)
META_API_TOKEN_PERSONAL=your-personal-token

# Eval account
META_API_TOKEN_EVAL=your-eval-token
```

**NOTE:** If all accounts are under the same MetaApi subscription, they can share the token. The `meta_api_account_id` is what differentiates them.

---

## Fix Option 2: You Only Have ONE Real Account (Virtual Sub-Accounts)

If you only have **one** real MetaTrader/MetaApi account but want to manage it as multiple "virtual" accounts (capital allocation):

### Step 1: Create ONE broker profile

```sql
-- Create a single broker profile for the real account
INSERT INTO broker_profiles (name, meta_api_account_id, token_env_key, risk_pct, max_positions, run_mode, is_active)
VALUES ('Main Trading Account', 'your-metaapi-account-id', 'META_API_TOKEN', 0.5, 3, 'LIVE', true)
RETURNING id;
-- Note the returned ID (e.g., 1)
```

### Step 2: Link ALL account_strategies to the same profile

```sql
-- Link all "virtual" accounts to the same broker profile
UPDATE account_strategies
SET broker_profile_id = 1  -- Use the ID from Step 1
WHERE is_active = true;
```

### Step 3: IMPORTANT - This is the expected behavior!

**If you only have one real broker account, all trades WILL appear in all "accounts"**

This is correct! The "accounts" in `account_strategies` are for:
- Capital allocation planning
- Strategy assignment
- Performance comparison

But they all execute on the **same** physical broker account.

**To truly separate trades by account, you need separate MetaApi accounts (separate MT4/MT5 logins).**

---

## Fix Option 3: Separate by Strategy Instead

If you want to track trades separately without multiple broker accounts:

### Use the `strategy_type` field

```sql
-- Update account_strategies with different strategies
UPDATE account_strategies SET strategy_type = 'AGGRESSIVE' WHERE account_name = 'FTMO - Demo - 50K';
UPDATE account_strategies SET strategy_type = 'BALANCED' WHERE account_name = 'Personal Trading';
UPDATE account_strategies SET strategy_type = 'CONSERVATIVE' WHERE account_name = 'Eval Challenge';
```

Then modify the frontend to filter by `strategy_type` instead of `broker_profile_id`.

**However, this still won't separate actual trades - they'll all execute on the same account.**

---

## Verify the Fix

After applying your fix, run these checks:

### 1. Verify broker profiles are unique

```sql
SELECT
    id,
    name,
    meta_api_account_id,
    COUNT(*) OVER (PARTITION BY meta_api_account_id) as duplicate_count
FROM broker_profiles
WHERE is_active = true;
```

Expected: `duplicate_count = 1` for all rows

### 2. Verify account linkages

```sql
SELECT
    acs.account_name,
    acs.broker_profile_id,
    bp.name as broker_name,
    bp.meta_api_account_id
FROM account_strategies acs
JOIN broker_profiles bp ON acs.broker_profile_id = bp.id
WHERE acs.is_active = true;
```

Expected: Each account links to the correct broker profile

### 3. Test with a new trade

1. Send a test signal via TradingView
2. Check which accounts it appears in:

```sql
SELECT
    ts.id,
    ts.symbol,
    ts.broker_profile_id,
    ts.account_name,
    bp.name as broker_profile_name
FROM trading_signals ts
LEFT JOIN broker_profiles bp ON ts.broker_profile_id = bp.id
ORDER BY ts.created_at DESC
LIMIT 1;
```

3. Verify `broker_profile_id` matches the expected profile
4. Verify `account_name` is set correctly

---

## Understanding the Architecture

```
┌─────────────────────────────────────────────────────┐
│ account_strategies (Virtual Account Management)     │
│ - account_name: "FTMO Demo"                         │
│ - broker_profile_id: 1 ───┐                         │
│ - allocated_capital_usd: $50,000                    │
└────────────────────────────┼────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────┐
│ broker_profiles (Physical Broker Connections)       │
│ - id: 1                                             │
│ - name: "FTMO Account"                              │
│ - meta_api_account_id: "abc123..." (UNIQUE!)       │
│ - token_env_key: "META_API_TOKEN"                   │
└────────────────────────────┼────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────┐
│ MetaApi Cloud (Physical MT4/MT5 Accounts)          │
│ Account ID: abc123...                               │
│ ← Actual trades execute here                        │
└─────────────────────────────────────────────────────┘
```

**Key Points:**
1. One `broker_profile` = One physical MetaApi account
2. Multiple `account_strategies` can share one `broker_profile` (capital allocation)
3. Trades are linked via `broker_profile_id` in `trading_signals`
4. To separate trades physically, you need separate MetaApi accounts

---

## Expected Behavior After Fix

### If you have multiple REAL broker accounts:
- Each account shows only ITS trades
- Capital is allocated separately
- Performance tracked independently

### If you have one REAL broker account:
- All "accounts" show the same trades (correct!)
- Use for capital allocation planning only
- Consider using `strategy_type` for virtual separation

---

## Common Mistakes

❌ **Wrong:** Creating multiple `account_strategies` with the same `broker_profile_id` and expecting separate trades

✅ **Right:** If sharing one broker account, all accounts will show the same trades (this is correct)

❌ **Wrong:** Using the same `meta_api_account_id` for multiple `broker_profiles`

✅ **Right:** Each `broker_profile` must have a unique `meta_api_account_id` from MetaApi

❌ **Wrong:** Expecting `account_name` alone to separate trades

✅ **Right:** `broker_profile_id` is the foreign key that links trades to accounts

---

## Next Steps

1. ✅ Run `diagnose_accounts.sql` to identify your specific issue
2. ✅ Choose Fix Option 1, 2, or 3 based on your setup
3. ✅ Apply the SQL fixes
4. ✅ Restart the backend worker: `docker-compose restart worker`
5. ✅ Run verification queries
6. ✅ Send a test trade to confirm correct association
7. ✅ Check Multi-Account Manager dashboard to see separated data

---

## Still Having Issues?

If trades still appear in the wrong account after the fix:

1. Clear old trades (optional):
```sql
-- Archive old trades that were incorrectly associated
UPDATE trading_signals
SET status = 'archived'
WHERE created_at < NOW() - INTERVAL '1 day'
  AND broker_profile_id IS NULL;
```

2. Check worker logs:
```bash
docker-compose logs -f worker | grep "broker_profile_id"
```

3. Verify MetaApi account IDs in your MetaApi dashboard match your `broker_profiles` table

4. Ensure environment variables are loaded:
```bash
docker-compose exec worker env | grep META_API
```

---

**Created:** 2026-02-08
**Status:** Complete diagnostic and fix guide
