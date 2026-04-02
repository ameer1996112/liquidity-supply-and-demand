-- Migration 070: Add 1-candle liquidity scoring fields to signals table
-- These fields are populated from the enriched Pine webhook payload
-- and used by LiquidityScorer for composite confidence scoring.

ALTER TABLE signals
    ADD COLUMN IF NOT EXISTS primed              BOOLEAN,
    ADD COLUMN IF NOT EXISTS sweep_to_touch_bars INTEGER,
    ADD COLUMN IF NOT EXISTS peak_to_touch_bars  INTEGER,
    ADD COLUMN IF NOT EXISTS liq_source          TEXT,
    ADD COLUMN IF NOT EXISTS zone_grade          TEXT,
    ADD COLUMN IF NOT EXISTS bars_since_zone     INTEGER,
    ADD COLUMN IF NOT EXISTS liquidity_score     INTEGER;  -- 0-100 composite score

COMMENT ON COLUMN signals.primed              IS 'Zone was primed (touched without entry) before signal fired';
COMMENT ON COLUMN signals.sweep_to_touch_bars IS 'Bars between liquidity sweep and zone touch (0 = immediate reaction)';
COMMENT ON COLUMN signals.peak_to_touch_bars  IS 'Bars between structural extreme (peak) and zone touch';
COMMENT ON COLUMN signals.liq_source          IS 'Source of liquidity level (e.g. MAKUCHAKU_PIVOT)';
COMMENT ON COLUMN signals.zone_grade          IS 'S&D zone grade (A/B/C) at time of signal';
COMMENT ON COLUMN signals.bars_since_zone     IS 'Age of the zone in bars at time of signal';
COMMENT ON COLUMN signals.liquidity_score     IS 'Composite confidence score 0-100 from LiquidityScorer';
