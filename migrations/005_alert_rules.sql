-- Alert Rules table: configurable rules evaluated by the alert engine
-- Used by: src/services/alert_engine.py, src/api_alerts.py

CREATE TABLE IF NOT EXISTS alert_rules (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_type   text NOT NULL,
    condition   jsonb NOT NULL DEFAULT '{}',
    severity    text NOT NULL DEFAULT 'warning' CHECK (severity IN ('critical', 'warning', 'info')),
    enabled     boolean NOT NULL DEFAULT true,
    created_at  timestamptz DEFAULT now()
);

-- Pre-seed default rules
INSERT INTO alert_rules (rule_type, condition, severity) VALUES
    ('consecutive_losses', '{"threshold": 3}', 'warning'),
    ('drawdown_pct', '{"threshold": 6}', 'critical'),
    ('dlq_count', '{"threshold": 1}', 'warning'),
    ('position_age_hours', '{"threshold": 24}', 'info');
