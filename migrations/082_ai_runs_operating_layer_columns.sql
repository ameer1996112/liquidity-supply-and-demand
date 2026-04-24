-- 082_ai_runs_operating_layer_columns.sql
-- Persist AI operating-layer context alongside council debate runs.

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS analysis_mode VARCHAR(32) NOT NULL DEFAULT 'shadow_pretrade';

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS chart_context JSONB NOT NULL DEFAULT '{}';

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS pine_context JSONB NOT NULL DEFAULT '{}';

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS module_status JSONB NOT NULL DEFAULT '{}';

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS layered_output JSONB NOT NULL DEFAULT '{}';

ALTER TABLE public.ai_runs
    ADD COLUMN IF NOT EXISTS council_report JSONB NOT NULL DEFAULT '{}';
