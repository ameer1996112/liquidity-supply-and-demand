-- Migration 060: Add connection tracking columns to broker_profiles
-- Enables UI to display connection health and know which account is selected for trading.

ALTER TABLE public.broker_profiles
  ADD COLUMN IF NOT EXISTS connection_status TEXT NOT NULL DEFAULT 'unknown'
    CHECK (connection_status IN ('unknown', 'connected', 'error')),
  ADD COLUMN IF NOT EXISTS connection_error TEXT,
  ADD COLUMN IF NOT EXISTS last_tested_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS selected_for_trading BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN public.broker_profiles.connection_status IS
  'Last known connection state: unknown | connected | error';
COMMENT ON COLUMN public.broker_profiles.connection_error IS
  'Error message from last failed test, NULL if connected';
COMMENT ON COLUMN public.broker_profiles.last_tested_at IS
  'Timestamp of last connection test';
COMMENT ON COLUMN public.broker_profiles.selected_for_trading IS
  'True for the single account currently used for trade execution. Only one row should be true at a time.';

-- Ensure only one profile can be selected for trading at a time via a partial unique index.
-- This prevents two profiles from being selected simultaneously.
CREATE UNIQUE INDEX IF NOT EXISTS idx_broker_profiles_single_selected
  ON public.broker_profiles (selected_for_trading)
  WHERE selected_for_trading = true;

-- Seed: mark the first active profile as selected for trading if none is selected yet.
UPDATE public.broker_profiles
SET selected_for_trading = true
WHERE id = (
  SELECT id FROM public.broker_profiles
  WHERE is_active = true
  ORDER BY id ASC
  LIMIT 1
)
AND NOT EXISTS (
  SELECT 1 FROM public.broker_profiles WHERE selected_for_trading = true
);
