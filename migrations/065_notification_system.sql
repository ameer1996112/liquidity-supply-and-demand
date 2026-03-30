-- Migration 065: Notification system upgrade
-- Adds: command_audit_log, notification_routing, notification_whitelist

-- Command audit log: tracks every two-way command issued via Discord/Telegram
CREATE TABLE IF NOT EXISTS command_audit_log (
    id              bigserial PRIMARY KEY,
    platform        text NOT NULL CHECK (platform IN ('telegram', 'discord')),
    user_id         text NOT NULL,
    command         text NOT NULL,
    args            text,
    signal_id       bigint REFERENCES trading_signals(id) ON DELETE SET NULL,
    alert_id        bigint REFERENCES trading_alerts(id) ON DELETE SET NULL,
    result          text,
    success         boolean DEFAULT true,
    executed_at     timestamptz DEFAULT now()
);

CREATE INDEX idx_command_audit_log_executed_at ON command_audit_log (executed_at DESC);
CREATE INDEX idx_command_audit_log_platform_user ON command_audit_log (platform, user_id);

-- Notification whitelist: users allowed to issue commands
CREATE TABLE IF NOT EXISTS notification_whitelist (
    id          bigserial PRIMARY KEY,
    platform    text NOT NULL CHECK (platform IN ('telegram', 'discord')),
    user_id     text NOT NULL,
    label       text,   -- friendly name e.g. "Ameer - Telegram"
    created_at  timestamptz DEFAULT now(),
    UNIQUE (platform, user_id)
);

-- Notification routing: which alert types go to which channels
CREATE TABLE IF NOT EXISTS notification_routing (
    id              bigserial PRIMARY KEY,
    alert_type      text NOT NULL,  -- 'signal', 'close', 'alert', 'guard', 'bug'
    discord_enabled boolean DEFAULT true,
    telegram_enabled boolean DEFAULT true,
    discord_channel text DEFAULT 'signals',  -- 'signals' | 'alerts'
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (alert_type)
);

-- Seed default routing rules
INSERT INTO notification_routing (alert_type, discord_enabled, telegram_enabled, discord_channel)
VALUES
    ('signal',  true,  true,  'signals'),
    ('close',   true,  true,  'signals'),
    ('alert',   true,  true,  'alerts'),
    ('guard',   true,  false, 'alerts'),
    ('bug',     true,  false, 'alerts')
ON CONFLICT (alert_type) DO NOTHING;
