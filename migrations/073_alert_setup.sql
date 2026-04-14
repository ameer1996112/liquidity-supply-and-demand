-- 073_alert_setup.sql
-- Approved pair configs and alert batches for TradingView alert deployment.

CREATE TABLE IF NOT EXISTS public.approved_pair_configs (
    id                  UUID PRIMARY KEY,
    pair                VARCHAR(32) NOT NULL,
    timeframe           VARCHAR(16) NOT NULL,
    status              VARCHAR(24) NOT NULL CHECK (status IN ('candidate', 'approved', 'archived')),
    params              JSONB NOT NULL DEFAULT '{}',
    risk_weight         NUMERIC(10, 4) NOT NULL DEFAULT 1.0,
    source_run_id       UUID,
    source_score        NUMERIC(18, 8),
    source_metrics      JSONB NOT NULL DEFAULT '{}',
    notes               TEXT,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pair, timeframe)
);

CREATE TABLE IF NOT EXISTS public.alert_batches (
    id                  UUID PRIMARY KEY,
    status              VARCHAR(24) NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
    source_mode         VARCHAR(24) NOT NULL,
    timeframe           VARCHAR(16) NOT NULL,
    pairs               JSONB NOT NULL DEFAULT '[]',
    alert_name_prefix   TEXT,
    webhook_url         TEXT,
    use_approved_weights BOOLEAN NOT NULL DEFAULT TRUE,
    pair_risk_weights   JSONB NOT NULL DEFAULT '{}',
    approved_config_ids JSONB NOT NULL DEFAULT '[]',
    config_snapshot     JSONB NOT NULL DEFAULT '[]',
    created_by          TEXT,
    notes               TEXT,
    summary             JSONB NOT NULL DEFAULT '{}',
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.alert_batch_results (
    id                  BIGSERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL REFERENCES public.alert_batches(id) ON DELETE CASCADE,
    pair                VARCHAR(32) NOT NULL,
    timeframe           VARCHAR(16) NOT NULL,
    status              VARCHAR(24) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    params              JSONB NOT NULL DEFAULT '{}',
    config_snapshot     JSONB NOT NULL DEFAULT '{}',
    alert_name          TEXT,
    alert_id            TEXT,
    error_message       TEXT,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, pair, timeframe)
);

CREATE TABLE IF NOT EXISTS public.alert_batch_events (
    id                  BIGSERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL REFERENCES public.alert_batches(id) ON DELETE CASCADE,
    event_type          VARCHAR(32) NOT NULL CHECK (event_type IN ('batch_started', 'pair_started', 'pair_completed', 'pair_failed', 'log', 'batch_finished', 'batch_cancelled')),
    pair                VARCHAR(32),
    payload             JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approved_pair_configs_pair_timeframe
    ON public.approved_pair_configs (pair, timeframe);

CREATE INDEX IF NOT EXISTS idx_approved_pair_configs_status_created_at
    ON public.approved_pair_configs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_batches_status_created_at
    ON public.alert_batches (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_batch_results_batch_id_pair
    ON public.alert_batch_results (batch_id, pair);

CREATE INDEX IF NOT EXISTS idx_alert_batch_events_batch_id_created_at
    ON public.alert_batch_events (batch_id, created_at DESC);

COMMENT ON TABLE public.approved_pair_configs IS 'Approved pair configs used to build TradingView alert batches.';
COMMENT ON TABLE public.alert_batches IS 'Alert Setup batches created from approved configs.';
COMMENT ON TABLE public.alert_batch_results IS 'Per-pair alert deployment results for each batch.';
COMMENT ON TABLE public.alert_batch_events IS 'Append-only event feed for alert batches.';
