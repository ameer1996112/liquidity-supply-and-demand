-- Migration 010: Add account_name to trading_signals
-- Purpose: Track which broker account executed each trade (MetaApi account name or config snapshot)
-- Run in Supabase SQL Editor after 009.

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS account_name TEXT;

COMMENT ON COLUMN public.trading_signals.account_name IS
  'Broker account name at execution (from MetaApi or broker_profiles/account_strategies). NULL = single-account or legacy.';

CREATE INDEX IF NOT EXISTS idx_trading_signals_account_name
  ON public.trading_signals(account_name)
  WHERE account_name IS NOT NULL;
