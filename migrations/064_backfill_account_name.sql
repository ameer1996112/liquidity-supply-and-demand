-- Backfill account_name on trading_signals from broker_profiles
-- Covers historical trades that have broker_profile_id but no account_name
UPDATE trading_signals
SET account_name = bp.name
FROM broker_profiles bp
WHERE trading_signals.broker_profile_id = bp.id
  AND (trading_signals.account_name IS NULL OR trading_signals.account_name = '');
