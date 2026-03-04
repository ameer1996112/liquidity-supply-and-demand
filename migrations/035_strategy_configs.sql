-- 035_strategy_configs.sql
-- Sprint 4.4: Strategy-as-data configuration
--
-- Strategy configuration stored as JSONB with versioning.
-- Linked snapshots for AI decisions (ai_runs) and backtests.

CREATE TABLE IF NOT EXISTS public.strategy_configs (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL UNIQUE,
    description TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT FALSE,
    version     INTEGER     NOT NULL DEFAULT 1,
    config      JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_configs_active
    ON public.strategy_configs (is_active)
    WHERE is_active = TRUE;

COMMENT ON TABLE public.strategy_configs IS
    'Sprint 4.4: Strategy-as-data configs (signal filters, risk presets, AI/debate, execution routing).';

-- Link strategy snapshots to AI debate runs
ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS strategy_id BIGINT REFERENCES public.strategy_configs(id) ON DELETE SET NULL;

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS strategy_version INTEGER;

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS strategy_config_snapshot JSONB;

-- Link strategy snapshots to backtests
ALTER TABLE public.backtests
    ADD COLUMN IF NOT EXISTS strategy_id BIGINT REFERENCES public.strategy_configs(id) ON DELETE SET NULL;

ALTER TABLE public.backtests
    ADD COLUMN IF NOT EXISTS strategy_version INTEGER;

