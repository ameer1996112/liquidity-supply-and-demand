-- ════════════════════════════════════════════════════════════════
-- Migration 022: Add raw pip columns for liquidity distance/spread
-- 
-- Previously, liquidity_distance stored a normalized SCORE (0-100),
-- but the dashboard displayed it as "pips" which was misleading.
-- These new columns store the actual pip distance from the zone
-- to the liquidity level, for accurate display on the dashboard.
-- The score columns are kept for AI model compatibility.
-- ════════════════════════════════════════════════════════════════

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS liquidity_distance_pips real,
  ADD COLUMN IF NOT EXISTS liquidity_spread_pips real;

COMMENT ON COLUMN public.trading_signals.liquidity_distance_pips IS
  'Raw pip distance from zone boundary to liquidity level (for display). Demand: zone top → liq low. Supply: zone bottom → liq high.';

COMMENT ON COLUMN public.trading_signals.liquidity_spread_pips IS
  'Raw pip distance between inducement high and low (for display).';

COMMENT ON COLUMN public.trading_signals.liquidity_distance IS
  'AI score 0-100 (higher = closer liquidity = better setup). Used by ML models. NOT pips.';

COMMENT ON COLUMN public.trading_signals.liquidity_spread IS
  'AI score: raw spread pips capped at 100. Used by ML models.';

-- Verify
DO $$
BEGIN
  RAISE NOTICE '✅ Migration 022 complete: liquidity_distance_pips and liquidity_spread_pips columns added';
END $$;
