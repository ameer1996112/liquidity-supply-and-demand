# Exit Webhook Bug Fix Plan — COMPLETED ✅

## Bugs Fixed

1. [x] Exit payload missing `run_mode`, `symbol`, `side` → backend defaults to PAPER, never closes MT5
2. [x] `exit_type` always "unknown" → added `comment_loss`/`comment_profit` to all `strategy.exit()` calls
3. [x] DB marked CLOSED BEFORE broker close → moved `update_alert_exit()` to AFTER confirmed broker close
4. [x] Backend `exit_run_mode` fallback was "PAPER" → now uses `get_settings().run_mode`
5. [x] No symbol verification → added symbol mismatch guard before `close_order()`

## Files Changed

- [x] `scripts/pinescript/libraries/SND_Utils.pine` — added `_symbol`, `_side`, `_run_mode` params to `build_exit_webhook_payload()`
- [x] `scripts/pinescript/strategies/SND_Strategy.pine` — passes `syminfo.ticker`, `exit_side`, `"LIVE"` to exit payload; fixed `exit_type` detection; added `comment_loss`/`comment_profit` to all 28 `strategy.exit()` calls
- [x] `src/logic.py` — fixed `exit_run_mode` fallback; moved `update_alert_exit()` after broker close; added symbol mismatch guard

## New Exit Payload (after fix)

```json
{
  "event_type": "exit",
  "zone_id": 18868,
  "symbol": "GBPCAD",
  "side": "buy",
  "run_mode": "LIVE",
  "outcome": "loss",
  "bars_held": 1,
  "close_price": 1.81852,
  "pnl_r": -1.0,
  "pnl_usd": -327.26,
  "exit_type": "sl_hit",
  "mae_pips": 12.3,
  "close_time": "2025-01-15 10:00:00"
}
```
