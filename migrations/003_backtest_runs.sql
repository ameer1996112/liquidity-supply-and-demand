-- Backtest run metadata
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS backtest_runs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          text UNIQUE NOT NULL,
    name            text,
    config          jsonb NOT NULL DEFAULT '{}',
    status          text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    signal_count    int DEFAULT 0,
    result_summary  jsonb DEFAULT '{}',
    started_at      timestamptz,
    completed_at    timestamptz,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_run_id ON backtest_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_status ON backtest_runs(status);

ALTER TABLE backtest_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all for service role" ON backtest_runs;
CREATE POLICY "Allow all for service role" ON backtest_runs
    FOR ALL USING (true);
