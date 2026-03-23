-- Migration 057: Project Tickets (Jira-style ticket tracker)
-- Creates the project_tickets table for task/bug/feature tracking
-- with AI changelog support and optional link to trading_signals.

-- ── Table ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS project_tickets (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT        NOT NULL,
    description  TEXT,
    type         TEXT        NOT NULL DEFAULT 'task'
                             CHECK (type IN ('bug', 'feature', 'task')),
    status       TEXT        NOT NULL DEFAULT 'todo'
                             CHECK (status IN ('todo', 'in_progress', 'done', 'archived')),
    priority     TEXT        NOT NULL DEFAULT 'medium'
                             CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    assignee     TEXT,
    signal_id    INTEGER     REFERENCES trading_signals(id) ON DELETE SET NULL,
    ai_changelog JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure signal_id column exists (handles tables created before this column was added)
ALTER TABLE project_tickets ADD COLUMN IF NOT EXISTS signal_id INTEGER;

-- ── updated_at trigger ───────────────────────────────────────────────────────

-- Only create function if it doesn't already exist (other migrations may have added it)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS project_tickets_updated_at ON project_tickets;
CREATE TRIGGER project_tickets_updated_at
    BEFORE UPDATE ON project_tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_project_tickets_status   ON project_tickets(status);
CREATE INDEX IF NOT EXISTS idx_project_tickets_type     ON project_tickets(type);
CREATE INDEX IF NOT EXISTS idx_project_tickets_priority ON project_tickets(priority);
CREATE INDEX IF NOT EXISTS idx_project_tickets_signal   ON project_tickets(signal_id);
CREATE INDEX IF NOT EXISTS idx_project_tickets_created  ON project_tickets(created_at DESC);

-- ── Row Level Security (optional, disable for service-role access) ────────────

ALTER TABLE project_tickets ENABLE ROW LEVEL SECURITY;

-- Allow full access via service role (backend uses service role key)
CREATE POLICY "service_role_full_access" ON project_tickets
    FOR ALL
    USING (true)
    WITH CHECK (true);
