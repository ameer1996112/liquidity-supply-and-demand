# How to Run Account Enhancement Migrations

## Prerequisites
- Access to Supabase SQL Editor (https://app.supabase.com)
- Database should have existing tables from migrations 001-012

## Run Order (IMPORTANT)
Execute migrations in this exact order:

### 1. Account Enhancements
```bash
# Copy contents of migrations/013_account_enhancements.sql
# Paste into Supabase SQL Editor
# Click "Run"
```

### 2. Evaluation Progress
```bash
# Copy contents of migrations/014_evaluation_progress.sql
# Paste into Supabase SQL Editor
# Click "Run"
```

### 3. Account Status Snapshots
```bash
# Copy contents of migrations/015_account_status_snapshots.sql
# Paste into Supabase SQL Editor
# Click "Run"
```

### 4. Position Snapshots
```bash
# Copy contents of migrations/016_position_snapshots.sql
# Paste into Supabase SQL Editor
# Click "Run"
```

### 5. Trade Journal
```bash
# Copy contents of migrations/017_trade_journal.sql
# Paste into Supabase SQL Editor
# Click "Run"
```

## Verification Queries

After running all migrations, verify success:

```sql
-- Check new columns in account_strategies
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'account_strategies'
  AND column_name IN ('provider', 'account_type', 'meta_api_account_id', 'connection_status')
ORDER BY column_name;

-- Check new tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'evaluation_progress',
    'account_status_snapshots',
    'position_snapshots',
    'trade_journal'
  )
ORDER BY table_name;

-- Count rows (should all be 0 initially)
SELECT 'evaluation_progress' AS table_name, COUNT(*) AS rows FROM evaluation_progress
UNION ALL
SELECT 'account_status_snapshots', COUNT(*) FROM account_status_snapshots
UNION ALL
SELECT 'position_snapshots', COUNT(*) FROM position_snapshots
UNION ALL
SELECT 'trade_journal', COUNT(*) FROM trade_journal;
```

## Test Data (Optional)

```sql
-- Create a test FTMO account
INSERT INTO account_strategies (
  account_name,
  provider,
  account_type,
  strategy_type,
  risk_percent,
  max_positions,
  allocated_capital_usd
)
VALUES (
  'FTMO Challenge Test',
  'FTMO',
  'Eval',
  'BALANCED',
  0.5,
  3,
  100000
);

-- Add evaluation rules for test account
INSERT INTO evaluation_progress (
  account_name,
  profit_target_usd,
  daily_loss_limit_pct,
  max_drawdown_pct,
  min_trading_days,
  consistency_max_day_pct
)
VALUES (
  'FTMO Challenge Test',
  10000,
  5.0,
  10.0,
  30,
  0.40
);

-- Verify test data
SELECT
  a.account_name,
  a.provider,
  a.account_type,
  e.profit_target_usd,
  e.daily_loss_limit_pct,
  e.max_drawdown_pct
FROM account_strategies a
LEFT JOIN evaluation_progress e ON a.account_name = e.account_name
WHERE a.account_name = 'FTMO Challenge Test';
```

## Rollback (If Needed)

To undo all migrations:

```sql
-- Drop new tables (reverse order)
DROP TABLE IF EXISTS public.trade_journal CASCADE;
DROP TABLE IF EXISTS public.position_snapshots CASCADE;
DROP TABLE IF EXISTS public.account_status_snapshots CASCADE;
DROP TABLE IF EXISTS public.evaluation_progress CASCADE;

-- Remove new columns from account_strategies
ALTER TABLE public.account_strategies
  DROP COLUMN IF EXISTS provider,
  DROP COLUMN IF EXISTS account_type,
  DROP COLUMN IF EXISTS meta_api_account_id,
  DROP COLUMN IF EXISTS meta_api_token_env_key,
  DROP COLUMN IF EXISTS last_sync_time,
  DROP COLUMN IF EXISTS connection_status;
```

## Success Indicators

✅ All 5 migrations run without errors
✅ Verification queries return expected results
✅ Test account inserts successfully
✅ No constraint violations or data type errors

## Next Steps

After migrations are confirmed working:
1. Proceed to TICKET 2: MetaAPI Adapter Enhancements
2. Add `get_open_positions()` and `get_account_status()` methods
