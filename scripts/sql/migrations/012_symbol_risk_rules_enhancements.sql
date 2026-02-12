-- Migration 012: Enhance symbol_risk_rules with missing columns and comprehensive presets
-- Run in Supabase SQL Editor (primary database)

-- Add missing columns used by risk_engine.py
ALTER TABLE public.symbol_risk_rules
ADD COLUMN IF NOT EXISTS stop_loss_buffer_pips REAL NOT NULL DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS min_lot_size REAL NOT NULL DEFAULT 0.01,
ADD COLUMN IF NOT EXISTS lot_step REAL NOT NULL DEFAULT 0.01;

-- Update existing records with new columns
UPDATE public.symbol_risk_rules
SET stop_loss_buffer_pips = 1.0, min_lot_size = 0.01, lot_step = 0.01
WHERE stop_loss_buffer_pips IS NULL OR min_lot_size IS NULL OR lot_step IS NULL;

-- Comprehensive symbol presets for Forex, Indices, Metals, and Crypto
-- Using UPSERT pattern to update existing or insert new

-- ========== FOREX MAJOR PAIRS ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('EURUSD', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('GBPUSD', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('USDJPY', 2.0, 0.5, 0.01, 1000.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('USDCHF', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('AUDUSD', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('NZDUSD', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('USDCAD', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== FOREX CROSS PAIRS ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('EURJPY', 2.0, 0.5, 0.01, 1000.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('GBPJPY', 2.0, 0.5, 0.01, 1000.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('EURGBP', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('EURAUD', 2.0, 0.5, 0.0001, 10.0, 3, 1.0, 0.01, 0.01, TRUE),
    ('AUDJPY', 2.0, 0.5, 0.01, 1000.0, 3, 1.0, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== INDICES (US) ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('NAS100', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('US30', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('SPX500', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('US100', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== INDICES (European) ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('GER40', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('GER30', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('UK100', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('FRA40', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('ESP35', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== INDICES (Asia-Pacific) ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('JPN225', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('HK50', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE),
    ('AUS200', 1.0, 0.5, 1.0, 1.0, 2, 5.0, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== METALS ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('XAUUSD', 0.5, 0.5, 0.01, 100.0, 2, 1.0, 0.01, 0.01, TRUE),
    ('XAGUSD', 1.0, 0.5, 0.001, 5000.0, 2, 0.05, 0.01, 0.01, TRUE),
    ('XPTUSD', 0.5, 0.5, 0.01, 100.0, 1, 1.0, 0.01, 0.01, TRUE),
    ('XPDUSD', 0.5, 0.5, 0.01, 100.0, 1, 1.0, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== CRYPTO ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('BTCUSD', 0.1, 0.5, 1.0, 1.0, 1, 50.0, 0.01, 0.01, TRUE),
    ('ETHUSD', 0.5, 0.5, 1.0, 1.0, 1, 10.0, 0.01, 0.01, TRUE),
    ('BCHUSD', 1.0, 0.5, 1.0, 1.0, 1, 5.0, 0.01, 0.01, TRUE),
    ('LTCUSD', 1.0, 0.5, 1.0, 1.0, 1, 5.0, 0.01, 0.01, TRUE),
    ('XRPUSD', 2.0, 0.5, 0.0001, 10.0, 1, 0.005, 0.01, 0.01, TRUE),
    ('ADAUSD', 2.0, 0.5, 0.0001, 10.0, 1, 0.01, 0.01, 0.01, TRUE),
    ('SOLUSD', 1.0, 0.5, 1.0, 1.0, 1, 2.0, 0.01, 0.01, TRUE),
    ('DOGEUSD', 5.0, 0.5, 0.00001, 100.0, 1, 0.001, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- ========== COMMODITIES ==========
INSERT INTO public.symbol_risk_rules (symbol, max_lot_size, risk_percent, pip_size, pip_value_per_lot, max_positions, stop_loss_buffer_pips, min_lot_size, lot_step, enabled)
VALUES
    ('USOIL', 1.0, 0.5, 0.01, 10.0, 2, 0.1, 0.01, 0.01, TRUE),
    ('UKOIL', 1.0, 0.5, 0.01, 10.0, 2, 0.1, 0.01, 0.01, TRUE),
    ('NATGAS', 1.0, 0.5, 0.001, 10.0, 2, 0.05, 0.01, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    pip_size = EXCLUDED.pip_size,
    pip_value_per_lot = EXCLUDED.pip_value_per_lot,
    stop_loss_buffer_pips = EXCLUDED.stop_loss_buffer_pips,
    min_lot_size = EXCLUDED.min_lot_size,
    lot_step = EXCLUDED.lot_step,
    updated_at = NOW();

-- Verify the updates
SELECT symbol, pip_size, pip_value_per_lot, stop_loss_buffer_pips, risk_percent, max_lot_size, enabled
FROM public.symbol_risk_rules
ORDER BY
    CASE
        WHEN symbol LIKE '%USD' OR symbol LIKE 'USD%' OR symbol LIKE 'EUR%' OR symbol LIKE 'GBP%' THEN 1
        WHEN symbol IN ('NAS100', 'US30', 'SPX500', 'US100', 'GER40', 'UK100', 'FRA40', 'JPN225') THEN 2
        WHEN symbol LIKE 'XAU%' OR symbol LIKE 'XAG%' OR symbol LIKE 'XPT%' OR symbol LIKE 'XPD%' THEN 3
        WHEN symbol LIKE '%BTC%' OR symbol LIKE '%ETH%' OR symbol LIKE '%SOL%' THEN 4
        ELSE 5
    END,
    symbol;
