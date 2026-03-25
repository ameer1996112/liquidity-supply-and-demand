-- Migration 059: Add token column to broker_profiles
-- Enables storing MetaAPI JWT tokens directly in DB (encrypted at rest via Supabase)
-- so accounts can be added via UI without requiring server env var changes.
-- Backward compatible: token_env_key still works as fallback.

ALTER TABLE broker_profiles
  ADD COLUMN IF NOT EXISTS token TEXT;

COMMENT ON COLUMN broker_profiles.token IS
  'MetaAPI JWT token stored directly in DB. Takes priority over token_env_key at runtime. '
  'Stored encrypted at rest by Supabase. If NULL, falls back to os.getenv(token_env_key).';

-- Also add token column to account_strategies for direct-link accounts
ALTER TABLE account_strategies
  ADD COLUMN IF NOT EXISTS meta_api_token TEXT;

COMMENT ON COLUMN account_strategies.meta_api_token IS
  'MetaAPI JWT token for direct-link accounts (no broker_profile). '
  'Falls back to os.getenv(meta_api_token_env_key) if NULL.';
