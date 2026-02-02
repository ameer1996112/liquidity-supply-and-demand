-- Migration: Add execution lifecycle columns and partial unique index on trade_key
-- Table: public.trading_signals
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- 1) Add nullable execution columns (no enums; use TEXT)
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS execution_status TEXT,
  ADD COLUMN IF NOT EXISTS broker_order_id TEXT,
  ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS filled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_error TEXT,
  ADD COLUMN IF NOT EXISTS close_broker_order_id TEXT;

-- 2) Partial unique index: one row per trade_key for "trade" rows only
--    (trade_key non-empty AND status in pending/active/closed/execution_failed)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade_key_trade_rows
  ON public.trading_signals (trade_key)
  WHERE (trade_key IS NOT NULL AND trim(trade_key) <> '')
    AND status IN ('pending', 'active', 'closed', 'execution_failed');

-- Comment for documentation
COMMENT ON COLUMN public.trading_signals.execution_status IS 'Lifecycle: pending, active, execution_failed, closed';
COMMENT ON COLUMN public.trading_signals.broker_order_id IS 'Broker order/ticket id for open (LIVE)';
COMMENT ON COLUMN public.trading_signals.close_broker_order_id IS 'Broker order/ticket id for close (LIVE)';
