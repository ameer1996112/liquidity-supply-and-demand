# Protocol: TradingView to Trinity Bot Connection (BTC Paper Mode)

**Version:** 1.0
**Classification:** Configuration Artifact
**Environment:** Paper Trading (Non-Live)

---

## Overview

This document provides step-by-step instructions for connecting TradingView alerts to your Trinity Trading Bot deployed on Railway. By the end of this guide, you will have a working webhook pipeline that triggers paper trades on **BTCUSD**.

---

## Section 1: The Payload Artifact

### 1.1 Exact JSON Payload

Copy the following JSON **exactly** and paste it into TradingView's alert **Message** field:

```json
{
  "symbol": "BTCUSD",
  "side": "buy",
  "entry": {{close}},
  "sl": {{close}} * 0.99,
  "tp": {{close}} * 1.02,
  "size": 0.01,
  "run_mode": "PAPER",
  "signal": "F:score=95 | F:signal_encoded=95 | F:source=TV_BTC_TEST",
  "score": 95,
  "zone_id": {{timenow}},
  "trade_key": "BTCUSD_{{timenow}}"
}
```

> **IMPORTANT:** This payload uses TradingView placeholders (`{{close}}`, `{{timenow}}`) that auto-populate with real-time data when the alert fires.

---

### 1.2 Alternative: Static Test Payload (For Manual Testing)

If you need a fully static payload for curl/Postman testing:

```json
{
  "symbol": "BTCUSD",
  "side": "buy",
  "entry": 45000.0,
  "sl": 44550.0,
  "tp": 45900.0,
  "size": 0.01,
  "run_mode": "PAPER",
  "signal": "F:score=95 | F:signal_encoded=95 | F:source=TV_BTC_TEST",
  "score": 95,
  "zone_id": 1706745600000,
  "trade_key": "BTCUSD_MANUAL_TEST"
}
```

---

### 1.3 Field Reference Table

| Field      | Value               | Purpose                                    |
| ---------- | ------------------- | ------------------------------------------ |
| `symbol`   | `"BTCUSD"`          | Target instrument (Bitcoin vs USD)         |
| `side`     | `"buy"` or `"sell"` | Trade direction                            |
| `entry`    | `{{close}}`         | Current price at alert trigger             |
| `sl`       | `{{close}} * 0.99`  | Stop Loss: 1% below entry                  |
| `tp`       | `{{close}} * 1.02`  | Take Profit: 2% above entry                |
| `size`     | `0.01`              | Position size in lots (passes risk checks) |
| `run_mode` | `"PAPER"`           | Paper trading mode (no real execution)     |
| `signal`   | Hardcoded string    | Forces AI approval with score=95           |
| `score`    | `95`                | High confidence score for testing          |

---

## Section 2: Webhook URL Configuration

### 2.1 Your Webhook Endpoint

```
https://grand-learning-production-bc96.up.railway.app/webhook
```

### 2.2 Authentication Options

Your bot supports three authentication methods. Choose **one**:

#### Option A: Query Parameter (Recommended for TradingView)

Append `?secret=YOUR_SECRET` to the webhook URL:

```
https://grand-learning-production-bc96.up.railway.app/webhook?secret=YOUR_SECRET_FROM_ENV_FILE
```

> **WARNING:** Replace `YOUR_SECRET_FROM_ENV_FILE` with the actual value of `WEBHOOK_SECRET` from your Railway environment variables. **Do not commit this value to version control.**

#### Option B: No Authentication (Development Only)

If `WEBHOOK_SECRET` is not set in Railway, the endpoint accepts all requests:

```
https://grand-learning-production-bc96.up.railway.app/webhook
```

> **SECURITY WARNING:** Only use this in controlled testing environments.

---

## Section 3: TradingView Alert Setup (Step-by-Step)

### Step 3.1: Open the BTCUSD Chart

