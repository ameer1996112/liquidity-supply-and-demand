-- Migration: broker_profiles for multi-account (Package A: Funded Fleet)
-- Optional. When used, worker/logic can loop over active profiles and execute the same signal on each.
-- token_env_key: env var name for the MetaApi token (e.g. META_API_TOKEN or META_API_TOKEN_FUNDED).

CREATE TABLE IF NOT EXISTS public.broker_profiles (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL,
    meta_api_account_id text NOT NULL,
    token_env_key text NOT NULL DEFAULT 'META_API_TOKEN',
    risk_pct    real NOT NULL DEFAULT 1.0,
    max_positions int NOT NULL DEFAULT 3,
    run_mode    text NOT NULL DEFAULT 'LIVE' CHECK (run_mode IN ('LIVE', 'PAPER')),
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_broker_profiles_active ON public.broker_profiles(is_active) WHERE is_active = true;
COMMENT ON TABLE public.broker_profiles IS 'Multi-account execution: one signal can be executed on multiple broker profiles with different risk settings.';
