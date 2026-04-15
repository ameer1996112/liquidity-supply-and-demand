-- Migration 077: Add prop_firm_name to broker_profiles
--
-- Some API/UI flows persist prop firm name (e.g., FTMO, ACG) to broker_profiles.
-- Older DBs may be missing this column, causing PostgREST PGRST204 errors.

ALTER TABLE public.broker_profiles
  ADD COLUMN IF NOT EXISTS prop_firm_name TEXT;

COMMENT ON COLUMN public.broker_profiles.prop_firm_name IS
  'Prop firm name for evaluation/funded accounts (e.g., FTMO, Alpha Capital Group). Optional for personal accounts.';

