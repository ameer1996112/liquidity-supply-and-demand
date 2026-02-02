# Supabase migrations: execution columns

## Files

- **Up:** `001_execution_columns_up.sql` — adds columns and partial unique index.
- **Down:** `001_execution_columns_down.sql` — drops index and columns (rollback).

---

## How to run in Supabase

1. Open your project in [Supabase Dashboard](https://app.supabase.com).
2. Go to **SQL Editor** → **New query**.
3. Paste the contents of `001_execution_columns_up.sql`.
4. Click **Run** (or Cmd/Ctrl+Enter).
5. Confirm success (no errors in the result panel).

To rollback: open a new query, paste `001_execution_columns_down.sql`, and run.

---

## Validation (SQL queries)

Run these in the SQL Editor after applying the **up** migration.

### 1) New columns exist and are nullable

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'trading_signals'
  AND column_name IN (
    'execution_status', 'broker_order_id', 'submitted_at',
    'filled_at', 'last_error', 'close_broker_order_id'
  )
ORDER BY ordinal_position;
```

**Expected:** 6 rows; `data_type` = `text` or `timestamp with time zone`, `is_nullable` = `YES`.

### 2) Partial unique index exists

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'trading_signals'
  AND indexname = 'idx_unique_trade_key_trade_rows';
```

**Expected:** One row; `indexdef` contains `UNIQUE`, `trade_key`, and `WHERE` with `pending`, `active`, `closed`, `execution_failed`.

### 3) Index enforces uniqueness (optional test)

```sql
-- Should succeed: two rows with same trade_key but status NOT in the index predicate
INSERT INTO public.trading_signals (
  symbol, side, entry, sl, tp, size, trade_key, status
) VALUES
  ('TEST', 'buy', 1.0, 0.9, 1.1, 0.01, 'test-key-1', 'filtered'),
  ('TEST', 'buy', 1.0, 0.9, 1.1, 0.01, 'test-key-1', 'filtered');

-- Should fail: second row with same trade_key and status in ('pending','active','closed','execution_failed')
INSERT INTO public.trading_signals (
  symbol, side, entry, sl, tp, size, trade_key, status
) VALUES ('TEST', 'buy', 1.0, 0.9, 1.1, 0.01, 'unique-test', 'pending');
INSERT INTO public.trading_signals (
  symbol, side, entry, sl, tp, size, trade_key, status
) VALUES ('TEST', 'buy', 1.0, 0.9, 1.1, 0.01, 'unique-test', 'pending');
-- Expect: duplicate key value violates unique constraint "idx_unique_trade_key_trade_rows"

-- Cleanup test rows
DELETE FROM public.trading_signals WHERE symbol = 'TEST' AND side = 'buy' AND entry = 1.0;
```

### 4) Existing data unchanged

```sql
SELECT id, status, execution_status, broker_order_id, submitted_at, last_error, close_broker_order_id
FROM public.trading_signals
ORDER BY id DESC
LIMIT 5;
```

**Expected:** New columns are `NULL` for existing rows; `status` and other existing columns unchanged.

---

## Notes

- **No enums:** `execution_status` is `TEXT`. Use values: `pending`, `active`, `execution_failed`, `closed` (and optionally `close_failed`).
- **Partial index:** Only rows with non-empty `trade_key` and `status IN ('pending','active','closed','execution_failed')` are included; duplicate `trade_key` in that set is rejected.
- **Down migration:** Dropping columns fails if any objects (views, triggers) depend on them. If you have such objects, drop or alter them before running the down migration.
