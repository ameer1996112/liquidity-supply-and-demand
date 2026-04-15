-- Migration 078: Allow multiple broker_profiles rows to be selected for trading.
-- This removes the old single-active-account restriction so several accounts
-- can have selected_for_trading = true at the same time.

DROP INDEX IF EXISTS public.idx_broker_profiles_single_selected;

CREATE INDEX IF NOT EXISTS idx_broker_profiles_selected_for_trading
  ON public.broker_profiles (selected_for_trading)
  WHERE selected_for_trading = true;

COMMENT ON COLUMN public.broker_profiles.selected_for_trading IS
  'True when the account is enabled for trading. Multiple rows may be true at once.';
