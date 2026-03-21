# Webhook Payload Reference — TradingView → Trading Bot

## Overview

TradingView sends webhook alerts to `POST /webhook` (LIVE) or `POST /webhook/test` (dry-run testing).

The bot validates, guards, and executes signals from:
**TradingView Pine Script (S&D Algo [Pro])** → **`POST /webhook`** → **Redis queue** → **Worker** → **MetaTrader (Vantage)**

---

## Entry Signal Payload

Sent when a new S&D zone trade triggers.

```json
{
  "symbol":       "GBPUSD",
  "side":         "buy",
  "entry":        1.25000,
  "sl":           1.24700,
  "tp":           1.25600,
  "size":         0.10,
  "rr_ratio":     2.0,
  "bar_time":     "2026-03-21T10:00:00Z",
  "zone_id":      18108,
  "signal_time":  "2026-03-21T10:00:35Z"
}
```

### Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `symbol` | string | ✅ | Instrument: `GBPUSD`, `NAS100`, `XAUUSD`, etc. |
| `side` | string | ✅ | `"buy"` or `"sell"` |
| `entry` | float | ✅ | Entry price from Pine Script |
| `sl` | float | ✅ | Stop loss price |
| `tp` | float | ✅ | Take profit price |
| `size` | float | ✅ | Lot size calculated by Pine Script |
| `rr_ratio` | float | ⭐ | Risk:Reward ratio — checked against `MIN_RR_RATIO` setting |
| `bar_time` | string | ⭐ | Bar open time (ISO 8601 UTC) — used for staleness + trading hours checks |
| `zone_id` | int | ⭐ | S&D zone ID — links entry → audit trail → exit |
| `signal_time` | string | — | When Pine generated the alert (ISO 8601 UTC) |
| `force_paper` | bool | — | `true` → forces PAPER mode (testing only) |
| `action` | string | — | `"entry"` or `"exit"` |
| `event_type` | string | — | `"exit"` for exit payloads (see below) |

> **⭐ Strongly recommended** — include `rr_ratio`, `bar_time`, `zone_id` in every alert for full guard rail coverage.

---

## Exit Signal Payload

Sent when a position closes (SL/TP hit or manual exit).

```json
{
  "event_type":  "exit",
  "zone_id":     18108,
  "outcome":     "win",
  "bars_held":   12,
  "close_price": 1.25600,
  "exit_type":   "tp",
  "mae_pips":    3.0
}
```

---

## TradingView Alert Setup

In Pine Script, add to your `alert()` call:

```pine
alertcondition(
  entryCondition,
  title="S&D Entry",
  message='{"symbol":"{{ticker}}","side":"buy","entry":{{close}},"sl":' + str.tostring(sl) + ',"tp":' + str.tostring(tp) + ',"size":' + str.tostring(lotSize) + ',"rr_ratio":' + str.tostring(rr) + ',"bar_time":"{{time}}","zone_id":' + str.tostring(zoneId) + '}'
)
```

> `{{ticker}}` and `{{time}}` are TradingView template variables. `{{time}}` outputs ISO 8601 format which the bot handles automatically.

---

## Processing Pipeline

```
TradingView Alert
    │
    ▼
POST /webhook  (rate limited 60/min)
    │
    ├─ Schema validation (EntryWebhookPayload)
    ├─ Staleness guard  (bar_time age)
    ├─ Trading hours    (pine_trading_start/end_hour)
    │
    ▼
Redis Queue
    │
    ▼
Worker
    │
    ├─ Correlation / duplicate check
    ├─ Consecutive loss circuit breaker
    ├─ RR ratio filter  (min_rr_ratio)
    ├─ AI/ML ensemble  (confidence gate)
    ├─ Prop firm guard  (daily loss, drawdown, evaluation phase)
    │
    ▼
MetaTrader (Vantage broker)
    │
    ▼
trading_signals table (Supabase)
```

---

## Testing Your Alert

Use `POST /webhook/test` to validate a payload without executing any trade:

```bash
curl -X POST https://your-backend.railway.app/webhook/test \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your_secret" \
  -d '{
    "symbol": "GBPUSD",
    "side": "buy",
    "entry": 1.25000,
    "sl": 1.24700,
    "tp": 1.25600,
    "size": 0.10,
    "rr_ratio": 2.0,
    "bar_time": "2026-03-21T10:00:00Z"
  }'
```

**Response:**
```json
{
  "dry_run": true,
  "schema_valid": true,
  "parsed_fields": { "symbol": "GBPUSD", "side": "buy", ... },
  "guards": {
    "staleness": { "passed": true, "reason": null },
    "trading_hours": { "passed": true, "bar_hour_utc": 10 },
    "rr_ratio": { "passed": true, "provided": 2.0, "minimum": 1.5 }
  },
  "risk_engine": {
    "account_balance": 50000,
    "risk_percent": 0.5,
    "computed_lot_size": 0.11,
    "sl_distance": 0.003
  },
  "would_execute": true,
  "rejection_reason": null
}
```

---

## Key Settings (`.env` / Railway)

| Variable | Default | Effect |
|---|---|---|
| `WEBHOOK_SECRET` | — | Required header `X-Webhook-Secret` for auth |
| `MIN_RR_RATIO` | `0.0` | Set to `1.5` to reject R:R < 1.5 setups |
| `EVALUATION_MODE` | `false` | `true` = apply FTMO phase limits |
| `EVALUATION_PHASE` | `phase1` | `phase1` / `phase2` / `funded` |
| `PINE_TRADING_START_HOUR` | `0` | UTC hour to start accepting signals |
| `PINE_TRADING_END_HOUR` | `23` | UTC hour to stop accepting signals |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Pause after N consecutive losses |
| `CONSEC_LOSS_PAUSE_HOURS` | `4.0` | Hours to pause after hitting loss streak |
