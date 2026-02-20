-- 026_clean_state_model.sql
-- Add explicit position state tracking fields to resolve ghost positions

-- Add columns for explicit execution lifecycle
ALTER TABLE public.trading_signals
ADD COLUMN execution_source VARCHAR(20) DEFAULT 'signal_only' CHECK (execution_source IN ('metaapi', 'paper', 'signal_only')),
ADD COLUMN broker_position_id VARCHAR(255),
ADD COLUMN opened_at TIMESTAMPTZ,
ADD COLUMN closed_at TIMESTAMPTZ,
ADD COLUMN last_broker_sync_at TIMESTAMPTZ;

-- Backfill data based on existing columns

-- 1. Any 'closed' row needs a closed_at (borrow from exit_time or updated_at)
UPDATE public.trading_signals
SET closed_at = COALESCE(exit_time, close_time, updated_at, created_at)
WHERE status = 'closed';

-- 2. Any 'executed' row needs an opened_at
UPDATE public.trading_signals
SET opened_at = COALESCE(entry_time, updated_at, created_at)
WHERE status IN ('executed', 'active');

-- 3. Backfill execution_source (approximate based on broker_order_id presence or mode)
UPDATE public.trading_signals
SET execution_source = CASE 
    WHEN broker_order_id IS NOT NULL AND broker_order_id NOT LIKE 'paper_%' THEN 'metaapi'
    WHEN mode = 'paper' OR broker_order_id LIKE 'paper_%' THEN 'paper'
    ELSE 'signal_only'
END;
