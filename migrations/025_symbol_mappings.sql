-- Migration 025: Symbol Mappings Table
-- Purpose: Map TradingView symbols to broker-specific MT5 symbols
-- Context: Fixes "Unknown symbol" errors when TV sends NAS100 but broker uses USTEC

-- Create symbol_mappings table
CREATE TABLE IF NOT EXISTS public.symbol_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tv_symbol TEXT NOT NULL,
    broker_symbol TEXT NOT NULL,
    broker_name TEXT DEFAULT 'MetaAPI',
    notes TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tv_symbol, broker_name)
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_symbol_mappings_tv_symbol
    ON public.symbol_mappings(tv_symbol);

-- Disable RLS (system table, managed by backend)
ALTER TABLE public.symbol_mappings DISABLE ROW LEVEL SECURITY;

-- Add comment for documentation
COMMENT ON TABLE public.symbol_mappings IS
'Maps TradingView symbols to broker-specific MT5 symbols. Used by SymbolMapper service to translate symbols before execution.';

-- ============================================================================
-- PRE-SEED COMMON BROKER-SPECIFIC MAPPINGS
-- ============================================================================
-- These are examples - adjust based on YOUR broker's symbol names!
-- Check your MT5 platform's "Market Watch" to see exact symbol names.

-- Example: Common broker variations
INSERT INTO public.symbol_mappings (tv_symbol, broker_symbol, broker_name, notes, enabled)
VALUES
    -- US Indices (most common variations)
    ('NAS100', 'USTEC', 'MetaAPI', 'Nasdaq 100 - MetaAPI standard', TRUE),
    ('SPX500', 'US500', 'MetaAPI', 'S&P 500 - MetaAPI standard', TRUE),

    -- Uncomment and adjust if your broker uses different names:
    -- ('NAS100', 'NQ=F', 'IC Markets', 'IC Markets Nasdaq futures', TRUE),
    -- ('SPX500', 'SPX500', 'FTMO', 'FTMO S&P 500', TRUE),
    -- ('XAUUSD', 'GOLD', 'XM', 'XM Gold spot', TRUE),

    -- Placeholder row for testing
    ('TEST_SYMBOL', 'TEST_BROKER_SYMBOL', 'Test Broker', 'Example mapping for testing', FALSE)

ON CONFLICT (tv_symbol, broker_name) DO NOTHING;

-- ============================================================================
-- HELPER VIEW: Active Symbol Mappings
-- ============================================================================
-- Shows only enabled mappings for quick reference

CREATE OR REPLACE VIEW public.active_symbol_mappings AS
SELECT
    tv_symbol,
    broker_symbol,
    broker_name,
    notes,
    created_at
FROM public.symbol_mappings
WHERE enabled = TRUE
ORDER BY broker_name, tv_symbol;

COMMENT ON VIEW public.active_symbol_mappings IS
'Lists all enabled symbol mappings. Use this to verify your broker symbol translations.';

-- ============================================================================
-- USAGE INSTRUCTIONS
-- ============================================================================
-- To add a custom mapping for YOUR broker:
--
-- 1. Find the correct symbol name in MT5 Market Watch
-- 2. Insert a mapping:
--
--    INSERT INTO public.symbol_mappings (tv_symbol, broker_symbol, broker_name, notes)
--    VALUES ('NAS100', 'YOUR_BROKER_SYMBOL_HERE', 'Your Broker Name', 'Notes')
--    ON CONFLICT (tv_symbol, broker_name) DO UPDATE
--    SET broker_symbol = EXCLUDED.broker_symbol,
--        notes = EXCLUDED.notes,
--        updated_at = NOW();
--
-- 3. Restart the worker to reload mappings
--
-- Example for FTMO broker:
--    INSERT INTO public.symbol_mappings (tv_symbol, broker_symbol, broker_name)
--    VALUES ('NAS100', 'USTEC', 'FTMO');
--
-- ============================================================================
