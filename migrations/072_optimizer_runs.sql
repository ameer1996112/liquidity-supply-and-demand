-- 072_optimizer_runs.sql
-- UI-launched optimizer runs, events, and per-symbol results.

CREATE TABLE IF NOT EXISTS public.optimizer_runs (
    id              UUID PRIMARY KEY,
    status          VARCHAR(24) NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
    mode            VARCHAR(32) NOT NULL,
    workers         INTEGER NOT NULL CHECK (workers > 0),
    pairs           JSONB NOT NULL DEFAULT '[]',
    n_trials        INTEGER NOT NULL CHECK (n_trials > 0),
    dd_limit        NUMERIC(10, 4) NOT NULL,
    dry_run         BOOLEAN NOT NULL DEFAULT FALSE,
    created_by      TEXT,
    summary         JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_run_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    event_type      VARCHAR(32) NOT NULL CHECK (event_type IN ('run_started', 'pair_started', 'pair_completed', 'pair_failed', 'log', 'run_finished', 'run_cancelled')),
    worker_id       INTEGER,
    symbol          VARCHAR(32),
    payload         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_run_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    symbol          VARCHAR(32) NOT NULL,
    status          VARCHAR(24) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    params          JSONB NOT NULL DEFAULT '{}',
    metrics         JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_optimizer_runs_status_created_at
    ON public.optimizer_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimizer_run_events_run_id_created_at
    ON public.optimizer_run_events (run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimizer_run_results_run_id_symbol
    ON public.optimizer_run_results (run_id, symbol);

COMMENT ON TABLE public.optimizer_runs IS 'UI-launched optimizer runs for TradingView parallel_runner.';
COMMENT ON TABLE public.optimizer_run_events IS 'Append-only event feed for optimizer runs.';
COMMENT ON TABLE public.optimizer_run_results IS 'Per-symbol optimizer results for each run.';
