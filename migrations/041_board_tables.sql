-- Migration 041: Create Kanban board tables
-- project_tickets: stores all board tickets (bugs, tasks, features, research)
-- ticket_agent_events: stores agent activity feed events

CREATE TABLE IF NOT EXISTS project_tickets (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id    text NOT NULL UNIQUE,          -- e.g. BUG-012, TASK-003
  type         text NOT NULL CHECK (type IN ('bug', 'task', 'feature', 'research')),
  title        text NOT NULL,
  description  text,
  component    text NOT NULL,
  priority     text NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
  status       text NOT NULL DEFAULT 'backlog'
               CHECK (status IN ('backlog', 'todo', 'in_progress', 'done')),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS ticket_agent_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   text NOT NULL,                  -- references project_tickets.ticket_id (loose FK)
  message     text NOT NULL,
  event_type  text NOT NULL CHECK (event_type IN ('update', 'move', 'create', 'close')),
  agent_name  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Index for fast board queries
CREATE INDEX IF NOT EXISTS idx_project_tickets_status      ON project_tickets (status);
CREATE INDEX IF NOT EXISTS idx_project_tickets_created_at  ON project_tickets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id     ON ticket_agent_events (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_events_created_at    ON ticket_agent_events (created_at DESC);

-- Enable Realtime on agent events so the board feed is live
ALTER TABLE ticket_agent_events REPLICA IDENTITY FULL;
