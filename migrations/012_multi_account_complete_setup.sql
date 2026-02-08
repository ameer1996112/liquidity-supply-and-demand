-- ========================================
-- Multi-Account Complete Setup
-- Consolidated migration for FTMO multi-account support
-- ========================================
-- This migration combines:
-- - 003_broker_profiles_up.sql
-- - 004_multi_account_trading_signals_up.sql
-- - 009_portfolio_command_center.sql (account_strategies only)
-- - 010_account_name.sql
-- ========================================

-- STEP 1: Create broker_profiles table
-- ========================================
CREATE TABLE IF NOT EXISTS public.broker_profiles (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL,
    meta_api_account_id text NOT NULL UNIQUE,
    token_env_key text NOT NULL DEFAULT 'META_API_TOKEN',
    risk_pct    real NOT NULL DEFAULT 1.0,
    max_positions int NOT NULL DEFAULT 3,
    run_mode    text NOT NULL DEFAULT 'LIVE' CHECK (run_mode IN ('LIVE', 'PAPER')),
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_broker_profiles_active
    ON public.broker_profiles(is_active) WHERE is_active = true;

COMMENT ON TABLE public.broker_profiles IS 'Multi-account execution: one signal can be executed on multiple broker profiles with different risk settings.';


-- STEP 2: Add broker_profile_id to trading_signals
-- ========================================
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS broker_profile_id bigint;

COMMENT ON COLUMN public.trading_signals.broker_profile_id IS
    'Optional: links to broker_profiles.id for multi-account; NULL = single-account row.';

-- Drop old unique index if exists
DROP INDEX IF EXISTS public.idx_unique_trade_key_trade_rows;

-- One row per trade_key when broker_profile_id IS NULL (single-account)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade_key_single
  ON public.trading_signals (trade_key)
  WHERE (trade_key IS NOT NULL AND trim(trade_key) <> '')
    AND broker_profile_id IS NULL
    AND status IN ('pending', 'active', 'closed', 'execution_failed', 'executed');

-- One row per (trade_key, broker_profile_id) when using profiles
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade_key_profile
  ON public.trading_signals (trade_key, broker_profile_id)
  WHERE (trade_key IS NOT NULL AND trim(trade_key) <> '')
    AND broker_profile_id IS NOT NULL
    AND status IN ('pending', 'active', 'closed', 'execution_failed', 'executed');


-- STEP 3: Add account_name to trading_signals
-- ========================================
ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS account_name TEXT;

COMMENT ON COLUMN public.trading_signals.account_name IS
  'Broker account name at execution (from MetaApi or broker_profiles/account_strategies). NULL = single-account or legacy.';

CREATE INDEX IF NOT EXISTS idx_trading_signals_account_name
  ON public.trading_signals(account_name)
  WHERE account_name IS NOT NULL;


-- STEP 4: Create account_strategies table
-- ========================================
CREATE TABLE IF NOT EXISTS public.account_strategies (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    broker_profile_id       bigint REFERENCES public.broker_profiles(id) ON DELETE CASCADE,
    account_name            VARCHAR(100) NOT NULL UNIQUE,

    -- Strategy configuration
    strategy_type           VARCHAR(50) DEFAULT 'BALANCED', -- 'CONSERVATIVE', 'BALANCED', 'AGGRESSIVE', 'CUSTOM'
    risk_percent            REAL,
    max_lot_size            REAL,
    min_rr_ratio            REAL,

    -- Filters (JSON array of filter rules)
    allowed_entry_models    TEXT[], -- ['FLIP', 'BASE']
    min_zone_grade          VARCHAR(5), -- 'A+', 'A', 'B+'
    allowed_sessions        TEXT[], -- ['LONDON', 'NY']

    -- Portfolio limits
    max_positions           INTEGER DEFAULT 3,
    max_daily_trades        INTEGER DEFAULT 2,

    -- Capital allocation
    allocated_capital_usd   REAL,
    target_allocation_pct   REAL, -- Desired % of total capital

    -- Status
    is_active               BOOLEAN DEFAULT true,
    pause_trading           BOOLEAN DEFAULT false,

    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_account_strategies_active
    ON public.account_strategies(account_name) WHERE is_active = true;

COMMENT ON TABLE public.account_strategies IS 'Per-account strategy configurations and risk profiles';


-- ========================================
-- Verification Queries
-- ========================================

-- Check tables exist
SELECT 'broker_profiles' as table_name, COUNT(*) as row_count FROM broker_profiles
UNION ALL
SELECT 'account_strategies', COUNT(*) FROM account_strategies;

-- Verify columns added to trading_signals
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'trading_signals'
  AND column_name IN ('broker_profile_id', 'account_name')
ORDER BY column_name;
