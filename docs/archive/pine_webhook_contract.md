# Pine Script → Python Webhook Contract
> Derived from `src/api.py:_validate_webhook_payload`, `src/core/signal.py`, and `src/worker.py` payload.get() calls.  
> **Do not modify this contract without updating all consuming modules listed in each field's "Used By" column.**

---

## Transport

| Property | Value |
|----------|-------|
| Method | `POST /webhook` |
| Auth | `X-Webhook-Secret` header (or `Authorization: Bearer <secret>` or `?secret=`) |
| Content-Type | `application/json` |
| Rate Limit | 60 req/min per IP |
| Queue | `signals:default` (Redis LPUSH) |

---

## Payload Schema

### Core Trade Fields (Required for entry signals)

| Field | Type | Example | Used By |
|-------|------|---------|---------|
| `symbol` | `string` | `"XAUUSD"` | All guards, all modules |
| `side` | `"buy" \| "sell"` | `"buy"` | Execution, correlation |
| `entry` | `float` | `2501.50` | Risk engine, size guard |
| `sl` | `float` | `2490.00` | Risk engine, size guard |
| `tp` | `float` | `2530.00` | Consistency analyzer |
| `size` | `float` | `0.05` | Size guard, max-lot guard |

### Event Routing

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `event_type` | `"entry" \| "exit"` | `"entry"` | `"exit"` bypasses all entry guards |
| `action` | `"entry" \| "exit"` | `"entry"` | Alternative to `event_type` |
| `run_mode` | `"LIVE" \| "PAPER"` | system config | **Injected by API layer** — Pine value is always overwritten by `system_config` DB |
| `trade_key` | `string` | — | Idempotency key. Format: `{zone_id}_{side}_{bar_time_epoch}` |

### Zone Identity

| Field | Type | Example | Used By |
|-------|------|---------|---------|
| `zone_id` | `int \| string` | `1712345678` | Dedup, DB record, exit matching |
| `zone_type` | `"demand" \| "supply"` | `"demand"` | Pine filters, notifications |
| `zone_grade` | `"A+" \| "A" \| "B+" \| "B" \| "C+" \| "C"` | `"B+"` | Pine filters, AI features |
| `zone_top` | `float` | `2505.00` | DB record |
| `zone_bottom` | `float` | `2498.00` | DB record |
| `zone_size_pips` | `float` | `7.0` | DB record |

### Entry Classification

| Field | Type | Example | Required | Notes |
|-------|------|---------|----------|-------|
| `entry_model` | `"boc" \| "directional" \| "flip" \| "auto"` | `"boc"` | **Required on LIVE Futures** | BUG-03: missing → rejected on LIVE |
| `bar_time` | `string` (ISO 8601) | `"2026-04-09T10:00:00Z"` | **Required for FLIP on LIVE** | BUG-02: missing → rejected on LIVE; must be on 5-min boundary |

### Pine Strategy Metrics (W-plots)

These map directly to Pine's `W0–W17` webhook output variables:

| Field | Pine Plot | Type | Range | Used By |
|-------|-----------|------|-------|---------|
| `score` | W3 | `int` | 0–100 | AI features, pine filters |
| `session` | W5 | `int` | 0=Asian, 1=London, 2=NY, 3=LN-NY | Time-based rules, liquidity scorer |
| `atr_ratio` | W6 | `float` | 0.0–5.0 | Dynamic sizing, risk engine |
| `trend` | W8 | `int` | -1, 0, 1 | Pine filters |
| `htf_trend` | W? | `int` | -1, 0, 1 | Pine filters |
| `rsi` | W9 | `float` | 0–100 | AI features |
| `rvol` | W11 | `float` | 0.0–5.0 | Liquidity scorer hard gates |
| `adx` | W12 | `float` | 0–100 | Liquidity scorer dynamic thresholds |
| `freshness` | W? | `int` | 1–10 | Pine filters, zone quality |
| `touch_count` | W? | `int` | 1–N | Pine filters |
| `base_quality` | W? | `int` | 0–100 | Zone quality score |
| `departure_strength` | W? | `float` | 0–100 | Liquidity scorer, AI features |
| `return_strength` | W? | `float` | 0–100 | Liquidity scorer |

