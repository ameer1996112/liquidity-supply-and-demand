-- Migration 047: Data Foundation for Prop Firm Metrics
-- Creates tables for firm metadata and challenge rules, and seeds FTMO data

CREATE TABLE IF NOT EXISTS public.prop_firm_server_mappings (
    id          bigserial PRIMARY KEY,
    server_prefix  text NOT NULL UNIQUE,  -- e.g. 'FTMO'
    firm_id        text NOT NULL,          -- e.g. 'ftmo'
    firm_display_name text NOT NULL,       -- e.g. 'FTMO'
    created_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.prop_firm_rules (
    id                  bigserial PRIMARY KEY,
    firm_id             text NOT NULL,          -- e.g. 'ftmo'
    challenge_type      text NOT NULL           -- 'phase_1' | 'phase_2' | 'funded'
        CHECK (challenge_type IN ('phase_1', 'phase_2', 'funded')),
    daily_dd_pct        real NOT NULL,          -- 5.0
    total_dd_pct        real NOT NULL,          -- 10.0
    profit_target_pct   real,                   -- NULL for funded
    min_trading_days    int NOT NULL DEFAULT 4,
    reset_tz            text NOT NULL DEFAULT 'America/New_York',
    drawdown_reference  text NOT NULL DEFAULT 'starting_balance'
        CHECK (drawdown_reference IN ('starting_balance', 'high_water_mark')),
    UNIQUE (firm_id, challenge_type)
);

INSERT INTO public.prop_firm_server_mappings (server_prefix, firm_id, firm_display_name)
VALUES ('FTMO', 'ftmo', 'FTMO')
ON CONFLICT (server_prefix) DO NOTHING;

INSERT INTO public.prop_firm_rules
    (firm_id, challenge_type, daily_dd_pct, total_dd_pct, profit_target_pct, min_trading_days, reset_tz, drawdown_reference)
VALUES
    ('ftmo', 'phase_1', 5.0, 10.0, 10.0, 4, 'America/New_York', 'starting_balance'),
    ('ftmo', 'phase_2', 5.0, 10.0, 5.0, 4, 'America/New_York', 'starting_balance'),
    ('ftmo', 'funded',  5.0, 10.0, NULL, 4, 'America/New_York', 'high_water_mark')
ON CONFLICT (firm_id, challenge_type) DO NOTHING;
