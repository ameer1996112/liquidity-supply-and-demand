-- 080_signal_setup_evidence.sql
-- Persist provider-backed setup evidence for notifications and journal surfaces.

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS setup_evidence JSONB;

COMMENT ON COLUMN public.trading_signals.setup_evidence IS
  'Provider-backed setup evidence bundle (focus zone, focus image, pine snapshot).';
