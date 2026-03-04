-- Delete all LIVE mode signals from trading_signals
-- Run this in Supabase SQL Editor when you want to start fresh.
--
-- Related tables (trade_journal, trade_reflections, pipeline_traces, etc.)
-- use ON DELETE CASCADE or ON DELETE SET NULL, so they are handled automatically.
--
-- WARNING: This is irreversible. Only run when you intend to clear all LIVE signals.

DELETE FROM public.trading_signals
WHERE UPPER(COALESCE(run_mode, 'LIVE')) = 'LIVE';
