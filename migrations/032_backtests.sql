-- 032_backtests.sql
-- Sprint 4.1: Backtest Lab — job tracking with progress + metrics.

CREATE TABLE IF NOT EXISTS public.backtests (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    progress        SMALLINT DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    start_time      TIMESTAMPTZ,
    end_time       TIMESTAMPTZ,
    config_snapshot JSONB DEFAULT '{}',
    metrics_json    JSONB DEFAULT '{}',
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtests_status ON public.backtests (status);
CREATE INDEX IF NOT EXISTS idx_backtests_created_at ON public.backtests (created_at DESC);

COMMENT ON TABLE public.backtests IS 'Sprint 4.1: Backtest Lab jobs with progress and metrics.';
