-- Kill switch audit trail
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS kill_switch_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action      text NOT NULL CHECK (action IN ('engage', 'reset')),
    reason      text,
    toggled_by  text DEFAULT 'api',
    created_at  timestamptz DEFAULT now()
);

ALTER TABLE kill_switch_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for service role" ON kill_switch_log
    FOR ALL USING (true);
