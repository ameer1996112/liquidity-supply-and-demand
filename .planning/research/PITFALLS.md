# Domain Pitfalls: Prop Firm Challenge Tracker

**Domain:** Real-time prop firm challenge tracking embedded in a live trading bot
**Researched:** 2026-03-18
**Overall confidence:** HIGH — findings grounded in codebase analysis of existing `prop_firm_tracker.py`, `mtm_guardian.py`, `api_funding.py`, and `CONCERNS.md`, plus domain knowledge of FTMO rules

---

## Critical Pitfalls

Mistakes that cause funded account loss or silent rule breaches.

---

### Pitfall 1: Daily Reset at UTC Midnight Instead of CET/EET Midnight

**What goes wrong:**
FTMO resets the daily drawdown counter at midnight **New York time (00:00 EST/EDT)**, not UTC midnight. Other firms use different reference times — The5ers and FundedNext use server time (MT5 server time, usually UTC+2/+3 EET). When the reset boundary is wrong, a trade closed at 22:30 UTC that is actually a "new day" trade for FTMO gets charged against the previous day's drawdown. Even worse: if your bot's daily `today_start` is computed in UTC and the prop firm uses New York midnight, there's a 5-6 hour window (CET is UTC+1 in winter, UTC+2 in summer) where trades cross the boundary differently in your system vs. the firm.

**Why it happens:**
The current `prop_firm_tracker.py` (line 104) and `mtm_guardian.py` (line 104) compute `today_start` as:
```python
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
```
This is pure UTC midnight — not FTMO's reset boundary.

