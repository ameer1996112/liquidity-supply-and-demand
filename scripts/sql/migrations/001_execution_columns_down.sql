-- Rollback: Remove execution columns and partial unique index
-- Run only after 001_execution_columns_up.sql; safe to run if index/columns already dropped.

-- 1) Drop partial unique index first (depends on table, not on columns)
DROP INDEX IF EXISTS public.idx_unique_trade_key_trade_rows;

-- 2) Drop new columns (order irrelevant)
ALTER TABLE public.trading_signals
  DROP COLUMN IF EXISTS execution_status,
  DROP COLUMN IF EXISTS broker_order_id,
  DROP COLUMN IF EXISTS submitted_at,
  DROP COLUMN IF EXISTS filled_at,
  DROP COLUMN IF EXISTS last_error,
  DROP COLUMN IF EXISTS close_broker_order_id;
