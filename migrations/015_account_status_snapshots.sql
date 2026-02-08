-- Migration 015: Account Status Snapshots
-- Time-series data for account balance, equity, margin from MetaAPI

CREATE TABLE IF NOT EXISTS public.account_status_snapshots (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name        VARCHAR(100) NOT NULL,
    broker_profile_id   bigint REFERENCES public.broker_profiles(id) ON DELETE CASCADE,

    -- Account metrics from MetaAPI
    balance             REAL NOT NULL,
    equity              REAL NOT NULL,
    margin              REAL DEFAULT 0,
    free_margin         REAL DEFAULT 0,
    margin_level_pct    REAL DEFAULT 0,

    -- Additional broker info
    credit              REAL DEFAULT 0,
    leverage            INTEGER,

    -- Connection metadata
    server_name         VARCHAR(100),
    platform_type       VARCHAR(20), -- MT4, MT5
    connection_status   VARCHAR(20) DEFAULT 'connected',
                        -- connected, disconnected, error
    sync_latency_ms     INTEGER,
    error_message       TEXT,

    -- Timestamp
    snapshot_time       TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate snapshots for same account at same time
    CONSTRAINT unique_account_snapshot UNIQUE(account_name, snapshot_time)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_account_snapshots_account_time
  ON public.account_status_snapshots(account_name, snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_account_snapshots_time
  ON public.account_status_snapshots(snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_account_snapshots_broker_profile
  ON public.account_status_snapshots(broker_profile_id);

-- Partition by month (optional, for large datasets)
-- Could add later if snapshot volume grows large

-- Comments
COMMENT ON TABLE public.account_status_snapshots IS
  'Time-series snapshots of account balance, equity, margin from MetaAPI. Used for equity curves and balance tracking.';

COMMENT ON COLUMN public.account_status_snapshots.balance IS
  'Account balance from broker (deposits + withdrawals + closed P&L)';

COMMENT ON COLUMN public.account_status_snapshots.equity IS
  'Account equity from broker (balance + open P&L)';

COMMENT ON COLUMN public.account_status_snapshots.margin IS
  'Margin used by open positions';

COMMENT ON COLUMN public.account_status_snapshots.free_margin IS
  'Available margin for new positions (equity - margin)';

COMMENT ON COLUMN public.account_status_snapshots.margin_level_pct IS
  'Margin level percentage (equity / margin * 100). <100% = margin call risk.';

COMMENT ON COLUMN public.account_status_snapshots.sync_latency_ms IS
  'Time taken to fetch data from MetaAPI (in milliseconds)';

-- Verification query
SELECT
    'account_status_snapshots' AS table_name,
    COUNT(*) AS row_count
FROM public.account_status_snapshots;
