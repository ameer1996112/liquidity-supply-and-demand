-- 037_signal_actions.sql
-- Sprint 6.2: Advanced TradingView strategy vocabulary mapping
--
-- Extend trading_signals schema to capture high-level action and
-- execution hints coming from TradingView alerts. All columns are
-- added with IF NOT EXISTS so the migration is idempotent.

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS signal_action TEXT,
  ADD COLUMN IF NOT EXISTS order_type TEXT,
  ADD COLUMN IF NOT EXISTS trailing_stop JSONB,
  ADD COLUMN IF NOT EXISTS multi_tp JSONB,
  ADD COLUMN IF NOT EXISTS partial_close_percent REAL;

COMMENT ON COLUMN public.trading_signals.signal_action IS
  'Normalized action from webhook: entry|exit|close_all|modify|cancel (optional).';

COMMENT ON COLUMN public.trading_signals.order_type IS
  'Order type hint from webhook: market|limit|stop (optional).';

COMMENT ON COLUMN public.trading_signals.trailing_stop IS
  'Trailing stop configuration payload (JSON: distance, activation rules, etc.).';

COMMENT ON COLUMN public.trading_signals.multi_tp IS
  'Array of additional take profit levels from strategy (JSON array of prices).';

COMMENT ON COLUMN public.trading_signals.partial_close_percent IS
  'Optional partial close percentage requested by strategy (0–100).';

