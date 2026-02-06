-- Update alert rules to filter by LIVE run_mode only
-- This prevents PAPER trades from triggering production alerts

-- Update consecutive_losses rule to only check LIVE trades
UPDATE alert_rules
SET condition = '{"threshold": 3, "run_mode": "LIVE"}'
WHERE rule_type = 'consecutive_losses';

-- Update drawdown_pct rule to only check LIVE trades
UPDATE alert_rules
SET condition = '{"threshold": 6, "run_mode": "LIVE"}'
WHERE rule_type = 'drawdown_pct';

-- Add comment explaining the run_mode filter
COMMENT ON COLUMN alert_rules.condition IS 'JSON condition with threshold and optional run_mode filter (LIVE/PAPER)';
