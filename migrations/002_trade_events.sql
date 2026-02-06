-- Execution audit trail
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS trade_events (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id   bigint,
    event_type  text NOT NULL,
    stage       text,
    metadata    jsonb DEFAULT '{}',
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX idx_trade_events_signal_id ON trade_events(signal_id);
CREATE INDEX idx_trade_events_event_type ON trade_events(event_type);
CREATE INDEX idx_trade_events_created_at ON trade_events(created_at DESC);

ALTER TABLE trade_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for service role" ON trade_events
    FOR ALL USING (true);
