-- Migration 040: Add commission and swap columns to trading_signals
-- These store actual broker commission and swap/rollover charges

ALTER TABLE public.trading_signals
ADD COLUMN IF NOT EXISTS commission REAL DEFAULT 0,
ADD COLUMN IF NOT EXISTS swap REAL DEFAULT 0;

COMMENT ON COLUMN public.trading_signals.commission IS 'Actual broker commission charged (negative value)';
COMMENT ON COLUMN public.trading_signals.swap IS 'Actual broker swap/rollover charges (can be positive or negative)';

-- Update pnl_usd comment to reflect that it should include commission/swap
COMMENT ON COLUMN public.trading_signals.pnl_usd IS 'Realized P&L in USD including commission/swap (fetched from broker for live trades)';

-- Verification
SELECT
    'Added commission and swap columns' AS status,
    COUNT(*) FILTER (WHERE commission IS NOT NULL) AS rows_with_commission,
    COUNT(*) FILTER (WHERE swap IS NOT NULL) AS rows_with_swap,
    COUNT(*) AS total_rows
FROM public.trading_signals
WHERE status = 'CLOSED';
