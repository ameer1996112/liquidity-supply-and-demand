-- Migration 069: Enforce atomic idempotency on trading_signals
--
-- Adds a unique constraint on (trade_key, broker_profile_id) so that concurrent
-- worker instances cannot insert duplicate rows for the same trade signal.
-- The Redis SETNX lock in worker._claim_trade_key() is the first line of defence;
-- this constraint is the hard DB-level safety net.
--
-- NULL broker_profile_id is treated as a distinct value per SQL standard, so
-- two rows with the same trade_key and NULL broker_profile_id would both pass
-- the constraint.  We use a partial unique index to cover that case separately.

-- Constraint for rows with a non-NULL broker_profile_id
ALTER TABLE trading_signals
    ADD CONSTRAINT uq_trade_key_broker_profile
    UNIQUE (trade_key, broker_profile_id);

-- Partial unique index for rows where broker_profile_id IS NULL
CREATE UNIQUE INDEX IF NOT EXISTS uq_trade_key_no_broker
    ON trading_signals (trade_key)
    WHERE broker_profile_id IS NULL;
