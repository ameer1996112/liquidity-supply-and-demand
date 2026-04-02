-- Migration 071: Fix all stale symbol mappings for ACG-DEMO broker
--
-- Problem: Migration 025 seeded generic broker symbols (USTEC, US500) that
-- don't exist on the ACG-DEMO MetaAPI terminal. The terminal uses '.raw' suffixed
-- symbols (e.g. NAS100.raw, SPX500.raw). Database overrides take priority over
-- the correct hardcoded SYMBOL_MAP, causing ERR_MARKET_UNKNOWN_SYMBOL (4301).
--
-- Migration 045 fixed NAS100 (USTEC -> nas100.raw) but missed SPX500 (US500).
-- This migration fixes SPX500 and disables any other stale generic mappings
-- so the hardcoded map (which is correct for ACG-DEMO) takes effect.

-- Fix SPX500: US500 -> SPX500.raw (ACG-DEMO format)
UPDATE symbol_mappings
SET broker_symbol = 'SPX500.raw',
    notes = 'ACG Demo - S&P 500 cash USD (was US500 - wrong for ACG)',
    updated_at = NOW()
WHERE tv_symbol = 'SPX500'
  AND broker_symbol = 'US500';

-- Verify NAS100 fix from migration 045 was applied; if not, apply it now
UPDATE symbol_mappings
SET broker_symbol = 'NAS100.raw',
    notes = 'ACG Demo - US Tech 100 cash USD (was USTEC - wrong for ACG)',
    updated_at = NOW()
WHERE tv_symbol = 'NAS100'
  AND broker_symbol = 'USTEC';

-- Disable the test placeholder row if still enabled
UPDATE symbol_mappings
SET enabled = FALSE,
    updated_at = NOW()
WHERE tv_symbol = 'TEST_SYMBOL'
  AND enabled = TRUE;
