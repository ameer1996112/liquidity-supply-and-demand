-- Migration 049: Add Discord thread tracking columns to trading_signals
-- These columns let the bot post fill confirmations and close summaries
-- as replies inside a per-trade Discord thread.

ALTER TABLE trading_signals
  ADD COLUMN IF NOT EXISTS discord_message_id  TEXT,
  ADD COLUMN IF NOT EXISTS discord_thread_id   TEXT,
  ADD COLUMN IF NOT EXISTS telegram_message_id BIGINT;
