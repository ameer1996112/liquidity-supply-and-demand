-- Migration 034: Trade Reflections (Sprint 4.3)
-- Post-mortem records for closed trades with pgvector embeddings for similarity retrieval.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.trade_reflections (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trade_id            bigint NOT NULL REFERENCES public.trading_signals(id) ON DELETE CASCADE,
    outcome             VARCHAR(20) NOT NULL,  -- win, loss, breakeven
    r_multiple          NUMERIC(10, 4),        -- R-multiple (pnl in R units)
    max_adverse_excursion NUMERIC(20, 6),      -- MAE in price units (nullable)
    reasons             TEXT,                  -- Why it won/lost
    what_to_improve     TEXT,                  -- Lessons / improvements
    content             TEXT NOT NULL,         -- Full text for embedding
    embedding           vector(1536),          -- OpenAI text-embedding-3-small
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_reflection_per_trade UNIQUE (trade_id)
);

CREATE INDEX IF NOT EXISTS idx_trade_reflections_trade_id
    ON public.trade_reflections(trade_id);

CREATE INDEX IF NOT EXISTS idx_trade_reflections_outcome
    ON public.trade_reflections(outcome);

CREATE INDEX IF NOT EXISTS idx_trade_reflections_created
    ON public.trade_reflections(created_at DESC);

-- HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_trade_reflections_embedding
    ON public.trade_reflections USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

COMMENT ON TABLE public.trade_reflections IS
    'Sprint 4.3: Trade post-mortem records with embeddings for memory-augmented AI context.';

-- RPC for similarity search (cosine distance)
CREATE OR REPLACE FUNCTION public.match_trade_reflections(
    query_embedding vector(1536),
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id bigint,
    trade_id bigint,
    outcome text,
    r_multiple numeric,
    reasons text,
    what_to_improve text,
    content text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        tr.id,
        tr.trade_id,
        tr.outcome::text,
        tr.r_multiple,
        tr.reasons,
        tr.what_to_improve,
        tr.content,
        1 - (tr.embedding <=> query_embedding) AS similarity
    FROM public.trade_reflections tr
    WHERE tr.embedding IS NOT NULL
    ORDER BY tr.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
