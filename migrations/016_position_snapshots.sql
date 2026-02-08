-- Migration 016: Position Snapshots
-- Cache of open positions from MetaAPI for reconciliation and history

CREATE TABLE IF NOT EXISTS public.position_snapshots (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name            VARCHAR(100) NOT NULL,
    broker_profile_id       bigint REFERENCES public.broker_profiles(id) ON DELETE CASCADE,
    broker_position_id      VARCHAR(50) NOT NULL, -- MetaAPI position.id

    -- Position details from MetaAPI
    symbol                  VARCHAR(20) NOT NULL,
    side                    VARCHAR(10) NOT NULL, -- buy, sell
    volume                  REAL NOT NULL,
    open_price              REAL NOT NULL,
    current_price           REAL,
    sl                      REAL,
    tp                      REAL,
    profit                  REAL,
    swap                    REAL DEFAULT 0,
    commission              REAL DEFAULT 0,
    magic_number            INTEGER,
    comment                 TEXT,

    -- Timestamps
    open_time               TIMESTAMPTZ,
    update_time             TIMESTAMPTZ,

    -- Reconciliation with trading_signals table
    matched_signal_id       bigint REFERENCES public.trading_signals(id) ON DELETE SET NULL,
    reconciliation_status   VARCHAR(20) DEFAULT 'pending',
                            -- pending, matched, orphaned (broker only), ghost (DB only)
    reconciliation_note     TEXT,

    -- Snapshot metadata
    snapshot_time           TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate snapshots
    CONSTRAINT unique_position_snapshot UNIQUE(account_name, broker_position_id, snapshot_time)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_position_snapshots_account_time
  ON public.position_snapshots(account_name, snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_position_snapshots_broker_position
  ON public.position_snapshots(broker_position_id);

CREATE INDEX IF NOT EXISTS idx_position_snapshots_signal
  ON public.position_snapshots(matched_signal_id) WHERE matched_signal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_position_snapshots_reconciliation
  ON public.position_snapshots(reconciliation_status)
  WHERE reconciliation_status IN ('orphaned', 'pending');

CREATE INDEX IF NOT EXISTS idx_position_snapshots_symbol
  ON public.position_snapshots(symbol);

-- Comments
COMMENT ON TABLE public.position_snapshots IS
  'Cached snapshots of open positions from MetaAPI. Used for position reconciliation (broker vs DB) and historical tracking.';

COMMENT ON COLUMN public.position_snapshots.broker_position_id IS
  'MetaAPI position ID (unique identifier from broker)';

COMMENT ON COLUMN public.position_snapshots.matched_signal_id IS
  'FK to trading_signals.id if position was matched during reconciliation';

COMMENT ON COLUMN public.position_snapshots.reconciliation_status IS
  'pending: not yet reconciled, matched: found in DB, orphaned: broker only (not in DB), ghost: DB only (not in broker)';

COMMENT ON COLUMN public.position_snapshots.magic_number IS
  'MT4/MT5 magic number (optional EA identifier)';

-- Verification query
SELECT
    'position_snapshots' AS table_name,
    COUNT(*) AS row_count
FROM public.position_snapshots;
