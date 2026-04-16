-- 081_signal_setup_evidence_image_url.sql
-- Add convenience image URL storage for persisted setup evidence.

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS image_url TEXT;

COMMENT ON COLUMN public.trading_signals.image_url IS
  'Convenience URL for the setup evidence focus image used by notifications and journal surfaces.';