### Liquidity Metrics

| Field | Type | Notes |
|-------|------|-------|
| `liquidity_distance` | `float` | Raw price distance to nearest liquidity level |
| `liquidity_distance_pips` | `float` | Same, expressed in pips |
| `liquidity_spread` | `float` | Raw spread at liquidity level |
| `liquidity_spread_pips` | `float` | Same, expressed in pips |
| `liq_swept` | `bool` | Liquidity sweep occurred |
| `target_swept` | `bool` | Target liquidity was swept |
| `caused_sweep` | `bool` | This zone caused the sweep (required for 1-candle liq trades) |
| `is_accuracy` | `bool` | Accuracy mode override |

### Account / Risk Context

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `account_balance` | `float` | settings default | USD balance from Pine's `account_size_usd` input |
| `risk_percent` | `float` | settings default | e.g. `1.0` for 1% |

---

## API-Injected Fields (Added at `POST /webhook`, not from Pine)

These are stamped by the API layer before the payload enters the Redis queue:

| Field | Source | Purpose |
|-------|--------|---------|
| `run_mode` | `system_config` DB (cached 30s) | Authoritative LIVE/PAPER mode — always overwrites Pine value |
| `_webhook_receipt_id` | `uuid4()` | Frontend visibility tracking |
| `_correlation_id` | `uuid4()` | Links Council AI run to this signal |
| `_account_id` | `AccountRouter.resolve_account_id()` | Target broker profile routing |
| `_signal_source` | `User-Agent` header detection | `"tradingview"` or `"webhook"` |

---

## Guard Consumption Map

Which guards read which fields:

```
check_env_kill_switch      ← settings only (no payload fields)
check_size_guard           ← size, entry, sl, account_balance, risk_percent
check_max_lot_guard        ← size
check_futures_entry_model  ← symbol, entry_model, run_mode
  └── check_flip_timing    ← entry_model, bar_time, run_mode
symbol_whitelist           ← symbol
staleness_guard            ← entry, sl, run_mode
holiday_guard              ← symbol, (current UTC date)
pine_filters               ← zone_grade, score, session, trend, htf_trend,
                             freshness, touch_count, atr_ratio, rsi,
                             rvol, adx, liq_swept, target_swept, caused_sweep
liquidity_scorer           ← rvol, adx, session, departure_strength,
                             return_strength, liquidity_distance_pips,
                             liquidity_spread_pips, caused_sweep
redis_kill_switch          ← run_mode (determines fail-open vs fail-closed)
prop_guard                 ← account_balance (from DB daily PnL)
correlation_guard          ← symbol, side
consistency_analyzer       ← entry, tp, size, symbol
```

---

## Exit Signal Shape

Exit signals skip all entry guards and route directly to `logic.process_trade`:

```json
{
  "event_type": "exit",
  "zone_id": 1712345678,
  "symbol": "XAUUSD",
  "side": "sell",
  "run_mode": "LIVE"
}
```

---

## Constraints & Invariants

1. `run_mode` is **always set by the system** (`system_config` DB) — Pine's value is discarded.
2. `bar_time` is **mandatory on LIVE** for any `entry_model` containing `"flip"`.
3. `entry_model` is **mandatory on LIVE** for all Futures symbols (Gold, NQ, Crude, etc.).
4. `trade_key` should be globally unique per signal. Missing `trade_key` disables idempotency protection.
5. `size` must be `> 0`. A size of `0` is treated as a calculation error (SL too wide or missing prices).
6. All float fields sent as strings are coerced by the API parser. Unquoted ISO dates in the raw body are auto-quoted before JSON parsing.
