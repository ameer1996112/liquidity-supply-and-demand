-- Migration 002: Per-symbol risk rules
-- Run in Supabase SQL Editor (primary database)

CREATE TABLE IF NOT EXISTS public.symbol_risk_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL UNIQUE,
    max_lot_size REAL NOT NULL DEFAULT 1.0,
    risk_percent REAL NOT NULL DEFAULT 1.0,
    pip_size REAL NOT NULL DEFAULT 0.0001,
    pip_value_per_lot REAL NOT NULL DEFAULT 10.0,
    max_positions INTEGER NOT NULL DEFAULT 3,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_symbol_risk_rules_symbol
    ON public.symbol_risk_rules(symbol);

ALTER TABLE public.symbol_risk_rules DISABLE ROW LEVEL SECURITY;

-- Pre-seed common trading symbols with correct pip characteristics
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, enabled)
VALUES
    ('XAUUSD', 0.50, 1.0, 0.01,   100.0,  2, TRUE),
    ('EURUSD', 1.00, 1.0, 0.0001,  10.0,  3, TRUE),
    ('GBPUSD', 1.00, 1.0, 0.0001,  10.0,  3, TRUE),
    ('USDJPY', 1.00, 1.0, 0.01,  1000.0,  3, TRUE),
    ('NAS100', 0.50, 0.5, 1.0,      1.0,  1, TRUE),
    ('US30',   0.50, 0.5, 1.0,      1.0,  1, TRUE)
ON CONFLICT (symbol) DO NOTHING;
