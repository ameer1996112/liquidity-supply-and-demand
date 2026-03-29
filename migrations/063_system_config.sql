-- Migration 063: system_config table for operator-controlled global settings
-- Allows switching trading mode (PAPER/LIVE/DRY_RUN) from the dashboard
-- without modifying Pine Script or redeploying.

CREATE TABLE IF NOT EXISTS system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default trading mode (safe default: PAPER)
INSERT INTO system_config (key, value)
VALUES ('trading_mode', 'PAPER')
ON CONFLICT (key) DO NOTHING;
