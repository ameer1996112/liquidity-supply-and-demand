# Worklog

## 2026-04-12 — Swap Guard (Rollover Protection)

**Problem:** Trades held through broker rollover (00:00 Israel time) were losing due to
spread spikes of 5-10x normal. TradingView signals were also arriving during the window.

**Solution:**
- `SwapGuard` in `src/core/guard_rails/swap_guard.py` — rejects all incoming signals
  during a configurable blackout window (default: 15min before + 15min after rollover)
- `SwapScheduler` in same file — closes all open positions 15min before rollover,
  retries 3x on failure, alerts Discord/Telegram if all retries fail
- Config: `enable_swap_guard`, `swap_time`, `swap_timezone`, `swap_close_before_min`, `swap_block_after_min`
- Wired into `src/worker.py` periodic tick and registered in `guard_registry.py`

**Default:** 00:00 Asia/Jerusalem ±15min, all instruments, all positions closed.
