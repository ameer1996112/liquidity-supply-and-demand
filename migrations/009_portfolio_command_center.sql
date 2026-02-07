-- Migration: Portfolio Command Center V2.0
-- Tables for Live Risk Controls, Portfolio Optimizer, Multi-Account Orchestration

-- ═══════════════════════════════════════════════════════════════
-- 1. LIVE RISK CONTROLS
-- Dynamic risk configuration (overrides .env settings)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.risk_config_overrides (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    setting_key         VARCHAR(100) NOT NULL UNIQUE,

    -- Value storage (use appropriate column based on type)
    value_float         REAL,
    value_bool          BOOLEAN,
    value_int           INTEGER,
    value_json          JSONB,

    -- Metadata
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_by          VARCHAR(50) DEFAULT 'UI',
    notes               TEXT,
    is_active           BOOLEAN DEFAULT true,

    -- Audit trail
    previous_value      TEXT,
    change_reason       TEXT
);

CREATE INDEX IF NOT EXISTS idx_risk_config_active
    ON public.risk_config_overrides(setting_key) WHERE is_active = true;

COMMENT ON TABLE public.risk_config_overrides IS 'Live risk settings that override .env config (no restart required)';
COMMENT ON COLUMN public.risk_config_overrides.setting_key IS 'Setting name (e.g., risk_percent, max_lot_size)';


