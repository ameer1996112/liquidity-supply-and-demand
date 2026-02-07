-- Migration: Portfolio Risk Management Tables
-- Creates tables for storing portfolio snapshots and risk metrics

-- ═══════════════════════════════════════════════════════════════
-- Portfolio Snapshots Table
-- Stores historical portfolio risk metrics for trend analysis
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.portfolio_snapshots (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_time       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Account metrics
    total_equity        REAL NOT NULL,
    account_balance     REAL,
    daily_pnl           REAL,

    -- VaR metrics
    var_95_1d           REAL,  -- 1-day VaR at 95% confidence
    var_99_1d           REAL,  -- 1-day VaR at 99% confidence
    cvar_95             REAL,  -- Conditional VaR (Expected Shortfall)
    var_limit_usd       REAL,  -- VaR limit at time of snapshot
    var_utilization_pct REAL,  -- VaR utilization percentage

    -- Portfolio metrics
    portfolio_vol       REAL,  -- Annualized portfolio volatility
    sharpe_ratio        REAL,  -- Sharpe ratio (if available)
    total_exposure      REAL,  -- Total notional exposure
    net_exposure        REAL,  -- Net long/short exposure
    position_count      INTEGER DEFAULT 0,

    -- Correlation metrics
    correlation_avg     REAL,  -- Average pairwise correlation
    max_correlation     REAL,  -- Maximum pairwise correlation

    -- Detailed snapshots (JSONB for flexibility)
    positions           JSONB DEFAULT '[]'::jsonb,  -- Array of position objects
    correlation_matrix  JSONB DEFAULT '{}'::jsonb,  -- Full correlation matrix
    sector_exposure     JSONB DEFAULT '{}'::jsonb,  -- Sector exposure breakdown
    risk_contribution   JSONB DEFAULT '{}'::jsonb,  -- Risk contribution per position

    -- Metadata
    run_mode            TEXT,  -- LIVE, PAPER, DRY_RUN
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_time
    ON public.portfolio_snapshots(snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_mode
    ON public.portfolio_snapshots(run_mode);

-- Row Level Security (disable for now, enable in production)
ALTER TABLE public.portfolio_snapshots DISABLE ROW LEVEL SECURITY;

-- Comments for documentation
COMMENT ON TABLE public.portfolio_snapshots IS 'Historical portfolio risk metrics snapshots';
COMMENT ON COLUMN public.portfolio_snapshots.var_95_1d IS '1-day Value at Risk at 95% confidence level (USD)';
COMMENT ON COLUMN public.portfolio_snapshots.cvar_95 IS 'Conditional VaR / Expected Shortfall at 95% (USD)';
COMMENT ON COLUMN public.portfolio_snapshots.portfolio_vol IS 'Annualized portfolio volatility (%)';
COMMENT ON COLUMN public.portfolio_snapshots.positions IS 'Array of position objects with symbol, size, notional, etc.';
COMMENT ON COLUMN public.portfolio_snapshots.correlation_matrix IS 'NxN correlation matrix as nested array';
COMMENT ON COLUMN public.portfolio_snapshots.sector_exposure IS 'Sector exposure breakdown {sector: {exposure_usd, exposure_pct}}';
COMMENT ON COLUMN public.portfolio_snapshots.risk_contribution IS 'VaR contribution per position {symbol: contribution_pct}';


-- ═══════════════════════════════════════════════════════════════
-- Helper Function: Insert Portfolio Snapshot
-- ═══════════════════════════════════════════════════════════════

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
    p_run_mode TEXT DEFAULT 'LIVE'
) RETURNS bigint AS $$
DECLARE
    snapshot_id bigint;
BEGIN
    INSERT INTO public.portfolio_snapshots (
        total_equity,
        var_95_1d,
        var_99_1d,
        cvar_95,
        portfolio_vol,
        position_count,
        correlation_avg,
        positions,
        sector_exposure,
        run_mode
    ) VALUES (
        p_total_equity,
        p_var_95_1d,
        p_var_99_1d,
        p_cvar_95,
        p_portfolio_vol,
        p_position_count,
        p_correlation_avg,
        p_positions,
        p_sector_exposure,
        p_run_mode
    ) RETURNING id INTO snapshot_id;

    RETURN snapshot_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION insert_portfolio_snapshot IS 'Helper function to insert a portfolio snapshot';


-- ═══════════════════════════════════════════════════════════════
-- Sample Query Examples (for documentation)
-- ═══════════════════════════════════════════════════════════════

-- Get latest portfolio snapshot:
-- SELECT * FROM public.portfolio_snapshots ORDER BY snapshot_time DESC LIMIT 1;

-- Get VaR trend over last 7 days:
-- SELECT snapshot_time, var_95_1d, var_utilization_pct
-- FROM public.portfolio_snapshots
-- WHERE snapshot_time >= NOW() - INTERVAL '7 days'
-- ORDER BY snapshot_time;

-- Get sector exposure from latest snapshot:
-- SELECT sector_exposure FROM public.portfolio_snapshots
-- ORDER BY snapshot_time DESC LIMIT 1;