**Consequences:**
- Daily drawdown appears partially consumed at the start of a new FTMO day (trades from 00:00-05:00 UTC show against "today" in our DB but against "yesterday" on FTMO's dashboard)
- "Days traded" counter counts a day too early or too late
- Alert at 80% threshold could fire falsely or — worse — not fire before actual breach
- During DST transitions (twice a year) the offset shifts by 1 hour, creating a systematic off-by-one that exists for ~6 months of the year

**Prevention:**
- Store the firm's reset timezone per `prop_firm_rules` row (e.g., `reset_tz: "America/New_York"`)
- When querying `today_start`, convert to firm's timezone: `today_in_firm_tz = datetime.now(ZoneInfo(reset_tz)).replace(hour=0, ...)`
- Use `zoneinfo` (Python 3.9+) or `pytz` — never hardcode UTC offsets; DST will break them
- Seed FTMO rule with `reset_tz = "America/New_York"` at launch

**Warning signs:**
- Daily drawdown shown on dashboard differs from FTMO dashboard by a consistent dollar amount
- "Days traded" count is 1 off compared to FTMO's records
- Discrepancies always appear near midnight UTC or midnight CET

**Phase:** Must be addressed in Phase 1 (rules DB + reset boundary logic) before any dashboard display.

---

### Pitfall 2: Daily Drawdown Calculated on Closed Trades Only

**What goes wrong:**
FTMO's daily drawdown rule counts floating (open) losses. If you have a $200 closed loss and a $350 floating loss on an open position, your real drawdown against the daily limit is $550 — not $200. A dashboard that only sums `pnl_usd` on CLOSED rows will show you are within limits when you are actually breaching them.

**Why it happens:**
`api_funding.py` `_fetch_closed_signals()` only fetches signals with status in `["closed", "executed", "CLOSED", "EXECUTED"]`. Open positions are excluded. The `mtm_guardian.py` does compute floating PnL correctly, but it uses `yfinance` for current prices — which returns 0 during market close, weekends, or rate-limit failures. When `get_current_price()` returns 0, the MTM guard explicitly skips that position (line 155-160), meaning floating loss is silently excluded from the equity calculation.

**Consequences:**
- Dashboard shows user is "safe" when they are actually at -4.8% daily drawdown (above the 5% limit)
- Kill switch does not engage; more trades execute; account blown
- This is not hypothetical — the existing kill switch in `mtm_guardian.py` has this exact vulnerability

**Prevention:**
- Prefer broker equity directly from MetaAPI (`account_status_snapshots.equity`) as the source of truth for current equity — not calculated equity
- MetaAPI's equity field already includes floating PnL, commissions, and swaps — no manual floating calculation needed
- Fall back to calculated equity only if MetaAPI snapshot is stale (> 5 minutes old)
- When using `account_status_snapshots`, the drawdown formula becomes: `daily_dd_pct = (day_start_balance - current_equity_from_broker) / day_start_balance * 100`
- Alert if MetaAPI snapshot age exceeds 2 minutes — show a "data stale" warning in the UI rather than a falsely reassuring metric

**Warning signs:**
- Floating PnL in dashboard shows $0 when positions are open
- `current_equity` stays flat despite open positions moving against the trader
- `yfinance` rate limit errors in logs

**Phase:** Critical for the daily drawdown progress bar. Phase 1 must use broker equity as primary source.

---

### Pitfall 3: Day-Start Balance Captured at Wrong Moment

**What goes wrong:**
The daily drawdown percentage is `(day_start_balance - current_equity) / day_start_balance`. If `day_start_balance` is wrong, every drawdown calculation is wrong. There are three common failure modes:

1. **No snapshot at day start** — `prop_firm_tracker.py` checks if a `prop_firm_metrics` row exists for today. If the service was down at midnight, no row exists, and it falls back to `_get_live_balance()` which returns the *current* balance — not the start-of-day balance. If the account is already down $500 when the service restarts, the "daily drawdown" will be 0% even though $500 has already been lost.

2. **Balance vs Equity confusion** — FTMO measures daily drawdown from the *equity* at reset time, not the *balance*. Balance does not include floating PnL. If you started the day with 2 open positions worth +$300 floating, your starting equity was $50,300 but your balance was $50,000. Using balance underestimates your starting equity and makes your drawdown look larger than it is.

3. **`account_status_snapshots` uses balance, not equity** — `mtm_guardian.py` line 236 takes `day_start_snap.data[0]["balance"]` as the starting value. This is the balance field, not equity.

**Consequences:**
- Daily drawdown shown as 0% after a service restart that happens after losses already occurred
- Traders see false "safe" status for the rest of the day
- Or: Drawdown appears inflated due to balance/equity confusion, causing premature false alerts

**Prevention:**
- Run a daily reset job at exactly the firm's reset boundary (not UTC midnight) that captures `account_status_snapshots.equity` (not `balance`) as `day_start_equity`
- Store `day_start_equity` in `prop_firm_rules` or a dedicated `daily_reset_snapshots` table keyed by `(account_id, date_in_firm_tz)`
- On startup, if today's `day_start_equity` is missing, query MetaAPI directly for the first available equity snapshot after today's reset boundary
- Never fall back to "current balance" as the starting value

**Warning signs:**
- Service restart logs show "No snapshot for today, using current balance"
- Day-start balance in the DB matches current balance exactly (shouldn't happen if losses occurred)
- Dashboard drawdown jumps to 0% after service restarts

**Phase:** Must be part of Phase 1 database schema — `day_start_equity` column, not derivable on the fly.

---

### Pitfall 4: Drawdown Denominator: Starting Balance vs. Account Size

**What goes wrong:**
FTMO uses different denominators for different drawdown types:
- **Daily drawdown**: measured from equity at start of that trading day
- **Maximum (trailing) drawdown (Phase 1/2)**: measured as % of the **initial account balance** (e.g., $50,000) — it does NOT trail the high water mark
- **Maximum drawdown (Funded/Swing)**: this IS trailing — measured from the highest equity ever achieved

Getting the denominator wrong by even 5% causes alerts to fire at the wrong thresholds.

**Why it happens:**
`prop_firm_tracker.py` lines 153-157:
```python
trailing_drawdown_pct = (
    (max_historical_equity - current_equity) / max_historical_equity * 100
```
This divides by `max_historical_equity` — correct for funded/swing accounts. But for Phase 1 and Phase 2, FTMO measures max drawdown from the **initial account balance** ($50,000), not from the high water mark. If your account grew to $53,000, your max drawdown denominator on Phase 1 is still $50,000 — not $53,000.

**Consequences:**
- Phase 1/2 max drawdown appears smaller than it is (false safety)
- The firm can fail you for an 8% drawdown while your tracker shows only 7.5%

**Prevention:**
- Store `initial_balance` (the original account size at challenge start) separately from `day_start_equity`
- The `prop_firm_rules` table should include a `drawdown_reference` field: `"initial_balance"` vs `"trailing_high_water_mark"`
- For FTMO Phase 1 and Phase 2: `max_dd_pct = (initial_balance - current_equity) / initial_balance * 100`
- For FTMO Funded (Swing): `max_dd_pct = (all_time_high_equity - current_equity) / all_time_high_equity * 100`

**Warning signs:**
- Tracker shows max drawdown lower than the actual account drop
- Account fails prop firm challenge but dashboard showed it within limits

**Phase:** Phase 1 (rules seeding). The rules DB schema must encode `drawdown_reference` per challenge type.

---

## Moderate Pitfalls

---

### Pitfall 5: MetaAPI Snapshot Staleness During Volatile Moves

**What goes wrong:**
`account_status_snapshots` is populated by `AccountSyncService` polling MetaAPI. The polling interval is not documented in the reviewed code, but if it is 30+ seconds, a fast $500 drawdown in volatile news (e.g., NFP, FOMC) happens between snapshots. The dashboard shows the pre-move equity for up to 30-60 seconds, during which the user sees a safe reading while the bot is actually in breach.

**Prevention:**
- Display the snapshot age prominently in the UI (e.g., "as of 23s ago")
- Show a "stale data" warning badge if snapshot age > 30 seconds
- For the kill switch, use a tighter TTL than for display — `mtm_guardian.py` has `mtm_cache_ttl_seconds=10`, which is reasonable, but must be verified against actual polling interval
- Never display a drawdown percentage without showing its data freshness

**Warning signs:**
- `snapshot_time` in `account_status_snapshots` is consistently >30 seconds behind `now()`
- Dashboard equity stays flat during a fast-moving market

**Phase:** Phase 2 (UI display). Show timestamp alongside all metrics.

---

### Pitfall 6: Floating PnL Approximation Error in MTM Guardian

**What goes wrong:**
`mtm_guardian.py` calculates floating PnL using `yfinance` prices and hardcoded pip values. Three specific errors compound:

1. **JPY pairs**: uses `pip_value_per_lot = 1000.0` (hardcoded, line 168) — but as documented in MEMORY.md, NZDJPY's actual pip value is ~$10.65/lot. This creates a 94× error in floating PnL for open JPY positions.
2. **Indices/crypto**: fall through to the forex default (`pip_size=0.0001`, `pip_value=10.0`) — same classification bug that caused the NZDJPY sizing issue.
3. **`yfinance` returns 0 on weekends/market close** — skipped silently (line 155-160), so floating PnL shows $0 for all positions during off-hours.

**Prevention:**
- Do not use the approximation path at all if MetaAPI equity is available — broker equity already includes real floating PnL
- If broker equity is unavailable, use the same `risk_engine.py` dynamic pip value calculation — never hardcode pip values in MTM
- For the dashboard specifically: source floating PnL from `account_status_snapshots.equity - account_status_snapshots.balance` — this is the broker's own floating PnL figure, already correct for all instruments

**Warning signs:**
- Floating PnL shows $0 at weekends
- Floating PnL for JPY pairs is wildly different from broker's reported unrealized PnL
- Broker equity and calculated equity disagree by large amounts (>$10)

**Phase:** Relevant to Phase 1 (metrics calculation). Avoid the approximation path; use broker equity.

---

### Pitfall 7: `trades_today` Always Returns 0

**What goes wrong:**
`prop_firm_tracker.py` line 255:
```python
"trades_today": 0,  # TODO: Calculate from trading_signals
```
This is hardcoded. It is written to the `prop_firm_metrics` snapshot table on every save. Any "trading days" counter that reads this column will always show 0 active trades.

**Consequences:**
- "Days traded" counter in the dashboard shows wrong values
- FTMO requires minimum 4 trading days (Phase 1) — if the tracker always shows 0 trades/day, the minimum days requirement cannot be validated
- Board ticket BUG-class: the field exists in the schema but is never populated

**Prevention:**
- Implement `trades_today` before displaying it: count rows in `trading_signals` where `account_name = X`, `status IN ('CLOSED','EXECUTED')`, and `closed_at >= today_start_in_firm_tz`
- A "trading day" for FTMO is a calendar day (CET) where at least one trade was **closed** — not just opened
- Cache the count per account per day in Redis to avoid repeated DB queries on every 5-second refresh

**Warning signs:**
- `prop_firm_metrics` table shows `trades_today=0` for all rows even on active trading days
- "Minimum trading days" progress bar stays at 0

**Phase:** Phase 2 (metrics display). Must be fixed before showing trading days progress.

---

### Pitfall 8: Counting "Trading Days" by Open vs. Close Date

**What goes wrong:**
FTMO counts a day as "traded" when at least one trade is **closed** on that day — not opened. If a trader opens 5 trades on Monday but closes them all on Tuesday, FTMO counts Tuesday as a trading day, not Monday. Counters that group by `created_at` will miscount.

`api_funding.py` line 190-193 uses `closed_at OR created_at` as the trading date:
```python
dt_str = sig.get("closed_at") or sig.get("created_at", "")
```
If `closed_at` is NULL (rare but possible for partially-filled positions), it falls back to `created_at`, which is the open date — potentially a different calendar day.

**Prevention:**
- Count trading days using `closed_at` only, never `created_at`
- If `closed_at` is NULL, exclude the trade from the count (it is not yet closed, so it does not contribute to the trading day requirement)
- Ensure `closed_at` is always populated when a position closes — check `logic.py` close handler

**Warning signs:**
- Trading days count is 1 ahead of FTMO's count
- Trades with `closed_at IS NULL` but status=CLOSED exist in the database (pre-existing data quality issue per MEMORY.md)

**Phase:** Phase 2 (days counter). Combine with the `trades_today` fix.

---

### Pitfall 9: Auto-Detection Confidence — Server Name String Matching

**What goes wrong:**
The planned auto-detection uses `broker server name` (e.g., `FTMO-Server3` → FTMO). Server name formats change without notice. FTMO has used: `FTMO-Demo`, `FTMO-Demo2`, `FTMO-Server`, `FTMO-Server2`, `FTMO-Server3`, `FTMO-ECN`. A simple `startswith("FTMO")` works today; `contains("FTMO")` is safer. But if FTMO introduces `FTMO-Markets-Server1` for a new product line, the match will succeed but the rules might not apply (different challenge type / rules).

**Prevention:**
- Match on `CONTAINS "FTMO"` (case-insensitive) — not exact prefix
- After matching, always show the detected firm name in the UI for user confirmation on first use
- Store `detected_server_name` alongside `detected_firm` in the account's DB record — allows debugging false matches
- If server name contains no recognized firm keyword, show "Unknown firm — configure manually" rather than silently applying wrong rules
- Never crash if detection fails — degrade gracefully to empty metrics

**Warning signs:**
- New FTMO account added but no challenge metrics appear (server name format changed)
- Rules applied to an account that uses a different firm's server name that contains "FTMO" in it

**Phase:** Phase 1 (detection logic). Implement conservative matching with explicit fallback.

---

### Pitfall 10: Display Inconsistency — Progress Bars > 100% or Negative

**What goes wrong:**
If `current_equity > day_start_equity` (profitable day), `daily_drawdown_pct` will be negative. A progress bar filled to `-12%` is undefined behavior in most UI frameworks — it either shows 0%, overflows, or throws a render error. Similarly, if the starting balance recorded is lower than the actual current equity due to a stale snapshot, the bar can show > 100%.

This happened in similar systems when a large winning trade closed on the same timestamp as the daily reset, causing `day_start_equity` to be captured *after* the win, making subsequent smaller losses show as abnormally large percentages.

**Prevention:**
- Clamp all percentage values server-side before returning: `max(0.0, min(dd_pct, 100.0))`
- Return both the raw value and clamped value — log a warning when raw exceeds bounds (signals a data integrity issue)
- In the frontend, always show the underlying USD amount alongside the percentage — "3.2% ($1,600 of $50,000 limit)" — so the user can sanity-check if the percentage looks wrong

**Warning signs:**
- Progress bar fills to 0% even though there are known losses
- Progress bar renders at > 100% width
- Console errors in browser on the accounts page

**Phase:** Phase 2 (UI rendering). Defensive clamping in the API layer.

---

### Pitfall 11: Concurrent Reads During High-Frequency Metric Polling

**What goes wrong:**
The accounts page is planned to poll at 5-second intervals. With multiple accounts (e.g., 3 FTMO accounts), that is 3 × 12 = 36 Supabase queries per minute just for metrics. Each call to `get_current_metrics()` in `prop_firm_tracker.py` makes at least 3 Supabase queries (prop_firm_metrics snapshot, account_status_snapshots equity, account_status_snapshots day_start). That is 108 Supabase queries per minute — on a service with no connection pooling (per CONCERNS.md).

At Supabase free/pro tier limits, this approaches the connection ceiling quickly. The existing concern about "100 concurrent requests saturate connection limit" (CONCERNS.md) applies here directly.

**Prevention:**
- Pre-compute the metrics bundle server-side and cache it in Redis with a 5-second TTL, keyed by `account_id`
- The frontend polls one cached endpoint: `GET /api/v1/prop-firm/metrics/{account_id}`
- The backend updates Redis from a background task (APScheduler, 5-second interval) rather than computing on every HTTP request
- This is the same architecture used by the positions page (per PROJECT.md: "match existing positions page pattern (5s interval)")

**Warning signs:**
- Supabase connection errors under normal load after adding prop firm metrics
- API response time for metrics endpoint > 1 second
- Timeouts on `/positions` after prop firm metrics polling is enabled

**Phase:** Phase 2 (API design). Do not compute on every request — compute and cache.

---

### Pitfall 12: Breach Detection Without Guard Rail Enforcement Gap

**What goes wrong:**
The dashboard shows an alert at 80% of the daily drawdown limit. But the existing kill switch (in `worker.py`) uses `trinity_max_daily_loss_pct` — a bot-internal limit that may be set lower than the FTMO limit. If the bot's kill switch fires at 4% but FTMO's limit is 5%, that is intentionally conservative. However, if someone changes the bot setting to 6% (above the firm's limit) without updating the firm rules DB, the kill switch will allow trades that breach the FTMO limit.

**Prevention:**
- The prop firm rules DB should be the authoritative source for both the display limit (dashboard) AND the kill switch limit
- When a firm rule is loaded for an account, automatically set the bot's `max_daily_loss_pct` to `firm_daily_dd_limit - safety_margin` (e.g., FTMO 5% → bot kills at 4%)
- Never allow `worker.py` kill switch threshold to exceed the firm's published limit for a funded account
- Log a warning at startup if `trinity_max_daily_loss_pct > prop_firm_daily_limit`

**Warning signs:**
- `trinity_max_daily_loss_pct` in settings does not match or exceed the firm rule for any account
- Prop firm dashboard shows 4.8% consumed but kill switch already engaged at 4%

**Phase:** Phase 1 (rules seeding + connection to risk engine). Document this contract in `docs/decisions.md`.

---

## Minor Pitfalls

---

### Pitfall 13: Challenge Type Never Re-Asked After Switch

**What goes wrong:**
The system saves challenge type (Phase 1 / Phase 2 / Funded) once and "never asks again." When a trader passes Phase 1 and starts Phase 2 on the same account, the rules do not auto-update. This is a known UX edge case: the account server name stays the same, but the rules change (Phase 2 has different profit target and time window).

**Prevention:**
- Provide a "Reassign challenge type" button in the UI — visible but not prominent
- When the profit target for Phase 1 is reached (10% for FTMO), show a prompt: "Congratulations — have you been promoted to Phase 2?"
- Log when the stored challenge type would produce a profit target already exceeded (implies stale type)

**Phase:** Phase 2 (UX). Minor — document the limitation clearly in the UI.

---

### Pitfall 14: Swaps and Commissions Excluded from Drawdown Calculation

**What goes wrong:**
FTMO counts commissions and overnight swap charges against the daily drawdown. A day where the trader breaks even on pips but pays $80 in commissions + $45 in swap is a -$125 day against the drawdown limit. If the metric only sums `pnl_usd` (the profit/loss from price movement) and excludes `commission` and `swap` columns in the DB, the drawdown will be understated.

`api_funding.py` sums `pnl_usd` which in the current implementation is set from `profit + commission + swap` when a trade closes (per MEMORY.md fix in the PnL Mismatch fix). So this is currently correct — but only for trades that went through the fixed close path. Pre-fix historical trades may have `pnl_usd` = price-movement only, with commission/swap not included.

**Prevention:**
- When displaying "total PnL for today" for prop firm purposes, sum `pnl_usd + commission + swap` explicitly (not just `pnl_usd`)
- Or: rely on broker equity (which natively includes all charges) as the source of truth
- Add a note in the UI: "P&L includes commissions and swap"

**Phase:** Phase 1 (data model). Verify historical data integrity before computing drawdown from DB columns.

---

### Pitfall 15: Status Case Inconsistency Silences Daily PnL

**What goes wrong:**
`CONCERNS.md` documents that `worker.py:642` uses lowercase `["active", "executed", "closed"]` while the DB stores uppercase. This same bug affects prop firm metrics: if `mtm_guardian.py`'s closed PnL query misses uppercase CLOSED/EXECUTED rows, it will show $0 daily closed PnL on days where those are the actual statuses stored.

`mtm_guardian.py` line 112 does handle both cases: `.in_("status", ["closed", "CLOSED", "executed", "EXECUTED"])`. So MTM is protected. But any new query added for prop firm tracking that copies the pattern without checking both cases will silently return 0.

**Prevention:**
- Define a canonical status constant list at the module level and import it
- Never write raw string lists for status filters — use the shared constant
- Add a test: query for today's closed signals, assert count > 0 if signals were processed

**Phase:** Phase 1. Use a shared status constant from the first implementation.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Rules DB schema design | Missing `reset_tz`, `drawdown_reference`, `initial_balance` fields | Design schema before coding — see Pitfalls 1, 3, 4 |
| Daily reset boundary | UTC midnight used instead of firm's timezone | Use `zoneinfo`, store `reset_tz` per firm |
| Day-start equity capture | Service down at reset time → wrong starting value | Scheduled job + fallback query for first snapshot after reset |
| Drawdown % formula | Balance vs. equity, wrong denominator for Phase 1 vs. Funded | Encode `drawdown_reference` in rules DB |
| Daily PnL source | Calculated floating PnL has instrument errors | Prefer `broker_equity - day_start_equity` over approximation |
| Metrics polling | 108 Supabase queries/minute | Redis cache + background compute |
| Progress bar display | Negative or >100% percentages | Clamp server-side, show absolute USD alongside % |
| Trading days counter | `trades_today` hardcoded to 0 | Implement before exposing in UI |
| Trading day definition | Counting open date instead of close date | Always use `closed_at`, ignore `created_at` |
| Kill switch alignment | Bot threshold mismatched with firm limit | Rules DB drives kill switch threshold |

---

## Existing Code Bugs That Directly Affect This Feature

These are not hypothetical — they exist in the current codebase and will surface immediately when prop firm metrics go live:

| Bug | File | Impact | Fix Required Before |
|-----|------|--------|---------------------|
| `trades_today` hardcoded to 0 | `prop_firm_tracker.py:255` | Trading days progress bar always 0 | Phase 2 display |
| UTC midnight reset boundary | `prop_firm_tracker.py:104`, `mtm_guardian.py:104` | Daily drawdown wrong by 5-6 hours | Phase 1 |
| JPY pip value hardcoded (×94 error) | `mtm_guardian.py:168` | Floating PnL wildly wrong for JPY pairs | Phase 1 |
| Day-start uses `balance` not `equity` | `mtm_guardian.py:236` | Starting reference wrong by floating PnL at open | Phase 1 |
| Max drawdown denominator wrong for Phase 1 | `prop_firm_tracker.py:153-157` | Max drawdown understated on evaluation accounts | Phase 1 |
| Silent exception swallowing (7 locations) | `prop_firm_tracker.py:78,126,183,202,261,290,314` | Metrics silently return stale/zero values | Phase 1 |

---

*Researched from: codebase analysis of `prop_firm_tracker.py`, `mtm_guardian.py`, `api_funding.py`, `CONCERNS.md`, `PROJECT.md`, FTMO published rules (training knowledge, HIGH confidence for rule structures, MEDIUM confidence for exact reset timezone — verify against current FTMO FAQ before seeding rules DB)*
