-- Migration 060: Add rubric_score JSONB column to signals table
-- Phase 6: Four-Dimension Rubric Engine
-- Stores the rubric scoring result for each signal

ALTER TABLE signals ADD COLUMN IF NOT EXISTS rubric_score JSONB;

-- Index for querying signals by gate_status
CREATE INDEX IF NOT EXISTS idx_signals_rubric_gate
    ON signals ((rubric_score->>'gate_status'))
    WHERE rubric_score IS NOT NULL;

COMMENT ON COLUMN signals.rubric_score IS
    'Phase 6 rubric engine output: {composite, gate_status, vetoed_by, ev_score, dimensions}';
