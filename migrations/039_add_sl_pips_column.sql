-- Migration 039: Add sl_pips column to trading_signals
-- Purpose: Store stop loss distance in pips from TradingView webhook
-- Bug fix: sl_pips was sent by Pine but never persisted (column didn't exist)

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS sl_pips REAL;

COMMENT ON COLUMN public.trading_signals.sl_pips IS 'Stop loss distance in pips (from TradingView webhook)';

-- Backfill exit_price from close_price for trades closed via webhook exit
-- (watchdog already writes exit_price; this covers the update_alert_exit path)
UPDATE public.trading_signals
SET exit_price = close_price
WHERE exit_price IS NULL
  AND close_price IS NOT NULL;
