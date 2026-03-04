-- 026_clean_state_model_safe.sql
-- Idempotent version: adds only columns that don't exist yet.
-- Use this if 026 was partially applied (e.g. closed_at already exists).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'trading_signals' AND column_name = 'execution_source') THEN
    ALTER TABLE public.trading_signals ADD COLUMN execution_source VARCHAR(20) DEFAULT 'signal_only' CHECK (execution_source IN ('metaapi', 'paper', 'signal_only'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'trading_signals' AND column_name = 'broker_position_id') THEN
    ALTER TABLE public.trading_signals ADD COLUMN broker_position_id VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'trading_signals' AND column_name = 'opened_at') THEN
    ALTER TABLE public.trading_signals ADD COLUMN opened_at TIMESTAMPTZ;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'trading_signals' AND column_name = 'closed_at') THEN
    ALTER TABLE public.trading_signals ADD COLUMN closed_at TIMESTAMPTZ;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'trading_signals' AND column_name = 'last_broker_sync_at') THEN
    ALTER TABLE public.trading_signals ADD COLUMN last_broker_sync_at TIMESTAMPTZ;
  END IF;
END $$;

-- Backfill data (safe to re-run; only updates where values are NULL)

UPDATE public.trading_signals
SET closed_at = COALESCE(closed_at, exit_time, close_time, updated_at, created_at)
WHERE status = 'closed' AND closed_at IS NULL;

UPDATE public.trading_signals
SET opened_at = COALESCE(opened_at, entry_time, updated_at, created_at)
WHERE status IN ('executed', 'active') AND opened_at IS NULL;

UPDATE public.trading_signals
SET execution_source = CASE 
    WHEN broker_order_id IS NOT NULL AND broker_order_id NOT LIKE 'paper_%' THEN 'metaapi'
    WHEN mode = 'paper' OR broker_order_id LIKE 'paper_%' THEN 'paper'
    ELSE 'signal_only'
END
WHERE execution_source IS NULL OR execution_source = 'signal_only';
