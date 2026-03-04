-- Reset All Positions — Start from the beginning
-- Run this in Supabase SQL Editor when you want to clear all position data.
--
-- This script:
--   1. Truncates position_snapshots (broker position cache from MetaAPI)
--   2. Deletes all trading_signals (LIVE + PAPER)
--
-- Related tables (trade_journal, trade_reflections, pipeline_traces, trailing_stops, etc.)
-- use ON DELETE CASCADE or ON DELETE SET NULL, so they are handled automatically.
--
-- WARNING: This is irreversible. Only run when you intend to fully reset.

BEGIN;

-- 1. Clear broker position cache (reconciliation snapshots)
TRUNCATE TABLE public.position_snapshots;

-- 2. Delete all trading signals (LIVE and PAPER)
DELETE FROM public.trading_signals;

COMMIT;
