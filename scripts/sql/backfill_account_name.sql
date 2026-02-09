-- Backfill account_name for existing trades
-- ============================================
-- Use this if your trades have broker_profile_id but no account_name set.
-- This will populate account_name from the linked account_strategies table.

-- Option 1: If you have one account and want to set all NULL account_names to it
-- (Replace 'FTMO-DEMO' with your actual account name)
/*
UPDATE public.trading_signals
SET account_name = 'FTMO-DEMO'
WHERE account_name IS NULL;
*/

-- Option 2: If you have multiple accounts with broker_profile_id, link them
UPDATE public.trading_signals ts
SET account_name = acs.account_name
FROM public.account_strategies acs
WHERE ts.broker_profile_id = acs.broker_profile_id
  AND ts.account_name IS NULL
  AND ts.broker_profile_id IS NOT NULL;

-- Verification: Check how many trades were updated
SELECT 
  account_name,
  COUNT(*) as trade_count
FROM public.trading_signals
WHERE account_name IS NOT NULL
GROUP BY account_name
ORDER BY account_name;

-- If you still have trades with NULL account_name and NULL broker_profile_id,
-- you can set a default account (e.g. "Default" or "Legacy"):
/*
UPDATE public.trading_signals
SET account_name = 'Default'
WHERE account_name IS NULL;
*/
