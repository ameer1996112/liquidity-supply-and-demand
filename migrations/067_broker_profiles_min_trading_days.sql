-- ============================================================
-- Migration 067: Add min_trading_days to broker_profiles
-- Allows per-account minimum trading day rules to be stored
-- alongside other challenge settings (profit_target, drawdown limits)
-- ============================================================

ALTER TABLE public.broker_profiles
  ADD COLUMN IF NOT EXISTS min_trading_days INTEGER DEFAULT 0;

COMMENT ON COLUMN public.broker_profiles.min_trading_days IS
  'Minimum number of calendar trading days required to pass current evaluation phase (0 = no minimum)';
