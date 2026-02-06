# Backend Logs: Filtered vs Error

Use this to tell whether a signal was **filtered by rules** (by design) or hit an **error** (bug/infra).

---

## Filtered by rules (by design)

These are **WARNING** or **INFO** and mean the bot correctly rejected the signal.

| Log message (contains) | Meaning | DB status |
|------------------------|--------|-----------|
| `SIZE REJECTED: size=0` | Position size was 0 or negative (e.g. TradingView sent `"size":0`). Fix Pine/alert position sizing. | `filtered` |
| `FLIP TIMING REJECTED:` | Entry bar time not on 15m boundary (00/15/30/45). | `filtered` |
| `PINE PRE-FILTER REJECTED:` | Zone score/grade, liq_swept, R:R, trading hours, or daily limit failed. | `filtered` |
| `CORRELATION REJECTED:` | Too many open positions or bucket full. | `correlation_rejected` |
| `PROP GUARD BLOCKED:` | Step-up risk (PropGuard) blocked due to daily PnL/drawdown. | `risk_rejected` |
| `KILL-SWITCH: execution blocked` | Kill switch is ON (env or Redis). | `kill_switch_blocked` |
| `Idempotency: signal_id/trade_key already exists` | Duplicate trade_key; already processed. | (no row or existing row) |
| `AI ensemble rejected` / `NO_GO` | Brain (RF + RAG + LLM) said no. | `ai_rejected` |
| ML confidence below threshold | ML Guardian rejected. | `ml_rejected` |

**Your 3+ signals:** If they had `"size": 0` or `"is_accuracy": false` and weak zone stats, they were likely **filtered** by:

- **Size** → now explicitly logged as `SIZE REJECTED: size=0` and saved as `filtered`.
- **Pine** → score/grade/liq_swept/return_strength/departure_strength/dead zone/hours/daily limit.
- **AI** → ensemble NO_GO (e.g. “no valid demand zone”, “bearish context”).

Check the **notes** column for the row in `trading_signals` (or your Mission Control “Reason”): it will say the exact filter reason.

---

## Errors (bugs / infra)

These are **ERROR** and mean something broke (code, DB, or network).

| Log message (contains) | Likely cause |
|------------------------|--------------|
| `Correlation guard crashed:` | DB or correlation logic exception. |
| `logic.process_trade failed:` | Execution path or Supabase update failed. |
| `Execution adapter error for alert #` | MetaApi/paper adapter threw (e.g. network, invalid order). |
| `TradeWatchdog: ... failed` | MetaApi/stats request failed or Supabase update failed. |
| `Failed to update broker_order_id` | Supabase not initialized or update failed. |
| `Brain load error:` / `Prediction error:` / `RAG query failed:` | AI/ML/RAG init or runtime error (often fail-open so trade may still run). |
| `Failed to fetch alerts` / `Failed to fetch active positions` | Supabase or MetaApi unreachable. |
| `Invalid JSON from queue:` | Malformed webhook payload in Redis. |

If you see **ERROR** lines, copy the full traceback or the line after `ERROR` (e.g. `logic.process_trade failed: ...`) so we can trace the exact failure.

---

## Quick checklist for “did my signal get filtered or error?”

1. In backend logs, search for the **symbol + time** (e.g. `NAS100` and `15:35`).
2. If you see **SIZE REJECTED** / **FLIP TIMING REJECTED** / **PINE PRE-FILTER REJECTED** / **CORRELATION REJECTED** / **PROP GUARD** / **KILL-SWITCH** / **Idempotency** / **NO_GO** / ML reject → **filtered by rules** (check notes in DB for exact reason).
3. If you see **ERROR** and **exception/traceback** → **error** (paste that log section for debugging).
4. In Supabase `trading_signals`, filter by `trade_key` or `zone_id` and check **status** and **notes** for that signal.

---

## Fixing “filtered” signals you want to allow

- **Size 0:** Fix TradingView alert or Pine script so `size` is always a positive number (e.g. from `calc_pos_size_units()` or a min lot).
- **Pine / FLIP:** Adjust config (e.g. `PINE_MIN_SCORE`, `PINE_MIN_GRADE`, trading hours, daily limit) or relax Pine filters in `worker.py` / settings.
- **AI/ML:** Adjust confidence thresholds or RAG rules; or run in shadow mode to still execute when AI says NO_GO.
