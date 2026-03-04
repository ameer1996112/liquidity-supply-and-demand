-- Migration 036: Reconciliation metadata on account_strategies
--
-- Adds per-account reconciliation status used by /api/reconcile/status
-- and the Portfolio Command Center UI.

ALTER TABLE public.account_strategies
ADD COLUMN IF NOT EXISTS last_reconcile_time TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_reconcile_drift_count INTEGER DEFAULT 0;

COMMENT ON COLUMN public.account_strategies.last_reconcile_time IS
  'Timestamp of last reconciliation run for this account (positions vs broker).';

COMMENT ON COLUMN public.account_strategies.last_reconcile_drift_count IS
  'Number of drift items (EXTERNAL, MISSING_ON_BROKER, EXTERNAL_ORDER) detected in the last reconciliation run.';

