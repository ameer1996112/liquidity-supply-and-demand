-- Add the JSONB column to store AI session logs with a default empty array
ALTER TABLE project_tickets 
ADD COLUMN ai_session_log JSONB DEFAULT '[]'::jsonb NOT NULL;
