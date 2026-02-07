-- Rollback: multi-account columns and indexes (Package A)
DROP INDEX IF EXISTS public.idx_unique_trade_key_profile;
DROP INDEX IF EXISTS public.idx_unique_trade_key_single;
ALTER TABLE public.trading_signals DROP COLUMN IF EXISTS broker_profile_id;

-- Restore original single-key unique index (same as 001)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade_key_trade_rows
  ON public.trading_signals (trade_key)
  WHERE (trade_key IS NOT NULL AND trim(trade_key) <> '')
    AND status IN ('pending', 'active', 'closed', 'execution_failed');
