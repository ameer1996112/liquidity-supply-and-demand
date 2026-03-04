-- 033_ai_decision_cache.sql
-- Sprint 4.1: AI decision cache for backtest reruns.

CREATE TABLE IF NOT EXISTS public.ai_decision_cache (
    id              BIGSERIAL PRIMARY KEY,
    cache_key       VARCHAR(64) NOT NULL UNIQUE,
    decision_json   JSONB NOT NULL,
    transcript_hash VARCHAR(64),
    token_estimate  INT DEFAULT 0,
    cost_estimate   REAL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_decision_cache_key ON public.ai_decision_cache (cache_key);

COMMENT ON TABLE public.ai_decision_cache IS 'Sprint 4.1: Cached AI decisions for backtest (strategy_version + prompt_version + model + signal_hash + candle_context_hash).';
