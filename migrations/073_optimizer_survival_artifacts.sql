CREATE TABLE IF NOT EXISTS public.optimizer_run_trials (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    trial_number INTEGER NOT NULL,
    "window" VARCHAR(24) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_run_stress_tests (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    stress_type VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.optimizer_portfolio_results (
    run_id UUID PRIMARY KEY REFERENCES public.optimizer_runs(id) ON DELETE CASCADE,
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.news_events (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    currency VARCHAR(8) NOT NULL,
    country TEXT,
    importance INTEGER NOT NULL,
    title TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS public.spread_profiles (
    id BIGSERIAL PRIMARY KEY,
    broker TEXT NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    baseline_spread NUMERIC(12, 6) NOT NULL,
    stress_125 NUMERIC(12, 6) NOT NULL,
    stress_150 NUMERIC(12, 6) NOT NULL,
    slippage_per_side NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broker, symbol)
);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_optimizer_portfolio_results_updated_at ON public.optimizer_portfolio_results;
CREATE TRIGGER trg_optimizer_portfolio_results_updated_at
BEFORE UPDATE ON public.optimizer_portfolio_results
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_spread_profiles_updated_at ON public.spread_profiles;
CREATE TRIGGER trg_spread_profiles_updated_at
BEFORE UPDATE ON public.spread_profiles
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();
