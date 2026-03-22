-- Migration 050: Alerts system upgrade
-- Adds: snoozed_until, error severity, cooldown_minutes on rules

-- 1. Allow 'error' severity (previously only critical/warning/info)
ALTER TABLE trading_alerts
  DROP CONSTRAINT IF EXISTS trading_alerts_severity_check;

ALTER TABLE trading_alerts
  ADD CONSTRAINT trading_alerts_severity_check
  CHECK (severity IN ('critical', 'error', 'warning', 'info'));

-- 2. Snooze support: suppress alerts until a given timestamp
ALTER TABLE trading_alerts
  ADD COLUMN IF NOT EXISTS snoozed_until timestamptz;

CREATE INDEX IF NOT EXISTS idx_alerts_snoozed
  ON trading_alerts(snoozed_until)
  WHERE snoozed_until IS NOT NULL;

-- 3. Per-rule cooldown: how many minutes to suppress repeated fires (default 60)
ALTER TABLE alert_rules
  ADD COLUMN IF NOT EXISTS cooldown_minutes integer NOT NULL DEFAULT 60;

-- Update existing rules to sensible cooldown defaults
UPDATE alert_rules SET cooldown_minutes = 60  WHERE rule_type IN ('consecutive_losses', 'drawdown_pct');
UPDATE alert_rules SET cooldown_minutes = 120 WHERE rule_type = 'position_age_hours';
UPDATE alert_rules SET cooldown_minutes = 30  WHERE rule_type = 'dlq_count';
