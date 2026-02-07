-- Migration: Multi-account support on trading_signals (Package A)
-- Allows one logical signal (trade_key) to have one row per broker profile.
-- Run 003_broker_profiles_up.sql first if you use the broker_profiles table.

-- 1) Add nullable broker_profile_id (no FK so migration works even without broker_profiles table)
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS broker_profile_id bigint;

COMMENT ON COLUMN public.trading_signals.broker_profile_id IS 'Optional: links to broker_profiles.id for multi-account; NULL = single-account row.';

-- 2) Drop the old single-column unique index
DROP INDEX IF EXISTS public.idx_unique_trade_key_trade_rows;

-- 3) One row per trade_key when broker_profile_id IS NULL (single-account backward compat)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade_key_single
  ON public.trading_signals (trade_key)
  WHERE (trade_key IS NOT NULL AND trim(trade_key) <> '')
    AND broker_profile_id IS NULL
    AND status IN ('pending', 'active', 'closed', 'execution_failed', 'executed');

-- 4) One row per (trade_key, broker_profile_id) when using profiles
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade_key_profile
  ON public.trading_signals (trade_key, broker_profile_id)
  WHERE (trade_key IS NOT NULL AND trim(trade_key) <> '')
    AND broker_profile_id IS NOT NULL
    AND status IN ('pending', 'active', 'closed', 'execution_failed', 'executed');
