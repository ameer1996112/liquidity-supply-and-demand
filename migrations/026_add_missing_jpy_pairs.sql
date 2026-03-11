-- Migration 026: Add missing JPY cross pairs to symbol_risk_rules
-- Purpose: Fix NZDJPY position sizing bug where bot calculated 0.08 lots instead of ~1.88 lots
-- Context: NZDJPY was missing from symbol_risk_rules, falling back to hardcoded pip_value_per_lot=1000.0
--          which is only correct for USDJPY @ parity. Other JPY pairs need accurate pip values.
-- Bug Impact: Position sizes were 20-25× too small for missing JPY pairs
-- Related: Issue where NZDJPY showed -$156.62 frontend but -$2.52 actual broker PnL

-- ========== MISSING JPY CROSS PAIRS ==========
-- Static approximations for common JPY pair ranges:
-- NZDJPY @ 90-95:  pip_value ≈ $11/lot
-- CADJPY @ 105-115: pip_value ≈ $9/lot
-- CHFJPY @ 165-175: pip_value ≈ $6/lot

INSERT INTO public.symbol_risk_rules (
    symbol,
    max_lot_size,
    risk_percent,
    pip_size,
    pip_value_per_lot,
    max_positions,
    stop_loss_buffer_pips,
    min_lot_size,
    lot_step,
    enabled
)
VALUES
    -- NZDJPY: New Zealand Dollar / Japanese Yen
    -- Typical range: 85-100 JPY per NZD
    -- pip_value @ 93: (0.01 / 93) * 100,000 ≈ $10.75/lot
    ('NZDJPY', 2.0, 0.5, 0.01, 11.0, 3, 1.0, 0.01, 0.01, TRUE),

    -- CADJPY: Canadian Dollar / Japanese Yen
    -- Typical range: 100-120 JPY per CAD
    -- pip_value @ 110: (0.01 / 110) * 100,000 ≈ $9.09/lot
    ('CADJPY', 2.0, 0.5, 0.01, 9.0, 3, 1.0, 0.01, 0.01, TRUE),

    -- CHFJPY: Swiss Franc / Japanese Yen
    -- Typical range: 160-180 JPY per CHF
    -- pip_value @ 170: (0.01 / 170) * 100,000 ≈ $5.88/lot
    ('CHFJPY', 2.0, 0.5, 0.01, 6.0, 3, 1.0, 0.01, 0.01, TRUE),

    -- NZDCHF: New Zealand Dollar / Swiss Franc (non-JPY but missing)
    -- Standard forex pip calculation
    ('NZDCHF', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),

    -- CADCHF: Canadian Dollar / Swiss Franc (non-JPY but missing)
    ('CADCHF', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE)

ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    risk_percent = EXCLUDED.risk_percent,
    max_lot_size = EXCLUDED.max_lot_size,
    max_positions = EXCLUDED.max_positions,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- Add comment explaining the static approximation
COMMENT ON TABLE public.symbol_risk_rules IS
'Symbol-specific risk parameters. Note: JPY pair pip_values are static approximations.
For precise calculation, use: pip_value = (pip_size / current_exchange_rate) * lot_size.
The risk_engine.py now uses dynamic calculation when entry_price is available (as of migration 026).';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration 026 completed: Added NZDJPY, CADJPY, CHFJPY, NZDCHF, CADCHF';
    RAISE NOTICE 'Note: pip_values are static approximations. risk_engine.py uses dynamic calculation.';
END $$;
