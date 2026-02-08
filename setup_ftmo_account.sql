-- ========================================
-- FTMO Multi-Account Setup
-- Links ALL trades to FTMO-DEMO account
-- ========================================

-- STEP 1: Create/Update broker_profile for FTMO account
-- --------------------------------------------------------
-- Replace 'YOUR_METAAPI_ACCOUNT_ID' with the full ID from MetaApi
-- (the one that starts with 2da19feb-8495-4e72-a4e8-7f8b001153...)

INSERT INTO broker_profiles (
    name,
    meta_api_account_id,
    token_env_key,
    risk_pct,
    max_positions,
    run_mode,
    is_active
)
VALUES (
    'FTMO-DEMO',
    'YOUR_METAAPI_ACCOUNT_ID',  -- ← PASTE YOUR FULL ACCOUNT ID HERE
    'META_API_TOKEN',
    0.5,
    3,
    'LIVE',
    true
)
ON CONFLICT (meta_api_account_id)
DO UPDATE SET
    name = EXCLUDED.name,
    is_active = true,
    updated_at = NOW()
RETURNING id, name, meta_api_account_id;

-- Note the returned 'id' - you'll need it for the next steps


-- STEP 2: Create account_strategies for FTMO account
-- --------------------------------------------------------
-- This creates the "FTMO - Demo - 50K" account in the Multi-Account Manager

INSERT INTO account_strategies (
    account_name,
    broker_profile_id,
    strategy_type,
    allocated_capital_usd,
    risk_percent,
    max_positions,
    max_lot_size,
    min_rr_ratio,
    pause_trading,
    is_active
)
VALUES (
    'FTMO - Demo - 50K',
    (SELECT id FROM broker_profiles WHERE name = 'FTMO-DEMO' LIMIT 1),
    'BALANCED',
    50000.00,
    0.5,
    3,
    10.0,
    2.0,
    false,
    true
)
ON CONFLICT (account_name)
DO UPDATE SET
    broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'FTMO-DEMO' LIMIT 1),
    allocated_capital_usd = 50000.00,
    is_active = true,
    updated_at = NOW()
RETURNING id, account_name, broker_profile_id;


-- STEP 3: Link ALL existing trades to FTMO account
-- --------------------------------------------------------
-- This updates ALL trades (LIVE + PAPER) to associate with FTMO

UPDATE trading_signals
SET
    broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'FTMO-DEMO' LIMIT 1),
    account_name = 'FTMO - Demo - 50K'
WHERE broker_profile_id IS NULL OR account_name IS NULL;

-- Also update trades that might have wrong broker_profile_id
UPDATE trading_signals
SET account_name = 'FTMO - Demo - 50K'
WHERE broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'FTMO-DEMO' LIMIT 1)
  AND (account_name IS NULL OR account_name = '');


-- STEP 4: Verify the setup
-- --------------------------------------------------------

-- Check broker_profiles
SELECT
    id,
    name,
    meta_api_account_id,
    run_mode,
    is_active
FROM broker_profiles
WHERE is_active = true;

-- Check account_strategies
SELECT
    id,
    account_name,
    broker_profile_id,
    strategy_type,
    allocated_capital_usd,
    is_active
FROM account_strategies
WHERE is_active = true;

-- Check recent trades linkage
SELECT
    ts.id,
    ts.symbol,
    ts.side,
    ts.status,
    ts.run_mode,
    ts.broker_profile_id,
    ts.account_name,
    bp.name as broker_name,
    ts.created_at
FROM trading_signals ts
LEFT JOIN broker_profiles bp ON ts.broker_profile_id = bp.id
ORDER BY ts.created_at DESC
LIMIT 20;

-- Count trades by mode
SELECT
    run_mode,
    status,
    COUNT(*) as count
FROM trading_signals
WHERE broker_profile_id = (SELECT id FROM broker_profiles WHERE name = 'FTMO-DEMO' LIMIT 1)
GROUP BY run_mode, status
ORDER BY run_mode, status;


-- ========================================
-- FUTURE: Add Evaluation Accounts
-- ========================================
-- When you start an evaluation, run these queries:

/*
-- Add evaluation account (when you get a new MetaApi account for the eval)
INSERT INTO broker_profiles (
    name,
    meta_api_account_id,
    token_env_key,
    risk_pct,
    max_positions,
    run_mode,
    is_active
)
VALUES (
    'FTMO-EVAL-1',
    'new-metaapi-account-id-for-eval',
    'META_API_TOKEN',
    0.5,
    3,
    'LIVE',
    true
);

-- Create account strategy for the evaluation
INSERT INTO account_strategies (
    account_name,
    broker_profile_id,
    strategy_type,
    allocated_capital_usd,
    risk_percent,
    max_positions,
    max_lot_size,
    min_rr_ratio,
    pause_trading,
    is_active
)
VALUES (
    'FTMO - Evaluation - Phase 1',
    (SELECT id FROM broker_profiles WHERE name = 'FTMO-EVAL-1' LIMIT 1),
    'AGGRESSIVE',
    100000.00,  -- Eval account size
    1.0,        -- Higher risk for eval
    5,          -- More positions allowed
    10.0,
    2.0,
    false,
    true
);
*/


-- ========================================
-- CLEANUP: Remove duplicate accounts (optional)
-- ========================================
-- Only run this if you have duplicate account_strategies

/*
-- Find duplicates
SELECT account_name, COUNT(*) as count
FROM account_strategies
GROUP BY account_name
HAVING COUNT(*) > 1;

-- Keep only the most recent one for each name
DELETE FROM account_strategies
WHERE id NOT IN (
    SELECT MAX(id)
    FROM account_strategies
    GROUP BY account_name
);
*/
