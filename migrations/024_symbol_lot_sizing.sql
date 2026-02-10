-- Migration 024: Add min_lot_size and lot_step to symbol_risk_rules
-- Purpose: Enforce broker-specific minimum lot sizes and lot step increments
-- Context: Fixes "Position size must be positive (got size=0)" errors

-- Add columns if they don't exist
ALTER TABLE public.symbol_risk_rules
ADD COLUMN IF NOT EXISTS min_lot_size REAL DEFAULT 0.01,
ADD COLUMN IF NOT EXISTS lot_step REAL DEFAULT 0.01,
ADD COLUMN IF NOT EXISTS stop_loss_buffer_pips REAL DEFAULT 1.0;

-- Update existing symbols with broker-specific minimums
UPDATE public.symbol_risk_rules
SET min_lot_size = 0.01, lot_step = 0.01
WHERE symbol IN ('EURUSD', 'GBPUSD', 'USDJPY', 'GBPJPY');

-- Indices typically have larger minimum sizes (broker-dependent)
UPDATE public.symbol_risk_rules
SET min_lot_size = 0.1, lot_step = 0.1
WHERE symbol IN ('NAS100', 'US30', 'SPX500', 'GER40');

-- Metals (gold/silver) typically 0.01 minimum
UPDATE public.symbol_risk_rules
SET min_lot_size = 0.01, lot_step = 0.01
WHERE symbol IN ('XAUUSD', 'XAGUSD');

-- Add comments for documentation
COMMENT ON COLUMN public.symbol_risk_rules.min_lot_size IS
'Minimum lot size accepted by broker (e.g., 0.01 for forex, 0.1 for indices)';

COMMENT ON COLUMN public.symbol_risk_rules.lot_step IS
'Lot size increment (e.g., 0.01 means you can trade 0.01, 0.02, 0.03 but not 0.015)';

COMMENT ON COLUMN public.symbol_risk_rules.stop_loss_buffer_pips IS
'Safety margin added beyond zone boundaries to prevent stop hunts (default 1.0 pip)';

-- Example: Insert a new symbol with custom lot sizing
-- INSERT INTO public.symbol_risk_rules (symbol, min_lot_size, lot_step, pip_size, pip_value_per_lot)
-- VALUES ('BTCUSD', 0.01, 0.01, 1.0, 1.0)
-- ON CONFLICT (symbol) DO UPDATE
-- SET min_lot_size = EXCLUDED.min_lot_size,
--     lot_step = EXCLUDED.lot_step;
