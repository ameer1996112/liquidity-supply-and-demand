-- Migration 007: Transaction Cost Analysis (TCA) Execution Metrics
-- Purpose: Track execution quality metrics (slippage, latency, spread costs)
-- Author: AI Trading System - TCA Module
-- Date: 2026-02-07

-- Create TCA execution metrics table
CREATE TABLE IF NOT EXISTS public.tca_execution_metrics (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id               bigint NOT NULL REFERENCES public.trading_signals(id) ON DELETE CASCADE,
    broker_profile_id       bigint REFERENCES public.broker_profiles(id) ON DELETE SET NULL,

    -- Price tracking
    intended_entry_price    REAL NOT NULL,
    actual_fill_price       REAL,
    slippage_pips           REAL,
    slippage_bps            REAL,        -- Basis points (1 bps = 0.01%)
    slippage_usd            REAL,

    -- Market conditions at execution
    bid_price               REAL,
    ask_price               REAL,
    spread_pips             REAL,
    spread_cost_usd         REAL,
    volatility_atr          REAL,        -- ATR at execution time

    -- Latency tracking (milliseconds)
    signal_to_submit_ms     INTEGER,     -- created_at → submitted_at
    submit_to_fill_ms       INTEGER,     -- submitted_at → filled_at
    total_execution_ms      INTEGER,     -- Total time

    -- Execution details
    execution_method        TEXT DEFAULT 'market', -- market, limit, iceberg, twap
    order_type              TEXT,        -- buy, sell
    executed_volume         REAL,        -- Lots filled

    -- Quality metrics
    implementation_shortfall REAL,      -- Price moved against us while executing
    arrival_price           REAL,        -- Price when signal arrived

    -- Timestamps
    signal_created_at       TIMESTAMPTZ NOT NULL,
    order_submitted_at      TIMESTAMPTZ,
    order_filled_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),

    -- Alert flags
    exceeds_slippage_threshold BOOLEAN DEFAULT FALSE,
    exceeds_latency_threshold  BOOLEAN DEFAULT FALSE
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_tca_signal_id
    ON public.tca_execution_metrics(signal_id);

CREATE INDEX IF NOT EXISTS idx_tca_broker_profile
    ON public.tca_execution_metrics(broker_profile_id)
    WHERE broker_profile_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tca_created_at
    ON public.tca_execution_metrics(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_signal_created
    ON public.tca_execution_metrics(signal_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_alerts
    ON public.tca_execution_metrics(created_at DESC)
    WHERE exceeds_slippage_threshold = TRUE OR exceeds_latency_threshold = TRUE;

-- Row-level security
ALTER TABLE public.tca_execution_metrics ENABLE ROW LEVEL SECURITY;

-- Policy: Allow all operations for service role
CREATE POLICY "Allow all for service role"
    ON public.tca_execution_metrics
    FOR ALL
    USING (true);

-- Comments
COMMENT ON TABLE public.tca_execution_metrics IS
    'Transaction Cost Analysis metrics for execution quality monitoring';

COMMENT ON COLUMN public.tca_execution_metrics.slippage_pips IS
    'Slippage in pips (positive = favorable fill, negative = unfavorable)';

COMMENT ON COLUMN public.tca_execution_metrics.slippage_bps IS
    'Slippage in basis points (1 bps = 0.01%)';

COMMENT ON COLUMN public.tca_execution_metrics.implementation_shortfall IS
    'Price impact: difference between arrival price and execution price';

COMMENT ON COLUMN public.tca_execution_metrics.exceeds_slippage_threshold IS
    'True if slippage exceeds configured alert threshold';

COMMENT ON COLUMN public.tca_execution_metrics.exceeds_latency_threshold IS
    'True if execution latency exceeds configured alert threshold';
