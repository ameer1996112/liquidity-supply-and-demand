-- Migration 069: Enforce atomic idempotency on trading_signals
--
-- Adds partial unique indexes on (trade_key, broker_profile_id) so that
-- concurrent worker instances cannot insert duplicate rows for the same
-- trade signal.
--
-- Only applies to rows with a non-empty trade_key — empty string means
-- "no idempotency key assigned" and is excluded from the constraint.
--
-- Step 1: Remove duplicate rows (keep highest id per group) before indexing.
-- Step 2: Create partial unique indexes that skip empty trade_key values.

-- ── Step 1: Deduplicate existing rows ────────────────────────────────────────

-- Remove duplicates where broker_profile_id IS NOT NULL, keeping the row
-- with the highest id in each (trade_key, broker_profile_id) group.
DELETE FROM trading_signals
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY trade_key, broker_profile_id
                   ORDER BY id DESC
               ) AS rn
        FROM trading_signals
        WHERE trade_key IS NOT NULL
          AND trade_key <> ''
          AND broker_profile_id IS NOT NULL
    ) ranked
    WHERE rn > 1
);

-- Remove duplicates where broker_profile_id IS NULL, keeping highest id.
DELETE FROM trading_signals
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY trade_key
                   ORDER BY id DESC
               ) AS rn
        FROM trading_signals
        WHERE trade_key IS NOT NULL
          AND trade_key <> ''
          AND broker_profile_id IS NULL
    ) ranked
    WHERE rn > 1
);

-- ── Step 2: Create partial unique indexes ────────────────────────────────────

-- Unique index for rows with a real trade_key AND a broker_profile_id
CREATE UNIQUE INDEX IF NOT EXISTS uq_trade_key_broker_profile
    ON trading_signals (trade_key, broker_profile_id)
    WHERE trade_key IS NOT NULL
      AND trade_key <> ''
      AND broker_profile_id IS NOT NULL;

-- Unique index for rows with a real trade_key and no broker_profile_id
CREATE UNIQUE INDEX IF NOT EXISTS uq_trade_key_no_broker
    ON trading_signals (trade_key)
    WHERE trade_key IS NOT NULL
      AND trade_key <> ''
      AND broker_profile_id IS NULL;
