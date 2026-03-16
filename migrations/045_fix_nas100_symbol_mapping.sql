-- Migration 045: Fix NAS100 broker symbol mapping for ACG account
--
-- ACG MT5 uses 'nas100.raw' (US Tech 100 cash - USD), not 'USTEC'.
-- The wrong mapping caused ERR_MARKET_UNKNOWN_SYMBOL on every NAS100 signal.

UPDATE symbol_mappings
SET broker_symbol = 'nas100.raw',
    notes = 'ACG Demo - US Tech 100 cash USD',
    updated_at = NOW()
WHERE tv_symbol = 'NAS100'
  AND broker_symbol = 'USTEC';
