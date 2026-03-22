---
created: 2026-03-22T07:55:16.453Z
title: Implement Discord thread per-trade fill and close notifications
area: api
files:
  - migrations/049_discord_thread_columns.sql
  - src/adapters/discord.py
  - src/worker.py
---

## Problem

Migration `049_discord_thread_columns.sql` adds `discord_message_id`, `discord_thread_id`, and `telegram_message_id` columns to `trading_signals`. These columns exist in the DB but are never written to — the worker doesn't yet create a Discord thread per trade, post fill confirmations as replies inside that thread, or post close summaries as thread replies.

Currently all Discord notifications are one-off top-level webhook posts via `send_discord` / `send_discord_async` in `src/adapters/discord.py`. There is no threading, so fill updates and close summaries are disconnected messages with no link back to the original signal card.

## Solution

1. Run migration `049_discord_thread_columns.sql` on production Supabase.
2. In `send_discord` (or a new `send_discord_trade_thread`), create a Discord thread on the initial signal card message using the Discord `startThread` endpoint.  Store the returned `thread_id` and `message_id` back to `trading_signals` (`discord_thread_id`, `discord_message_id`).
3. On fill confirmation (when `broker_order_id` is set), post a reply inside the thread using the stored `discord_thread_id`.
4. On close/exit (watchdog or webhook), post a final PnL summary as a reply inside the same thread.
5. Add `send_discord_thread_reply(thread_id, message)` helper to `discord.py`.
6. Guard all thread operations behind `discord_thread_id IS NOT NULL` checks to remain backward-compatible with signals that predate this feature.
