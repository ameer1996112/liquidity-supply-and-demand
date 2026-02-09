-- Migration 018: Prop Firm Metrics Table
-- Real-time tracking of prop firm compliance metrics (FTMO/MyFundedFX)
--
-- Purpose:
-- - Track daily high water marks for drawdown calculation
-- - Include floating PnL in daily loss calculations
-- - Monitor consistency rule compliance
-- - Provide historical trend analysis
--
-- Author: Trinity Engine v3.0
-- Date: 2025-02-09

-- Create prop_firm_metrics table
CREATE TABLE IF NOT EXISTS public.prop_firm_metrics (
    id BIGSERIAL PRIMARY KEY,
    snapshot_time TIMESTAMPTZ DEFAULT NOW(),

    -- Account identification
    account_name TEXT NOT NULL DEFAULT 'default',
    broker_profile_id INTEGER REFERENCES broker_profiles(id),
    evaluation_phase TEXT NOT NULL CHECK (evaluation_phase IN ('phase1', 'phase2', 'funded')),

    -- Daily metrics (reset at 00:00 server time)
    daily_start_balance REAL NOT NULL,
    daily_high_water_mark REAL NOT NULL,  -- Highest equity reached today
    daily_pnl_closed REAL NOT NULL,        -- Closed PnL only
    daily_pnl_floating REAL NOT NULL,      -- Open position MTM
    daily_pnl_total REAL NOT NULL,         -- Closed + Floating

    -- Drawdown calculations
    current_equity REAL NOT NULL,
    max_historical_equity REAL NOT NULL,   -- All-time high (for trailing DD)
    daily_drawdown_pct REAL NOT NULL,      -- (High Water Mark - Current) / Daily Start
    trailing_drawdown_pct REAL NOT NULL,   -- (Historical Peak - Current) / Historical Peak

    -- Prop firm limits
    daily_loss_limit_usd REAL NOT NULL,
    max_drawdown_limit_pct REAL NOT NULL,

    -- Status flags
    daily_loss_breach BOOLEAN DEFAULT FALSE,
    drawdown_breach BOOLEAN DEFAULT FALSE,
    kill_switch_engaged BOOLEAN DEFAULT FALSE,

    -- Trade statistics
    trades_today INTEGER DEFAULT 0,
    winning_trades_today INTEGER DEFAULT 0,
    losing_trades_today INTEGER DEFAULT 0,

    -- Consistency tracking
    largest_win_today REAL DEFAULT 0,
    largest_loss_today REAL DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prop_firm_metrics_snapshot_time
    ON public.prop_firm_metrics(snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_prop_firm_metrics_account
    ON public.prop_firm_metrics(account_name, snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_prop_firm_metrics_phase
    ON public.prop_firm_metrics(evaluation_phase);

CREATE INDEX IF NOT EXISTS idx_prop_firm_metrics_breach
    ON public.prop_firm_metrics(daily_loss_breach, drawdown_breach);

-- Enable RLS
ALTER TABLE public.prop_firm_metrics ENABLE ROW LEVEL SECURITY;

-- Create policy for read access
CREATE POLICY "Enable read for all users"
    ON public.prop_firm_metrics
    FOR SELECT
    USING (true);

-- Create policy for insert (service role only for snapshots)
CREATE POLICY "Enable insert for service role"
    ON public.prop_firm_metrics
    FOR INSERT
    WITH CHECK (true);

-- Grant permissions
GRANT SELECT ON public.prop_firm_metrics TO anon;
GRANT SELECT ON public.prop_firm_metrics TO authenticated;
GRANT ALL ON public.prop_firm_metrics TO service_role;
GRANT USAGE, SELECT ON SEQUENCE prop_firm_metrics_id_seq TO anon;
GRANT USAGE, SELECT ON SEQUENCE prop_firm_metrics_id_seq TO authenticated;
GRANT ALL ON SEQUENCE prop_firm_metrics_id_seq TO service_role;

-- Create function to clean old snapshots (keep last 30 days only)
CREATE OR REPLACE FUNCTION cleanup_old_prop_firm_snapshots()
RETURNS void AS $$
BEGIN
    DELETE FROM public.prop_firm_metrics
    WHERE snapshot_time < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create scheduled job to run cleanup weekly (if pg_cron is available)
-- Note: Uncomment if your Supabase project has pg_cron enabled
-- SELECT cron.schedule(
--     'cleanup-prop-firm-snapshots',
--     '0 0 * * 0',  -- Every Sunday at midnight
--     $$SELECT cleanup_old_prop_firm_snapshots()$$
-- );

-- Migration complete
-- To apply: Run this SQL in your Supabase SQL Editor
