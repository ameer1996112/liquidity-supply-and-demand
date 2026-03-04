-- 030_ai_runs.sql
-- Sprint 3.3: Debate guardrail (Bull vs Bear) — ai_run records for transcript + votes.
-- Linked to signal_id (when available) and correlation_id for trace association.

CREATE TABLE IF NOT EXISTS public.ai_runs (
    id              BIGSERIAL PRIMARY KEY,
    correlation_id  VARCHAR(64) NOT NULL,
    signal_id       BIGINT      REFERENCES public.trading_signals(id) ON DELETE SET NULL,
    trace_id        UUID,
    run_type        VARCHAR(32)  NOT NULL DEFAULT 'debate',

    -- Structured output (Sprint 3.3)
    recommendation  VARCHAR(16)  NOT NULL,  -- allow | block
    confidence      SMALLINT    NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    reason_codes     JSONB       DEFAULT '[]',
    memo            TEXT,

    -- Votes per agent: {"bull": "allow", "bear": "block", "risk": "allow", "chair": "allow"}
    votes           JSONB       NOT NULL DEFAULT '{}',

    -- Transcript stored as JSON array of {role, content}
    transcript      JSONB       NOT NULL DEFAULT '[]',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_runs_correlation_id ON public.ai_runs (correlation_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_signal_id ON public.ai_runs (signal_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_created_at ON public.ai_runs (created_at DESC);

COMMENT ON TABLE public.ai_runs IS 'Sprint 3.3: Debate guardrail runs (Bull/Bear/Risk/Chair). Shadow mode: log-only, never blocks.';
