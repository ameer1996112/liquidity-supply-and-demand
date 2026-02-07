-- Migration: guard_decisions table for analytics (Package C)
-- Optional. log_guard_decision() writes here when table exists; also writes to trade_events.

CREATE TABLE IF NOT EXISTS public.guard_decisions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guard_name  text NOT NULL,
    result      text NOT NULL,
    reason      text NOT NULL DEFAULT '',
    symbol      text DEFAULT '',
    metadata    jsonb DEFAULT '{}',
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_guard_decisions_guard ON public.guard_decisions(guard_name);
CREATE INDEX IF NOT EXISTS idx_guard_decisions_created ON public.guard_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guard_decisions_symbol ON public.guard_decisions(symbol) WHERE symbol <> '';

COMMENT ON TABLE public.guard_decisions IS 'Audit log of guard/AI decisions for analytics and tuning (Package C).';