-- ═══════════════════════════════════════════════════════════════
-- 2. TIME-BASED RISK RULES
-- Automated risk adjustments based on time/events
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.time_based_risk_rules (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name           VARCHAR(100) NOT NULL,
    enabled             BOOLEAN DEFAULT true,

    -- Trigger conditions
    trigger_type        VARCHAR(50) NOT NULL, -- 'TIME_OF_DAY', 'DAY_OF_WEEK', 'NFP_RELEASE', 'MARKET_OPEN', 'CUSTOM'
    trigger_time_start  TIME,
    trigger_time_end    TIME,
    trigger_days        TEXT[], -- ['MONDAY', 'FRIDAY']
    trigger_timezone    VARCHAR(50) DEFAULT 'UTC',

    -- Action
    action_type         VARCHAR(50) NOT NULL, -- 'REDUCE_RISK', 'INCREASE_RISK', 'PAUSE_TRADING', 'CLOSE_POSITIONS'
    risk_multiplier     REAL, -- 0.5 = reduce by 50%, 1.5 = increase by 50%

    -- Settings override (optional - for complex rules)
    settings_override   JSONB, -- {"max_lot_size": 2.0, "min_rr_ratio": 3.0}

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_time_rules_enabled
    ON public.time_based_risk_rules(enabled) WHERE enabled = true;

COMMENT ON TABLE public.time_based_risk_rules IS 'Automated risk rules triggered by time/events (e.g., reduce risk during NFP)';


-- ═══════════════════════════════════════════════════════════════
-- 3. TRAILING STOPS
-- Smart trailing stop management
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.trailing_stops (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id               bigint NOT NULL REFERENCES public.trading_signals(id) ON DELETE CASCADE,

    -- Configuration
    trail_distance_pips     REAL NOT NULL,
    activation_price        REAL, -- Price must hit this before trailing starts (NULL = start immediately)
    wait_for_breakeven      BOOLEAN DEFAULT false,

    -- State tracking
    is_active               BOOLEAN DEFAULT true,
    is_activated            BOOLEAN DEFAULT false, -- Has activation_price been hit?
    current_sl              REAL NOT NULL,
    highest_price_seen      REAL, -- For long positions
    lowest_price_seen       REAL, -- For short positions

    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    last_moved_at           TIMESTAMPTZ,
    times_moved             INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_trailing_stops_active
    ON public.trailing_stops(signal_id) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_trailing_stops_signal
    ON public.trailing_stops(signal_id);

COMMENT ON TABLE public.trailing_stops IS 'Trailing stop configurations for active positions';
COMMENT ON COLUMN public.trailing_stops.activation_price IS 'Wait until price hits this level before trailing starts';


-- ═══════════════════════════════════════════════════════════════
-- 4. PROFIT LOCK RULES
-- Automated scale-out and profit locking
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.profit_lock_rules (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name           VARCHAR(100) NOT NULL,
    enabled             BOOLEAN DEFAULT true,

    -- Trigger (when to execute)
    trigger_r_multiple  REAL NOT NULL, -- +2.0 = when position hits +2R profit

    -- Actions
    close_percent       REAL, -- 0.5 = close 50% of position
    move_sl_to          VARCHAR(50), -- 'BREAKEVEN', 'ENTRY', '+1R', 'TRAILING_50PIPS'

    -- Application scope
    apply_to_symbol     VARCHAR(20), -- NULL = all symbols, 'EURUSD' = specific symbol
    apply_to_entry_model VARCHAR(50), -- NULL = all, 'FLIP' = specific entry model

    -- Priority (lower number = higher priority)
    priority            INTEGER DEFAULT 100,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profit_lock_enabled
    ON public.profit_lock_rules(enabled) WHERE enabled = true;

COMMENT ON TABLE public.profit_lock_rules IS 'Automated profit-taking rules (e.g., close 50% at +2R, move SL to BE)';


-- ═══════════════════════════════════════════════════════════════
-- 5. PROFIT LOCK EXECUTIONS (Audit Log)
-- Track when profit lock rules fire
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.profit_lock_executions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id           bigint NOT NULL REFERENCES public.trading_signals(id) ON DELETE CASCADE,
    rule_id             bigint REFERENCES public.profit_lock_rules(id) ON DELETE SET NULL,

    -- Execution details
    r_multiple_at_exec  REAL NOT NULL,
    close_percent       REAL,
    new_sl              REAL,
    old_sl              REAL,

    executed_at         TIMESTAMPTZ DEFAULT NOW(),
    success             BOOLEAN DEFAULT true,
    error_message       TEXT
);

CREATE INDEX IF NOT EXISTS idx_profit_lock_exec_signal
    ON public.profit_lock_executions(signal_id);

COMMENT ON TABLE public.profit_lock_executions IS 'Audit log of profit lock rule executions';


-- ═══════════════════════════════════════════════════════════════
-- 6. ACCOUNT STRATEGIES
-- Per-account risk profiles and strategy assignments
-- ═══════════════════════════════════════════════════════════════

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


-- ═══════════════════════════════════════════════════════════════
-- 7. TRADE COPY RULES
-- Master-slave trade copying configuration
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.trade_copy_rules (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name               VARCHAR(100) NOT NULL,
    enabled                 BOOLEAN DEFAULT true,

    -- Master account
    master_account_name     VARCHAR(100) NOT NULL,

    -- Slave accounts (JSON array)
    slave_account_names     TEXT[] NOT NULL,

    -- Copy settings
    scale_by_balance        BOOLEAN DEFAULT true,
    risk_multiplier         REAL DEFAULT 1.0,
    copy_sl_tp              BOOLEAN DEFAULT true,

    -- Filters (which trades to copy)
    copy_symbols            TEXT[], -- NULL = all, ['EURUSD', 'GBPUSD'] = specific
    min_master_confidence   REAL, -- Only copy if master trade has AI confidence >= X

    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_copy_enabled
    ON public.trade_copy_rules(enabled) WHERE enabled = true;

COMMENT ON TABLE public.trade_copy_rules IS 'Trade copying rules (master → slave accounts)';


-- ═══════════════════════════════════════════════════════════════
-- 8. TRADE COPY LOG
-- Audit log of copied trades
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.trade_copy_log (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id                 bigint REFERENCES public.trade_copy_rules(id) ON DELETE SET NULL,

    -- Master trade
    master_signal_id        bigint REFERENCES public.trading_signals(id) ON DELETE CASCADE,
    master_account          VARCHAR(100),

    -- Slave trade
    slave_signal_id         bigint REFERENCES public.trading_signals(id) ON DELETE CASCADE,
    slave_account           VARCHAR(100),

    -- Copy details
    master_size             REAL,
    slave_size              REAL,
    size_multiplier         REAL,

    copied_at               TIMESTAMPTZ DEFAULT NOW(),
    success                 BOOLEAN DEFAULT true,
    error_message           TEXT
);

CREATE INDEX IF NOT EXISTS idx_trade_copy_master
    ON public.trade_copy_log(master_signal_id);

CREATE INDEX IF NOT EXISTS idx_trade_copy_slave
    ON public.trade_copy_log(slave_signal_id);

COMMENT ON TABLE public.trade_copy_log IS 'Audit log of all trade copy operations';


-- ═══════════════════════════════════════════════════════════════
-- 9. CAPITAL ALLOCATION HISTORY
-- Track capital allocation changes over time
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.capital_allocation_history (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name            VARCHAR(100) NOT NULL,

    -- Allocation change
    previous_allocation_usd REAL,
    new_allocation_usd      REAL,
    change_usd              REAL,

    -- Reason
    allocation_reason       TEXT,
    automated               BOOLEAN DEFAULT false, -- Was this an automated rebalance?

    -- Performance at time of change
    account_sharpe          REAL,
    account_win_rate        REAL,

    allocated_at            TIMESTAMPTZ DEFAULT NOW(),
    allocated_by            VARCHAR(50) DEFAULT 'UI'
);

CREATE INDEX IF NOT EXISTS idx_capital_alloc_account
    ON public.capital_allocation_history(account_name);

CREATE INDEX IF NOT EXISTS idx_capital_alloc_time
    ON public.capital_allocation_history(allocated_at DESC);

COMMENT ON TABLE public.capital_allocation_history IS 'Historical record of capital allocation changes';


-- ═══════════════════════════════════════════════════════════════
-- 10. HEDGE SUGGESTIONS
-- Auto-hedging recommendations
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.hedge_suggestions (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Portfolio state
    portfolio_snapshot          JSONB NOT NULL, -- Current positions
    total_exposure_usd          REAL NOT NULL,
    current_var                 REAL NOT NULL,

    -- Hedge recommendation
    suggested_symbol            VARCHAR(20) NOT NULL,
    suggested_side              VARCHAR(10) NOT NULL,
    suggested_size              REAL NOT NULL,
    expected_var_reduction_pct  REAL NOT NULL,

    -- Reasoning
    hedge_reason                TEXT,
    currency_exposure           JSONB, -- {"EUR": 8500, "USD": -3200}

    -- Status
    status                      VARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED'
    executed_signal_id          bigint REFERENCES public.trading_signals(id) ON DELETE SET NULL,

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    executed_at                 TIMESTAMPTZ,
    expires_at                  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hedge_suggestions_status
    ON public.hedge_suggestions(status) WHERE status = 'PENDING';

COMMENT ON TABLE public.hedge_suggestions IS 'Auto-generated hedge recommendations to reduce portfolio risk';


-- ═══════════════════════════════════════════════════════════════
-- Helper Functions
-- ═══════════════════════════════════════════════════════════════

-- Function: Get active risk config setting
CREATE OR REPLACE FUNCTION get_risk_setting(p_setting_key VARCHAR(100))
RETURNS TABLE(
    value_float REAL,
    value_bool BOOLEAN,
    value_int INTEGER,
    value_json JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.value_float,
        r.value_bool,
        r.value_int,
        r.value_json
    FROM public.risk_config_overrides r
    WHERE r.setting_key = p_setting_key
      AND r.is_active = true
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_risk_setting IS 'Retrieve active risk config override for a setting';


-- Function: Update risk setting with audit trail
CREATE OR REPLACE FUNCTION update_risk_setting(
    p_setting_key VARCHAR(100),
    p_value_float REAL DEFAULT NULL,
    p_value_bool BOOLEAN DEFAULT NULL,
    p_value_int INTEGER DEFAULT NULL,
    p_value_json JSONB DEFAULT NULL,
    p_updated_by VARCHAR(50) DEFAULT 'UI',
    p_change_reason TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_old_value TEXT;
BEGIN
    -- Get old value for audit
    SELECT COALESCE(
        value_float::TEXT,
        value_bool::TEXT,
        value_int::TEXT,
        value_json::TEXT
    ) INTO v_old_value
    FROM public.risk_config_overrides
    WHERE setting_key = p_setting_key AND is_active = true;

    -- Upsert new value
    INSERT INTO public.risk_config_overrides (
        setting_key, value_float, value_bool, value_int, value_json,
        updated_by, updated_at, previous_value, change_reason
    ) VALUES (
        p_setting_key, p_value_float, p_value_bool, p_value_int, p_value_json,
        p_updated_by, NOW(), v_old_value, p_change_reason
    )
    ON CONFLICT (setting_key) DO UPDATE SET
        value_float = EXCLUDED.value_float,
        value_bool = EXCLUDED.value_bool,
        value_int = EXCLUDED.value_int,
        value_json = EXCLUDED.value_json,
        updated_by = EXCLUDED.updated_by,
        updated_at = NOW(),
        previous_value = v_old_value,
        change_reason = EXCLUDED.change_reason;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_risk_setting IS 'Update risk setting with automatic audit trail';


-- ═══════════════════════════════════════════════════════════════
-- Seed Data: Default Profit Lock Rules
-- ═══════════════════════════════════════════════════════════════

INSERT INTO public.profit_lock_rules (rule_name, enabled, trigger_r_multiple, close_percent, move_sl_to, priority)
VALUES
    ('Default: Lock Breakeven at +1R', false, 1.0, NULL, 'BREAKEVEN', 100),
    ('Default: Scale Out 50% at +2R', false, 2.0, 0.5, '+1R', 200),
    ('Default: Trail 50 pips at +3R', false, 3.0, NULL, 'TRAILING_50PIPS', 300)
ON CONFLICT DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
-- Sample Query Examples (for documentation)
-- ═══════════════════════════════════════════════════════════════

-- Get current risk_percent (with override):
-- SELECT * FROM get_risk_setting('risk_percent');

-- Update risk_percent live:
-- SELECT update_risk_setting('risk_percent', p_value_float := 0.75, p_change_reason := 'Increased for high-confidence setup');

-- Get all active trailing stops:
-- SELECT * FROM public.trailing_stops WHERE is_active = true;

-- Get pending hedge suggestions:
-- SELECT * FROM public.hedge_suggestions WHERE status = 'PENDING' AND expires_at > NOW();
