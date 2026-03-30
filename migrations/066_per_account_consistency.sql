-- migrations/066_per_account_consistency.sql
-- Add per-account consistency rule toggle to broker_profiles.
--
-- Resolution order in the worker:
--   1. profile.consistency_enabled (this column)  — NULL means "use global"
--   2. Global CONSISTENCY_ENABLED setting          — fallback
--
-- NULL  = use global settings.consistency_enabled (default safe behaviour)
-- TRUE  = enforce FTMO 40% best-day rule for this account
-- FALSE = skip consistency rule for this account (use for ACG, etc.)

ALTER TABLE broker_profiles
  ADD COLUMN IF NOT EXISTS consistency_enabled BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN broker_profiles.consistency_enabled IS
  'NULL=use global CONSISTENCY_ENABLED setting, TRUE=enforce 40% rule, FALSE=skip rule';
