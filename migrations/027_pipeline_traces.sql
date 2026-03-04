-- 027_pipeline_traces.sql
-- End-to-end latency trace per signal pipeline run.
-- One row per correlation_id (injected by WorkerSubject).
-- Populated incrementally by TraceObserver via UPSERT.

CREATE TABLE IF NOT EXISTS public.pipeline_traces (
    -- ── Identity ─────────────────────────────────────────────────────────────
    id              BIGSERIAL PRIMARY KEY,
    trace_id        UUID        NOT NULL DEFAULT gen_random_uuid(),
    correlation_id  VARCHAR(64) NOT NULL UNIQUE,   -- WorkerSubject uuid4().hex
    signal_id       BIGINT      REFERENCES public.trading_signals(id) ON DELETE SET NULL,
    account_id      VARCHAR(128),                  -- broker_profile name / "default"
    symbol          VARCHAR(32),
    run_mode        VARCHAR(16),                   -- PAPER | LIVE | DRY_RUN

    -- ── Hop timestamps (UTC) ─────────────────────────────────────────────────
    -- Each field is set once; NULL means that hop hasn't been reached yet.
    received_at         TIMESTAMPTZ,   -- SIGNAL_RECEIVED observer event
    enqueued_at         TIMESTAMPTZ,   -- future: set by API at webhook ingest
    dequeued_at         TIMESTAMPTZ,   -- future: set at transport.dequeue()
    validated_at        TIMESTAMPTZ,   -- future: after consumer_validator passes
    risk_started_at     TIMESTAMPTZ,   -- future: before MAS Council
    risk_finished_at    TIMESTAMPTZ,   -- future: after MAS Council decision
    exec_started_at     TIMESTAMPTZ,   -- future: before logic.process_trade
    exec_submitted_at   TIMESTAMPTZ,   -- ORDER_SUBMITTED observer event
    broker_ack_at       TIMESTAMPTZ,   -- future: broker HTTP response
    broker_confirmed_at TIMESTAMPTZ,   -- future: position confirmed open
    reconciled_at       TIMESTAMPTZ,   -- future: account_sync reconciliation
    error_at            TIMESTAMPTZ,   -- ERROR observer event (NULL if no error)

    -- ── Derived durations (ms, computed at query time) ────────────────────
    -- These are VIEW-level columns; no need to store them.
    -- See the pipeline_trace_durations view below.

    -- ── Error info ───────────────────────────────────────────────────────────
    error_type      VARCHAR(128),
    error_message   TEXT,

    -- ── Bookkeeping ──────────────────────────────────────────────────────────
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trigger: keep updated_at current
CREATE OR REPLACE FUNCTION public.set_pipeline_traces_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_pipeline_traces_updated_at ON public.pipeline_traces;
CREATE TRIGGER trg_pipeline_traces_updated_at
    BEFORE UPDATE ON public.pipeline_traces
    FOR EACH ROW EXECUTE FUNCTION public.set_pipeline_traces_updated_at();

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_correlation_id
    ON public.pipeline_traces (correlation_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_traces_signal_id
    ON public.pipeline_traces (signal_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_traces_account_id
    ON public.pipeline_traces (account_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_traces_received_at
    ON public.pipeline_traces (received_at DESC);

-- ── Convenience view: derived durations in ms ────────────────────────────────
CREATE OR REPLACE VIEW public.pipeline_trace_durations AS
SELECT
    correlation_id,
    signal_id,
    account_id,
    symbol,
    run_mode,

    received_at,
    exec_submitted_at,
    error_at,

    -- queue → worker (enqueue → dequeue)
    CASE WHEN dequeued_at IS NOT NULL AND enqueued_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (dequeued_at - enqueued_at)) * 1000
    END AS queue_wait_ms,

    -- dequeue → risk start (consumer validation + guard setup)
    CASE WHEN risk_started_at IS NOT NULL AND dequeued_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (risk_started_at - dequeued_at)) * 1000
    END AS pre_risk_ms,

    -- risk evaluation duration (MAS Council)
    CASE WHEN risk_finished_at IS NOT NULL AND risk_started_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (risk_finished_at - risk_started_at)) * 1000
    END AS risk_ms,

    -- execution duration (broker submit)
    CASE WHEN exec_submitted_at IS NOT NULL AND exec_started_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (exec_submitted_at - exec_started_at)) * 1000
    END AS exec_ms,

    -- total end-to-end (received → submitted / error)
    CASE WHEN exec_submitted_at IS NOT NULL AND received_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (exec_submitted_at - received_at)) * 1000
         WHEN error_at IS NOT NULL AND received_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (error_at - received_at)) * 1000
    END AS total_ms,

    created_at,
    updated_at
FROM public.pipeline_traces;
