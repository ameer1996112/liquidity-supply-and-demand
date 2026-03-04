-- 031_ai_mode_graduation.sql
-- Sprint 3.4: Strategy graduation pipeline — audit log + runtime state.

-- Audit log: every AI mode toggle (shadow ↔ enforce)
CREATE TABLE IF NOT EXISTS public.ai_mode_toggles (
    id          BIGSERIAL PRIMARY KEY,
    from_mode   VARCHAR(16) NOT NULL,   -- shadow | enforce
    to_mode     VARCHAR(16) NOT NULL,
    reason      TEXT,                   -- optional: "graduation_ready" | "manual" | etc.
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  VARCHAR(128)            -- optional: user/session id
);

CREATE INDEX IF NOT EXISTS idx_ai_mode_toggles_created_at ON public.ai_mode_toggles (created_at DESC);

COMMENT ON TABLE public.ai_mode_toggles IS 'Sprint 3.4: Full audit log of AI mode toggles (shadow ↔ enforce).';

-- Runtime override: current ai_mode (overrides env when set)
-- Single row: id=1. Upsert on toggle.
CREATE TABLE IF NOT EXISTS public.ai_mode_state (
    id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    mode        VARCHAR(16) NOT NULL CHECK (mode IN ('shadow', 'enforce')),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.ai_mode_state (id, mode) VALUES (1, 'shadow')
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE public.ai_mode_state IS 'Sprint 3.4: Runtime AI mode override. NULL/empty = use env.';
