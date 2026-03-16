-- Migration 043: Clear corrupted PnL from rejected signals
--
-- Signals that were rejected by guard rails (staleness, AI, filters, etc.)
-- should never have PnL values. Before this fix was applied, exit webhooks
-- from TradingView would write simulated PnL to these records and mark them
-- CLOSED. This migration clears that data and adds a note explaining why.

UPDATE trading_signals
SET
    pnl_usd      = NULL,
    pnl          = NULL,
    outcome      = NULL,
    status       = status,   -- keep original rejected status (no change)
    notes        = CONCAT(
                     'PnL cleared by migration 043: entry was ',
                     status,
                     ' — trade was never executed on broker.'
                   )
WHERE
    status IN (
        'staleness_rejected',
        'filtered',
        'ai_rejected',
        'execution_failed',
        'rejected',
        'guard_rejected'
    )
    AND (pnl_usd IS NOT NULL OR pnl IS NOT NULL);
