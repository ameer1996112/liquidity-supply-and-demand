-- Migration 020: Add execution telemetry columns to trading_signals
-- Purpose: Add missing columns that backend API expects for trade history/analytics
-- These complement existing columns (mae_pips, close_time, etc.) with more detailed tracking

-- Entry/Exit tracking
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS entry_price REAL,
  ADD COLUMN IF NOT EXISTS exit_price REAL,
  ADD COLUMN IF NOT EXISTS entry_time TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS exit_time TIMESTAMPTZ;

-- P&L and execution metrics
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS pnl_usd REAL,
  ADD COLUMN IF NOT EXISTS pnl_percent REAL,
  ADD COLUMN IF NOT EXISTS mae REAL,
  ADD COLUMN IF NOT EXISTS mfe REAL;

-- Exit metadata
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS exit_reason TEXT,
  ADD COLUMN IF NOT EXISTS hold_duration_seconds INTEGER;

-- Comments
COMMENT ON COLUMN public.trading_signals.entry_price IS 'Actual entry price from broker (may differ from planned entry)';
COMMENT ON COLUMN public.trading_signals.exit_price IS 'Actual exit price from broker';
COMMENT ON COLUMN public.trading_signals.entry_time IS 'Timestamp when position was opened at broker';
COMMENT ON COLUMN public.trading_signals.exit_time IS 'Timestamp when position was closed at broker';
COMMENT ON COLUMN public.trading_signals.pnl_usd IS 'Realized P&L in USD including commission/swap';
COMMENT ON COLUMN public.trading_signals.pnl_percent IS 'Realized P&L as percentage of account balance';
COMMENT ON COLUMN public.trading_signals.mae IS 'Maximum Adverse Excursion in USD (max drawdown during trade)';
COMMENT ON COLUMN public.trading_signals.mfe IS 'Maximum Favorable Excursion in USD (max profit during trade)';
COMMENT ON COLUMN public.trading_signals.exit_reason IS 'Why trade was closed: TP, SL, manual, trailing_stop, time_exit, etc.';
COMMENT ON COLUMN public.trading_signals.hold_duration_seconds IS 'How long position was held in seconds';

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trading_signals_exit_time
  ON public.trading_signals(exit_time DESC)
  WHERE exit_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trading_signals_entry_time
  ON public.trading_signals(entry_time DESC)
  WHERE entry_time IS NOT NULL;

-- Optional: Backfill exit_time from close_time for existing trades
UPDATE public.trading_signals
SET 
  exit_time = close_time,
  exit_price = close_price,
  entry_price = entry,
  entry_time = created_at,
  pnl_usd = pnl,
  exit_reason = COALESCE(exit_type, 'unknown')
WHERE exit_time IS NULL
  AND close_time IS NOT NULL;
