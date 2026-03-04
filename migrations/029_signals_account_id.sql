-- 029_signals_account_id.sql
-- Sprint 2.3: wire account routing into trading_signals rows.
--
-- Adds an account_id column that mirrors the accounts.account_id PK value.
-- The worker now stamps payload["_account_id"] onto every saved signal,
-- enabling per-account filtering of positions, analytics, and traces.
--
-- Backward-compatibility guarantee:
--   • Default is 'default' — all pre-existing rows get the same value the
--     default-account path would have written, so single-account deployments
--     see zero query-result change when no account_id filter is applied.
--   • Existing code that never passes account_id continues to work: the
--     column is nullable-safe and all API filters are optional.

ALTER TABLE public.trading_signals
    ADD COLUMN IF NOT EXISTS account_id VARCHAR(128) NOT NULL DEFAULT 'default';

-- Backfill: prefer the value stored in account_name when it looks like a
-- structured account_id (non-null, non-empty, not a human display name).
-- Safe to re-run; ON CONFLICT / WHERE guard prevents double-application.
UPDATE public.trading_signals
SET    account_id = account_name
WHERE  account_name IS NOT NULL
  AND  account_name <> ''
  AND  account_id = 'default';

-- Index for per-account API queries (traces, positions, analytics).
CREATE INDEX IF NOT EXISTS idx_trading_signals_account_id
    ON public.trading_signals (account_id);

-- Composite index: most common query pattern — filter by account + status.
CREATE INDEX IF NOT EXISTS idx_trading_signals_account_status
    ON public.trading_signals (account_id, status);
