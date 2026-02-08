-- ========================================
-- Multi-Account Diagnostic Queries
-- ========================================

-- 1. Check account_strategies configuration
SELECT
    id,
    account_name,
    broker_profile_id,
    strategy_type,
    allocated_capital_usd,
    is_active,
    created_at
FROM account_strategies
WHERE is_active = true
ORDER BY account_name;

-- 2. Check broker_profiles configuration
SELECT
    id as profile_id,
    name as profile_name,
    meta_api_account_id,
    run_mode,
    risk_pct,
    is_active
FROM broker_profiles
WHERE is_active = true
ORDER BY name;

-- 3. Check trade distribution by broker_profile_id
SELECT
    broker_profile_id,
    account_name,
    status,
    COUNT(*) as trade_count,
    MIN(created_at) as first_trade,
    MAX(created_at) as last_trade
FROM trading_signals
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY broker_profile_id, account_name, status
ORDER BY broker_profile_id, trade_count DESC;

-- 4. Check if broker_profile_id linkage is correct
SELECT
    acs.account_name,
    acs.broker_profile_id,
    bp.name as broker_profile_name,
    bp.meta_api_account_id,
    COUNT(ts.id) as trade_count
FROM account_strategies acs
LEFT JOIN broker_profiles bp ON acs.broker_profile_id = bp.id
LEFT JOIN trading_signals ts ON ts.broker_profile_id = acs.broker_profile_id
WHERE acs.is_active = true
GROUP BY acs.account_name, acs.broker_profile_id, bp.name, bp.meta_api_account_id
ORDER BY acs.account_name;

-- 5. Check for duplicate meta_api_account_id (CRITICAL CHECK)
SELECT
    meta_api_account_id,
    COUNT(*) as profile_count,
    STRING_AGG(name, ', ') as profile_names
FROM broker_profiles
WHERE is_active = true
GROUP BY meta_api_account_id
HAVING COUNT(*) > 1;

-- 6. Recent trades with account info
SELECT
    ts.id,
    ts.trade_key,
    ts.symbol,
    ts.side,
    ts.status,
    ts.broker_profile_id,
    ts.account_name,
    ts.broker_order_id,
    bp.name as broker_profile_name,
    bp.meta_api_account_id,
    ts.created_at
FROM trading_signals ts
LEFT JOIN broker_profiles bp ON ts.broker_profile_id = bp.id
WHERE ts.created_at >= NOW() - INTERVAL '7 days'
ORDER BY ts.created_at DESC
LIMIT 20;
