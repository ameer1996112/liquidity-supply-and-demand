# Worklog

## 2026-05-08 - RD Concepts Research Data Lake Implementation

**Problem:** The trading bot needed an offline evidence layer for RD Concepts pair, setup, session, and rule research before PineScript tuning.

**Solution:**
- Added the isolated `scripts/rd_concepts_pipeline/` utility package
- Added Discord channel discovery, scraping, parsing, rule extraction, knowledge-base aggregation, and Streamlit browsing
- Wrote fixture-driven tests under `tests/rd_concepts_pipeline/`
- Kept generated Discord archives under ignored `data/rd_concepts/`

## 2026-05-08 — RD Concepts Research Data Lake Design

**Problem:** The bot can execute the existing strategy, but the missing layer is evidence for which RD Concepts pairs, setups, sessions, and strategy rules should be trusted before tuning PineScript and prop-firm execution permissions.

**Solution:**
- Wrote `docs/superpowers/specs/2026-05-08-rd-concepts-data-lake-design.md`
- Scoped the work as an offline Discord research data lake under `scripts/rd_concepts_pipeline/`
- Chose `data/rd_concepts/` for raw archives, image downloads, processed signals, rules, concept maps, and dashboard-ready summaries
- Deferred live execution changes and PineScript tuning until the dataset is clean and reviewable

- [src/api_positions.py, src/services/live_positions_aggregator.py, frontend/src/app/page.tsx] Live dashboard positions were tied to a single broker adapter and silently degraded to signal fallback in multi-account mode [added multi-account live aggregation across MetaAPI and cTrader for `/positions/active` and `/positions/account`, plus a pure fallback mapper that preserves `signal.size` when degraded fallback is used]

- [scripts/pinescript/strategies/SND_Strategy.pine] Silver pairs were still eligible for accuracy zones even though gold already bypassed them [excluded `is_silver` from `should_use_accuracy_zones` so `XAGUSD` behaves like `XAUUSD` in plotted zones and webhook payloads]

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
