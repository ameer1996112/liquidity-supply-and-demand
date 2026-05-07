-- Persist execution-time sizing/risk values for dashboard and journal risk display.

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS risk_usd numeric,
  ADD COLUMN IF NOT EXISTS target_risk_usd numeric,
  ADD COLUMN IF NOT EXISTS effective_risk_percent numeric,
  ADD COLUMN IF NOT EXISTS spread_pips numeric,
  ADD COLUMN IF NOT EXISTS effective_sl_pips numeric,
  ADD COLUMN IF NOT EXISTS pip_value_per_lot numeric;
