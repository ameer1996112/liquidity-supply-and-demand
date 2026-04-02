-- Migration 072: Fix migration 070 — columns were added to 'signals' but code uses 'trading_signals'
-- Re-add the 1-candle liquidity scoring fields to the correct table.

ALTER TABLE trading_signals
    ADD COLUMN IF NOT EXISTS primed              BOOLEAN,
    ADD COLUMN IF NOT EXISTS sweep_to_touch_bars INTEGER,
    ADD COLUMN IF NOT EXISTS peak_to_touch_bars  INTEGER,
    ADD COLUMN IF NOT EXISTS liq_source          TEXT,
    ADD COLUMN IF NOT EXISTS zone_grade          TEXT,
    ADD COLUMN IF NOT EXISTS bars_since_zone     INTEGER,
    ADD COLUMN IF NOT EXISTS liquidity_score     INTEGER;

COMMENT ON COLUMN trading_signals.primed              IS 'Zone was primed (touched without entry) before signal fired';
COMMENT ON COLUMN trading_signals.sweep_to_touch_bars IS 'Bars between liquidity sweep and zone touch';
COMMENT ON COLUMN trading_signals.peak_to_touch_bars  IS 'Bars between structural extreme (peak) and zone touch';
COMMENT ON COLUMN trading_signals.liq_source          IS 'Source of liquidity level (e.g. MAKUCHAKU_PIVOT)';
COMMENT ON COLUMN trading_signals.zone_grade          IS 'S&D zone grade (A/B/C) at time of signal';
COMMENT ON COLUMN trading_signals.bars_since_zone     IS 'Age of the zone in bars at time of signal';
COMMENT ON COLUMN trading_signals.liquidity_score     IS 'Composite confidence score 0-100 from LiquidityScorer';