1. Navigate to [TradingView.com](https://www.tradingview.com)
2. Click the **Search** bar at the top center
3. Type `BTCUSD` and select your preferred exchange (e.g., `BTCUSD` on Coinbase, Bitstamp, or INDEX)
4. Press **Enter** to load the chart

---

### Step 3.2: Create a New Alert

1. Right-click anywhere on the chart
2. Select **"Add Alert..."** from the context menu

   **Alternative:** Press the keyboard shortcut `Alt + A` (Windows) or `Option + A` (Mac)

   **Alternative:** Click the **Clock** icon in the right sidebar, then click **"Create Alert"**

---

### Step 3.3: Configure Alert Condition

In the **"Create Alert"** dialog:

| Setting       | Configuration                                                     |
| ------------- | ----------------------------------------------------------------- |
| **Condition** | Select `BTCUSD` from the first dropdown                           |
| **Trigger**   | Select `Crossing`                                                 |
| **Value**     | Enter a price slightly above or below current price (for testing) |
| **Options**   | Check `"Once Per Bar Close"` for cleaner triggers                 |

**Example Test Setup:**

- If BTC is at $45,000, set the trigger to `Crossing Up` at `$45,050`
- This triggers when price crosses above $45,050

---

### Step 3.4: Configure Webhook Destination

1. Scroll down to the **"Notifications"** section
2. **Enable** the **"Webhook URL"** toggle (it will turn blue)
3. In the **Webhook URL** field, paste:

```
https://grand-learning-production-bc96.up.railway.app/webhook?secret=YOUR_SECRET_FROM_ENV_FILE
```

> **CRITICAL:** Replace `YOUR_SECRET_FROM_ENV_FILE` with your actual secret value.

---

### Step 3.5: Configure the Message Payload

1. Locate the **"Message"** text area
2. **Delete all default content** in the Message field
3. Paste the following JSON exactly:

```json
{
  "symbol": "BTCUSD",
  "side": "buy",
  "entry": {{close}},
  "sl": {{close}} * 0.99,
  "tp": {{close}} * 1.02,
  "size": 0.01,
  "run_mode": "PAPER",
  "signal": "F:score=95 | F:signal_encoded=95 | F:source=TV_BTC_TEST",
  "score": 95,
  "zone_id": {{timenow}},
  "trade_key": "BTCUSD_{{timenow}}"
}
```

---

### Step 3.6: Name and Save the Alert

1. In the **"Alert name"** field, enter: `Trinity BTC Paper Test`
2. Set **"Expiration"** to your desired duration (e.g., "Open-ended" or 24 hours)
3. Click the **"Create"** button

---

## Section 4: Verification Checklist

### 4.1 Expected Success Flow

When the alert triggers successfully:

```
TradingView Alert Fires
        │
        ▼
POST /webhook (Railway)
        │
        ▼
Payload Validated ✓
        │
        ▼
Job Queued to Redis
        │
        ▼
Worker Processes Job
        │
        ▼
Discord Notification Sent ✓
```

**Success Indicator:** You receive a Discord notification with trade details.

---

### 4.2 What to Check if No Discord Ping

| Issue                  | Diagnostic Action                                     |
| ---------------------- | ----------------------------------------------------- |
| **Alert didn't fire**  | Check TradingView's "Alerts" tab for status           |
| **Webhook rejected**   | Check Railway logs for HTTP 401/422 errors            |
| **Secret mismatch**    | Verify `WEBHOOK_SECRET` in Railway matches URL        |
| **Payload malformed**  | Validate JSON at [jsonlint.com](https://jsonlint.com) |
| **Worker not running** | Check Railway for active worker process               |
| **Risk check failed**  | Check Railway logs for "REJECT" messages              |

---

### 4.3 Checking Railway Logs

1. Navigate to your [Railway Dashboard](https://railway.app/dashboard)
2. Click on your project: **grand-learning-production**
3. Select the **Deployments** tab
4. Click on the latest deployment
5. Click **"View Logs"** or **"Runtime Logs"**

**Look for these log patterns:**

```
# Success
INFO:     POST /webhook 200 OK
INFO:     Job queued: BTCUSD_buy

# Authentication Failed
WARNING:  Invalid webhook secret
INFO:     POST /webhook 401 Unauthorized

# Validation Failed
ERROR:    Missing required field: symbol
INFO:     POST /webhook 422 Unprocessable Entity

# Risk Check Rejected
WARNING:  [RISK] Trade rejected: Daily loss limit exceeded
```

---

## Section 5: Quick Reference Card

### Webhook URL (With Auth)

```
https://grand-learning-production-bc96.up.railway.app/webhook?secret=YOUR_SECRET_FROM_ENV_FILE
```

### Test Payload (Copy-Paste Ready)

```json
{
  "symbol": "BTCUSD",
  "side": "buy",
  "entry": {{close}},
  "sl": {{close}} * 0.99,
  "tp": {{close}} * 1.02,
  "size": 0.01,
  "run_mode": "PAPER",
  "signal": "F:score=95 | F:signal_encoded=95 | F:source=TV_BTC_TEST",
  "score": 95,
  "zone_id": {{timenow}},
  "trade_key": "BTCUSD_{{timenow}}"
}
```

### Manual cURL Test

```bash
curl -X POST "https://grand-learning-production-bc96.up.railway.app/webhook?secret=YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "side": "buy",
    "entry": 45000.00,
    "sl": 44550.00,
    "tp": 45900.00,
    "size": 0.01,
    "run_mode": "PAPER",
    "signal": "F:score=95 | F:signal_encoded=95 | F:source=TV_BTC_TEST"
  }'
```

**Expected Response:**

```json
{ "status": "queued" }
```

---

## Section 6: Troubleshooting Matrix

| Symptom                         | Cause                  | Solution                                   |
| ------------------------------- | ---------------------- | ------------------------------------------ |
| `401 Unauthorized`              | Secret mismatch        | Check `WEBHOOK_SECRET` in Railway env vars |
| `422 Unprocessable Entity`      | Missing/invalid fields | Validate JSON structure matches template   |
| `400 Bad Request`               | Malformed JSON         | Check for syntax errors, missing commas    |
| No Discord ping but 200 OK      | Worker not processing  | Check Redis connection, restart worker     |
| Trade rejected by Risk Guardian | Daily limits exceeded  | Wait for daily reset or increase limits    |
| Trade rejected by Pine Guardian | Size variance >5%      | Adjust `size` field to match expected      |

---

## Appendix A: TradingView Placeholders Reference

| Placeholder    | Description         | Example Output         |
| -------------- | ------------------- | ---------------------- |
| `{{ticker}}`   | Symbol name         | `BTCUSD`               |
| `{{close}}`    | Current close price | `45123.45`             |
| `{{open}}`     | Current open price  | `45000.00`             |
| `{{high}}`     | Current high price  | `45500.00`             |
| `{{low}}`      | Current low price   | `44800.00`             |
| `{{volume}}`   | Current volume      | `1234567`              |
| `{{timenow}}`  | Unix timestamp (ms) | `1706745600000`        |
| `{{time}}`     | Bar timestamp       | `2024-02-01T12:00:00Z` |
| `{{exchange}}` | Exchange name       | `COINBASE`             |

---

## Appendix B: Sell Order Payload

For short/sell orders, modify the payload:

```json
{
  "symbol": "BTCUSD",
  "side": "sell",
  "entry": {{close}},
  "sl": {{close}} * 1.01,
  "tp": {{close}} * 0.98,
  "size": 0.01,
  "run_mode": "PAPER",
  "signal": "F:score=95 | F:signal_encoded=95 | F:source=TV_BTC_TEST",
  "score": 95,
  "zone_id": {{timenow}},
  "trade_key": "BTCUSD_{{timenow}}"
}
```

Note: For sell orders, SL is **above** entry and TP is **below** entry.

---

## Section: Exit Webhooks (Update Trade Status & PNL)

To have the dashboard and Mission Control show **Win/Loss** and **PNL** when a trade closes, your strategy must send a **second webhook** when TP or SL is hit, with `event_type: "exit"`.

**Same URL** as entry: `https://your-api.up.railway.app/webhook?secret=...`

**Exit payload (required fields):**

| Field         | Type                                 | Description                                                             |
| ------------- | ------------------------------------ | ----------------------------------------------------------------------- |
| `event_type`  | `"exit"`                             | Must be exactly `"exit"`                                                |
| `zone_id`     | number                               | Same `zone_id` you sent on entry (used to find the row to update)       |
| `trade_key`   | string                               | Optional; if set on entry, use same value here (preferred for matching) |
| `outcome`     | `"win"` \| `"loss"` \| `"breakeven"` | Result of the trade                                                     |
| `close_price` | number                               | Price at which the position closed                                      |
| `exit_type`   | string                               | e.g. `"tp"`, `"sl"`, `"manual"`                                         |
| `bars_held`   | number                               | Bars the position was held                                              |
| `mae_pips`    | number                               | Max adverse excursion in pips                                           |
| `pnl_usd`     | number                               | Optional; P&L in USD                                                    |
| `pnl_r`       | number                               | Optional; P&L in R-multiples                                            |

**Example exit payload (TP hit):**

```json
{
  "event_type": "exit",
  "zone_id": 18580,
  "trade_key": "NAS100_1738600000",
  "outcome": "win",
  "close_price": 25920.68,
  "exit_type": "tp",
  "bars_held": 12,
  "mae_pips": 5.0,
  "pnl_r": 2.0,
  "pnl_usd": 150.0
}
```

In Pine Script: create a **second alert** that fires when your exit condition is met (TP hit, SL hit, or manual close) and set the message to the exit JSON above, using the **same `zone_id`** (and `trade_key` if you use it) as the entry alert. The worker will update the `trading_signals` row to `status=closed`, set `outcome` and `pnl_usd`, and the dashboard will show the result.

**Local test:** Use `scripts/simulate_exit.py` with `ZONE_ID=<your active trade's zone_id>` to simulate an exit and verify the row and dashboard update.

---

**Document End**

_Last Updated: 2026-02-03_
