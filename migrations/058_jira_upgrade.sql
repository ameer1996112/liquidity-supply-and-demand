-- Migration 058: Jira upgrade — sprints, labels, comments, relations, epics
-- Run AFTER 057_project_tickets.sql

-- ── Sprints ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jira_sprints (
    id          SERIAL      PRIMARY KEY,
    name        TEXT        NOT NULL,
    goal        TEXT,
    start_date  DATE,
    end_date    DATE,
    status      TEXT        NOT NULL DEFAULT 'planned'
                            CHECK (status IN ('planned', 'active', 'completed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER jira_sprints_updated_at
    BEFORE UPDATE ON jira_sprints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Labels ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jira_labels (
    id    SERIAL PRIMARY KEY,
    name  TEXT   NOT NULL UNIQUE,
    color TEXT   NOT NULL DEFAULT '#6366f1'
);

-- Pre-seed common labels
INSERT INTO jira_labels (name, color) VALUES
    ('frontend',  '#3b82f6'),
    ('backend',   '#8b5cf6'),
    ('trading',   '#f59e0b'),
    ('infra',     '#10b981'),
    ('urgent',    '#ef4444'),
    ('ai',        '#a855f7')
ON CONFLICT (name) DO NOTHING;

-- ── Upgrade project_tickets ───────────────────────────────────────────────────

-- Sprint link
ALTER TABLE project_tickets
    ADD COLUMN IF NOT EXISTS sprint_id   INTEGER REFERENCES jira_sprints(id) ON DELETE SET NULL;

-- Labels (text array of label names)
ALTER TABLE project_tickets
    ADD COLUMN IF NOT EXISTS labels      TEXT[]  NOT NULL DEFAULT '{}';

-- Epic (self-referential parent)
ALTER TABLE project_tickets
    ADD COLUMN IF NOT EXISTS parent_id   UUID REFERENCES project_tickets(id) ON DELETE SET NULL;

-- Manual sort rank within a column
ALTER TABLE project_tickets
    ADD COLUMN IF NOT EXISTS rank        FLOAT8  NOT NULL DEFAULT 0;

-- Story points
ALTER TABLE project_tickets
    ADD COLUMN IF NOT EXISTS story_points INT2;

-- Review status for "in_progress" swim-lane
ALTER TABLE project_tickets
    DROP CONSTRAINT IF EXISTS project_tickets_status_check;
ALTER TABLE project_tickets
    ADD CONSTRAINT project_tickets_status_check
    CHECK (status IN ('todo', 'in_progress', 'review', 'done', 'archived'));

-- ── Comments ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jira_comments (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id   UUID        NOT NULL REFERENCES project_tickets(id) ON DELETE CASCADE,
    body_md    TEXT        NOT NULL,
    author     TEXT        NOT NULL DEFAULT 'user',
    is_ai      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER jira_comments_updated_at
    BEFORE UPDATE ON jira_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX IF NOT EXISTS idx_jira_comments_issue ON jira_comments(issue_id, created_at);

-- ── Relations ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jira_relations (
    id        SERIAL PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES project_tickets(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES project_tickets(id) ON DELETE CASCADE,
    type      TEXT NOT NULL CHECK (type IN ('blocks', 'relates', 'duplicates')),
    UNIQUE(source_id, target_id, type)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_project_tickets_sprint  ON project_tickets(sprint_id);
CREATE INDEX IF NOT EXISTS idx_project_tickets_parent  ON project_tickets(parent_id);
CREATE INDEX IF NOT EXISTS idx_project_tickets_rank    ON project_tickets(status, rank);

-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE jira_sprints  ENABLE ROW LEVEL SECURITY;
ALTER TABLE jira_labels   ENABLE ROW LEVEL SECURITY;
ALTER TABLE jira_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE jira_relations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access" ON jira_sprints  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_full_access" ON jira_labels   FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_full_access" ON jira_comments FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_full_access" ON jira_relations FOR ALL USING (true) WITH CHECK (true);
