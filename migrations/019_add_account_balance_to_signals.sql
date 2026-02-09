-- Migration: Add account_balance column to trading_signals table
-- Purpose: Store the dynamic account balance from Pine script webhook
-- This allows tracking account size per signal and displaying it in dashboard

-- Add account_balance column to trading_signals
ALTER TABLE trading_signals
ADD COLUMN IF NOT EXISTS account_balance REAL DEFAULT 50000;

-- Add index for better query performance when filtering by account_balance
CREATE INDEX IF NOT EXISTS idx_trading_signals_account_balance
ON trading_signals(account_balance);

-- Update comment
COMMENT ON COLUMN trading_signals.account_balance IS
'Account balance used for this signal (from Pine webhook or .env fallback)';
