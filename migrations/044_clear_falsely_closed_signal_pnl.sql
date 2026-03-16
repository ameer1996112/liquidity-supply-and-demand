-- Migration 044: Clear PnL from signals that were falsely marked CLOSED
--
-- Before the fix in logic.py, the exit handler changed the status of rejected
-- signals (staleness_rejected, filtered, etc.) to CLOSED and wrote TradingView's
-- simulated PnL. These records have no broker_order_id because the entry was
-- never executed. This migration clears the fake PnL and reverts their status.

UPDATE trading_signals
SET
    pnl_usd  = NULL,
    pnl      = NULL,
    outcome  = NULL,
    status   = 'unexecuted',
    notes    = CONCAT(
                 'PnL cleared by migration 044: marked CLOSED by exit webhook '
                 'but no broker execution (broker_order_id is null). ',
                 COALESCE(notes, '')
               )
WHERE
    status = 'CLOSED'
    AND broker_order_id IS NULL
    AND (pnl_usd IS NOT NULL OR pnl IS NOT NULL);
