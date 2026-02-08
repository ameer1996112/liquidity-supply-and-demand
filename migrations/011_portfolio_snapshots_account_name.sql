-- Migration 011: Add account_name support to portfolio_snapshots
-- Aligns with migration 010's multi-account architecture

-- Add account_name column to portfolio_snapshots
ALTER TABLE public.portfolio_snapshots
ADD COLUMN IF NOT EXISTS account_name VARCHAR(100);

-- Add foreign key constraint (references account_strategies table)
-- Note: Using ON DELETE SET NULL to preserve historical snapshots even if account is deleted
ALTER TABLE public.portfolio_snapshots
ADD CONSTRAINT fk_portfolio_snapshots_account
FOREIGN KEY (account_name) REFERENCES public.account_strategies(account_name)
ON DELETE SET NULL;

-- Add index for efficient account-based queries
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_account
ON public.portfolio_snapshots(account_name);

-- Add composite index for efficient account + time queries
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_account_time
ON public.portfolio_snapshots(account_name, snapshot_time DESC)
WHERE account_name IS NOT NULL;

-- Add unique constraint to prevent duplicate snapshots (account + time + run_mode)
-- Note: Using partial index to allow NULL account_name for legacy data
CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_snapshots_account_time_mode
ON public.portfolio_snapshots(account_name, snapshot_time, run_mode)
WHERE account_name IS NOT NULL;

-- Drop the old function first (from migration 008)
DROP FUNCTION IF EXISTS insert_portfolio_snapshot(
    REAL, REAL, REAL, REAL, REAL, INTEGER, REAL, JSONB, JSONB, TEXT
);

-- Create the new helper function with full parameter list
CREATE OR REPLACE FUNCTION insert_portfolio_snapshot(
    p_total_equity REAL,
    p_var_95_1d REAL,
    p_var_99_1d REAL DEFAULT NULL,
    p_cvar_95 REAL DEFAULT NULL,
    p_portfolio_vol REAL DEFAULT NULL,
    p_position_count INTEGER DEFAULT 0,
    p_correlation_avg REAL DEFAULT NULL,
    p_positions JSONB DEFAULT '[]'::jsonb,
    p_sector_exposure JSONB DEFAULT '{}'::jsonb,
    p_run_mode TEXT DEFAULT 'LIVE',
    p_account_name VARCHAR(100) DEFAULT NULL,
    p_account_balance REAL DEFAULT NULL,
    p_daily_pnl REAL DEFAULT NULL,
    p_var_limit_usd REAL DEFAULT NULL,
    p_var_utilization_pct REAL DEFAULT NULL,
    p_total_exposure REAL DEFAULT NULL,
    p_net_exposure REAL DEFAULT NULL,
    p_max_correlation REAL DEFAULT NULL,
    p_correlation_matrix JSONB DEFAULT '{}'::jsonb,
    p_risk_contribution JSONB DEFAULT '{}'::jsonb,
    p_sharpe_ratio REAL DEFAULT NULL
) RETURNS bigint AS $$
DECLARE
    snapshot_id bigint;
BEGIN
    INSERT INTO public.portfolio_snapshots (
        total_equity,
        account_balance,
        daily_pnl,
        var_95_1d,
        var_99_1d,
        cvar_95,
        var_limit_usd,
        var_utilization_pct,
        portfolio_vol,
        sharpe_ratio,
        total_exposure,
        net_exposure,
        position_count,
        correlation_avg,
        max_correlation,
        positions,
        correlation_matrix,
        sector_exposure,
        risk_contribution,
        run_mode,
        account_name
    ) VALUES (
        p_total_equity,
        p_account_balance,
        p_daily_pnl,
        p_var_95_1d,
        p_var_99_1d,
        p_cvar_95,
        p_var_limit_usd,
        p_var_utilization_pct,
        p_portfolio_vol,
        p_sharpe_ratio,
        p_total_exposure,
        p_net_exposure,
        p_position_count,
        p_correlation_avg,
        p_max_correlation,
        p_positions,
        p_correlation_matrix,
        p_sector_exposure,
        p_risk_contribution,
        p_run_mode,
        p_account_name
    ) RETURNING id INTO snapshot_id;

    RETURN snapshot_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON COLUMN public.portfolio_snapshots.account_name IS 'Account name for multi-account support (NULL = aggregated portfolio)';
COMMENT ON FUNCTION insert_portfolio_snapshot IS 'Insert portfolio snapshot with full metrics (updated for multi-account support)';

-- Sample queries for multi-account snapshots
-- Get latest snapshot for specific account:
-- SELECT * FROM public.portfolio_snapshots WHERE account_name = 'MyAccount' ORDER BY snapshot_time DESC LIMIT 1;

-- Get aggregated portfolio snapshot (NULL account_name):
-- SELECT * FROM public.portfolio_snapshots WHERE account_name IS NULL ORDER BY snapshot_time DESC LIMIT 1;

-- Get VaR trend for all accounts over last 7 days:
-- SELECT account_name, snapshot_time, var_95_1d, var_utilization_pct
-- FROM public.portfolio_snapshots
-- WHERE snapshot_time >= NOW() - INTERVAL '7 days'
-- ORDER BY account_name, snapshot_time;
