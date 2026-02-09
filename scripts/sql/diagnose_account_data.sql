-- Diagnostic Query: Check account_name data quality
-- Run this in Supabase SQL Editor to diagnose why account performance is showing wrong data

-- 1. Check what account_name values exist in trading_signals
SELECT 
  account_name,
  COUNT(*) as signal_count,
  COUNT(CASE WHEN exit_price IS NOT NULL THEN 1 END) as closed_trades,
  COUNT(CASE WHEN pnl_usd IS NOT NULL THEN 1 END) as trades_with_pnl,
  MIN(created_at) as first_trade,
  MAX(created_at) as last_trade
FROM public.trading_signals
GROUP BY account_name
ORDER BY signal_count DESC;

-- 2. Check if trades have broker_profile_id but no account_name
SELECT 
  broker_profile_id,
  COUNT(*) as trades_without_account_name,
  STRING_AGG(DISTINCT symbol, ', ') as symbols
FROM public.trading_signals
WHERE account_name IS NULL AND broker_profile_id IS NOT NULL
GROUP BY broker_profile_id;

-- 3. Check account_strategies configuration
SELECT 
  account_name,
  broker_profile_id,
  provider,
  account_type,
  strategy_type,
  is_active,
  pause_trading,
  allocated_capital_usd
FROM public.account_strategies
ORDER BY account_name;

-- 4. For your specific account: Check all trades
-- Note: Some columns may be NULL if migration 020 hasn't been run yet
SELECT 
  id,
  symbol,
  side,
  status,
  outcome,
  COALESCE(pnl_usd, pnl) as pnl, -- pnl_usd added in migration 020, pnl is legacy
  account_name,
  broker_profile_id,
  COALESCE(entry_time, created_at) as entry_time,
  COALESCE(exit_time, close_time) as exit_time,
  COALESCE(mae, mae_pips) as mae, -- mae added in migration 020, mae_pips is legacy
  COALESCE(exit_reason, exit_type) as exit_reason,
  created_at
FROM public.trading_signals
WHERE account_name = 'FTMO-DEMO' -- Change to your exact account name
   OR account_name LIKE '%FTMO%' -- Fuzzy match to catch variations
ORDER BY created_at DESC
LIMIT 50;

-- 5. Check if column exit_time exists and has data
SELECT 
  column_name, 
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'trading_signals'
  AND column_name IN ('exit_time', 'mae', 'mfe', 'exit_reason', 'account_name')
ORDER BY column_name;
