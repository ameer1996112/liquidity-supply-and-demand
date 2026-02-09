-- ========================================
-- Per-Account Evaluation Settings
-- Enables running different accounts in different evaluation phases
-- simultaneously (e.g., Account A in Phase 1, Account B funded)
-- ========================================

-- STEP 1: Add evaluation columns to broker_profiles
-- ========================================
ALTER TABLE public.broker_profiles
  ADD COLUMN IF NOT EXISTS evaluation_mode boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS evaluation_phase text NOT NULL DEFAULT 'phase1'
    CHECK (evaluation_phase IN ('phase1', 'phase2', 'funded')),
  ADD COLUMN IF NOT EXISTS evaluation_start_date date,
  ADD COLUMN IF NOT EXISTS starting_balance real NOT NULL DEFAULT 10000.0,
  ADD COLUMN IF NOT EXISTS max_daily_loss_pct real NOT NULL DEFAULT 5.0,
  ADD COLUMN IF NOT EXISTS max_drawdown_pct real NOT NULL DEFAULT 10.0,
  ADD COLUMN IF NOT EXISTS profit_target real NOT NULL DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS consistency_limit_pct real NOT NULL DEFAULT 40.0;

COMMENT ON COLUMN public.broker_profiles.evaluation_mode IS
  'True if this account is in prop firm evaluation mode';
COMMENT ON COLUMN public.broker_profiles.evaluation_phase IS
  'Current evaluation phase: phase1, phase2, or funded';
COMMENT ON COLUMN public.broker_profiles.starting_balance IS
  'Account starting balance for risk calculations (not fetched from broker)';
COMMENT ON COLUMN public.broker_profiles.max_daily_loss_pct IS
  'Maximum daily loss percentage before kill switch (prop firm rule)';
COMMENT ON COLUMN public.broker_profiles.max_drawdown_pct IS
  'Maximum overall drawdown percentage (prop firm rule)';
COMMENT ON COLUMN public.broker_profiles.profit_target IS
  'Profit target in USD for current evaluation phase (0 = no target)';
COMMENT ON COLUMN public.broker_profiles.consistency_limit_pct IS
  'FTMO consistency rule: best day max % of total profit (default: 40%)';


-- STEP 2: Add index for evaluation queries
-- ========================================
CREATE INDEX IF NOT EXISTS idx_broker_profiles_evaluation
  ON public.broker_profiles(evaluation_mode, evaluation_phase)
  WHERE evaluation_mode = true;


-- STEP 3: Verification
-- ========================================
SELECT
  column_name,
  data_type,
  column_default,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'broker_profiles'
  AND column_name IN (
    'evaluation_mode', 'evaluation_phase', 'evaluation_start_date',
    'starting_balance', 'max_daily_loss_pct', 'max_drawdown_pct',
    'profit_target', 'consistency_limit_pct'
  )
ORDER BY column_name;
