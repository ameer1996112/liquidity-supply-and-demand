-- Migration 014: Evaluation Progress Tracking
-- Track FTMO/prop firm challenge progress and rules

CREATE TABLE IF NOT EXISTS public.evaluation_progress (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name                VARCHAR(100) NOT NULL REFERENCES public.account_strategies(account_name) ON DELETE CASCADE,

    -- Challenge rules (configured at start)
    profit_target_usd           REAL NOT NULL,
    daily_loss_limit_pct        REAL NOT NULL,
    max_drawdown_pct            REAL NOT NULL,
    min_trading_days            INTEGER DEFAULT 0,
    consistency_max_day_pct     REAL, -- E.g., 0.40 = no single day > 40% of total profit

    -- Current state (updated daily)
    current_profit_usd          REAL DEFAULT 0,
    current_dd_pct              REAL DEFAULT 0,
    daily_loss_today_pct        REAL DEFAULT 0,
    days_traded                 INTEGER DEFAULT 0,
    largest_day_profit_pct      REAL DEFAULT 0, -- As % of total profit
    largest_day_profit_usd      REAL DEFAULT 0,

    -- Status tracking
    status                      VARCHAR(20) DEFAULT 'active'
                                CHECK (status IN ('active', 'passed', 'failed', 'paused')),
    failure_reason              TEXT,
    started_at                  TIMESTAMPTZ DEFAULT NOW(),
    completed_at                TIMESTAMPTZ,

    -- Metadata
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure one eval per account
    CONSTRAINT unique_account_eval UNIQUE(account_name)
);

-- Index for active evals
CREATE INDEX IF NOT EXISTS idx_eval_progress_account
  ON public.evaluation_progress(account_name);

CREATE INDEX IF NOT EXISTS idx_eval_progress_status
  ON public.evaluation_progress(status) WHERE status = 'active';

-- Comments
COMMENT ON TABLE public.evaluation_progress IS
  'Track FTMO/prop firm challenge progress: profit targets, drawdown limits, trading days, consistency rules';

COMMENT ON COLUMN public.evaluation_progress.profit_target_usd IS
  'Total profit required to pass challenge (e.g., $10,000 for FTMO)';

COMMENT ON COLUMN public.evaluation_progress.daily_loss_limit_pct IS
  'Maximum daily loss allowed as % of starting balance (e.g., 5% for FTMO)';

COMMENT ON COLUMN public.evaluation_progress.max_drawdown_pct IS
  'Maximum drawdown allowed from peak equity (e.g., 10% for FTMO)';

COMMENT ON COLUMN public.evaluation_progress.min_trading_days IS
  'Minimum number of trading days required (e.g., 30 for FTMO)';

COMMENT ON COLUMN public.evaluation_progress.consistency_max_day_pct IS
  'Maximum % of total profit allowed on any single day (e.g., 0.40 = 40% max)';

-- Verification query
SELECT
    'evaluation_progress' AS table_name,
    COUNT(*) AS row_count
FROM public.evaluation_progress;
