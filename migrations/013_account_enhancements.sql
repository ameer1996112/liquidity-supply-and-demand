-- Migration 013: Account Enhancements
-- Add provider, account_type, and direct MetaAPI fields to account_strategies

-- Add new columns to account_strategies
ALTER TABLE public.account_strategies
  ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'Personal',
  ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) DEFAULT 'Personal'
    CHECK (account_type IN ('Eval', 'Funded', 'Personal')),
  ADD COLUMN IF NOT EXISTS meta_api_account_id TEXT,
  ADD COLUMN IF NOT EXISTS meta_api_token_env_key TEXT DEFAULT 'META_API_TOKEN',
  ADD COLUMN IF NOT EXISTS last_sync_time TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS connection_status VARCHAR(20) DEFAULT 'not_configured'
    CHECK (connection_status IN ('connected', 'disconnected', 'error', 'not_configured'));

-- Create index for provider filtering
CREATE INDEX IF NOT EXISTS idx_account_strategies_provider
  ON public.account_strategies(provider);

-- Create index for account_type filtering
CREATE INDEX IF NOT EXISTS idx_account_strategies_type
  ON public.account_strategies(account_type);

-- Create index for connection status
CREATE INDEX IF NOT EXISTS idx_account_strategies_connection
  ON public.account_strategies(connection_status);

-- Add comments
COMMENT ON COLUMN public.account_strategies.provider IS
  'Account provider (FTMO, PropFirm, MyFundedFX, Personal, etc.)';

COMMENT ON COLUMN public.account_strategies.account_type IS
  'Account type: Eval (challenge), Funded (passed challenge), or Personal';

COMMENT ON COLUMN public.account_strategies.meta_api_account_id IS
  'Direct MetaAPI account ID (alternative to broker_profile_id mapping)';

COMMENT ON COLUMN public.account_strategies.meta_api_token_env_key IS
  'Environment variable name containing the MetaAPI token (default: META_API_TOKEN)';

COMMENT ON COLUMN public.account_strategies.last_sync_time IS
  'Last successful sync with MetaAPI (NULL if never synced)';

COMMENT ON COLUMN public.account_strategies.connection_status IS
  'MetaAPI connection status: connected, disconnected, error, not_configured';

-- Verification query
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'account_strategies'
  AND column_name IN ('provider', 'account_type', 'meta_api_account_id', 'connection_status')
ORDER BY column_name;
