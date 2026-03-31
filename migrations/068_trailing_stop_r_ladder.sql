-- ============================================================
-- Migration 068: Add R-ladder columns to trailing_stops
-- Adds columns needed for the R-multiple profit ladder.
-- sl_distance_pips: original SL distance in pips at time of trailing stop creation.
--                   Used to compute 1R/2R/3R price levels.
-- r2_locked / r3_locked: prevent double-firing when a milestone is revisited.
-- ============================================================

ALTER TABLE public.trailing_stops
  ADD COLUMN IF NOT EXISTS sl_distance_pips  REAL    DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS r2_locked         BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS r3_locked         BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN public.trailing_stops.sl_distance_pips IS
  'Original SL distance in pips when trailing stop was created. Basis for R-multiple calculations.';
COMMENT ON COLUMN public.trailing_stops.r2_locked IS
  'TRUE after SL has been moved to lock in 1R profit (price reached 2R).';
COMMENT ON COLUMN public.trailing_stops.r3_locked IS
  'TRUE after SL has been moved to lock in 2R profit (price reached 3R).';
