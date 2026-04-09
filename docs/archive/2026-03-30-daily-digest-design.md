# Automated Daily Performance Digest - System Design

## Overview
An automated service that aggregates daily trading performance and pushes a formatted performance digest (PnL, Win Rate, etc.) to the notification channels (Discord/Telegram) at the end of every trading session.

## Architecture & Scheduling
* **Trigger:** A background scheduler (e.g., `APScheduler`) running within `src/worker.py` or `src/api.py`.
* **Timing:** Configurable via `.env` variable `DIGEST_TIME_UTC` (default `"21:00"`). Will run exactly once per day.

## Data Flow & Aggregation
* **Database Query:** The system queries the `trading_signals` table in Supabase for all entries where `status = 'closed'` and the exit timestamp falls within the rolling 24-hour reporting horizon.
* **Math & Grouping:** The aggregation logic groups trades by `account_name`.
  * For each account, it calculates:
    1. **Net PnL:** Sum of gross PnL + Commission + Swap.
    2. **Win Rate:** Number of winning trades divided by total trades.
    3. **Best/Worst Trades:** The highest positive PnL and the lowest negative PnL.

## Components
1. **`src/services/digest_service.py`:**
   * Contains the core logic for fetching closed trades and executing mathematical aggregations per account.
2. **`NotificationService` Updates (`src/services/notification_service.py`):**
   * A new method `format_digest(report_data)` that constructs the custom `NotificationPayload` intended for daily digests.
3. **Dispatch Flow:**
   * Utilizes the existing `dispatch_payload_async` adapter to send messages uniformly mapped to Discord Embeds and Telegram text blocks.

## Error Handling & Edge Cases
* **Zero Trades (Quiet Days):** If 0 trades were executed for a given reporting period (e.g., weekends or slow market days), the digest service will exit gracefully and **remain silent**, producing no notification to avoid spam.
* **Aggregation Failures:** Encased in try-except block; issues will log locally but will not disrupt regular incoming tick/webhook processing in the main worker threads.
