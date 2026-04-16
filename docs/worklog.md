# Worklog

- [src/api.py] Silent health/AI-mode/websocket cleanup failures and unguarded queue enqueue reduced ingress observability and resilience [added explicit warning/error logging, deduped CORS origins, and return 503 when webhook queueing fails]
- [tests/test_api_webhook_ingress.py] Ingress outage fallback and AI-mode fallback logging had no direct regression coverage [added focused FastAPI tests for queue enqueue failure and settings-based AI-mode fallback]

## 2026-04-16 — Multi-Strategy Bot Design

**Problem:** The trading system still assumes one globally active strategy in key places, but the product direction is to run multiple fully mechanical strategies through one bot while keeping alerts, risk, notifications, analytics, and UI attributable per strategy.

**Solution:**
- Wrote `docs/superpowers/specs/2026-04-16-multi-strategy-bot-design.md`
- Defined a strategy-first architecture where every Pine alert must include `strategy_id` and `strategy_version`
- Specified hard rejection for unknown or inactive strategies
- Defined strategy-aware execution, risk, optimizer, notifications, and page behavior
- Chose one shared webhook channel with strategy identity in the payload, instead of backend inference

**Direction:** One primary live strategy first, additional strategies paper or shadow-only until proven.

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
