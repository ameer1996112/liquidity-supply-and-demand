-- Migration 076: Multi-venue broker_profiles (Binance/Bybit support)
--
-- Goal:
-- - Allow broker_profiles rows which are NOT MetaApi/MT5 (e.g., binance/bybit)
-- - Store crypto API credentials in DB (masked in API responses; encrypted-at-rest by Supabase)
--
-- Notes:
-- - Existing schema required meta_api_account_id NOT NULL UNIQUE.
--   For crypto venues this must be nullable.

-- 1) Make meta_api_account_id nullable and remove hard UNIQUE constraint
ALTER TABLE public.broker_profiles
  ALTER COLUMN meta_api_account_id DROP NOT NULL;

ALTER TABLE public.broker_profiles
  DROP CONSTRAINT IF EXISTS broker_profiles_meta_api_account_id_key;

-- 2) Add venue + crypto credential columns
ALTER TABLE public.broker_profiles
  ADD COLUMN IF NOT EXISTS venue TEXT NOT NULL DEFAULT 'metaapi_mt5',
  ADD COLUMN IF NOT EXISTS api_key TEXT,
  ADD COLUMN IF NOT EXISTS api_secret TEXT;

COMMENT ON COLUMN public.broker_profiles.venue IS
  'Execution venue: metaapi_mt5 | binance | bybit (ctrader reserved).';

COMMENT ON COLUMN public.broker_profiles.api_key IS
  'Crypto exchange API key for binance/bybit venues. Stored encrypted at rest by Supabase. Never returned plaintext via API.';

COMMENT ON COLUMN public.broker_profiles.api_secret IS
  'Crypto exchange API secret for binance/bybit venues. Stored encrypted at rest by Supabase. Never returned plaintext via API.';

-- 3) Recreate uniqueness for MetaApi account IDs only (ignore NULL/empty)
CREATE UNIQUE INDEX IF NOT EXISTS broker_profiles_meta_api_account_id_unique
  ON public.broker_profiles(meta_api_account_id)
  WHERE meta_api_account_id IS NOT NULL AND trim(meta_api_account_id) <> '';

