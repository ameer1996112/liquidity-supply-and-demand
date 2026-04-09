# Notification Upgrade — Task Tracker (DEV-76)

| # | Task | Status |
|---|---|---|
| 1 | Delete command system files | [x] done |
| 2 | Remove TelegramPoller from worker.py | [x] done |
| 3 | Strip whitelist/command endpoints from api_notifications.py | [x] done |
| 4 | Remove frontend command/whitelist panels | [x] done |
| 5 | Extend NotificationPayload with new fields | [x] done |
| 6 | Upgrade Discord embed render | [x] done |
| 7 | Upgrade Telegram render — sendPhoto fallback | [x] done |
| 8 | Wire new fields into worker signal dispatch | [x] done |
| 9 | End-to-end smoke test | [x] done (via test suite) |

---

# Python Micro-Module Refactor — Task Tracker (DEV-100)

| # | Phase | Task | Status |
|---|-------|------|--------|
| 1.1 | Phase 1 | Create `src/pipeline/__init__.py` | not_started |
| 1.2 | Phase 1 | Extract `src/pipeline/idempotency.py` | not_started |
| 1.3 | Phase 1 | Extract `src/pipeline/audit.py` | not_started |
| 1.4 | Phase 1 | Extract `src/pipeline/signal_filter.py` | not_started |
| 1.5 | Phase 1 | Extract `src/pipeline/account_state.py` | not_started |
| 1.6 | Phase 1 | Extract `src/pipeline/account_guards.py` | not_started |
| 1.7 | Phase 1 | Extract `src/pipeline/profile_executor.py` | not_started |
| 1.8 | Phase 1 | Extract `src/pipeline/trade_processor.py` | not_started |
| 1.9 | Phase 1 | Trim `src/worker.py` to queue loop only | not_started |
| 1.T | Phase 1 | `pytest tests/ -v` → 349 passed | not_started |
| 2.1 | Phase 2 | Extract `src/ai/feature_engineer.py` | not_started |
| 2.2 | Phase 2 | Extract `src/ai/llm_client.py` | not_started |
| 2.3 | Phase 2 | Extract `src/ai/rf_threshold.py` | not_started |
| 2.4 | Phase 2 | Extract `src/ai/rf_predictor.py` | not_started |
| 2.5 | Phase 2 | Extract `src/ai/ensemble.py` | not_started |
| 2.6 | Phase 2 | Trim `src/ai/brain.py` to re-export shim | not_started |
| 2.T | Phase 2 | `pytest tests/ -v` → 349 passed | not_started |
| 3.1 | Phase 3 | Extract `src/api_lifecycle.py` | not_started |
| 3.2 | Phase 3 | Extract `src/api_webhook.py` | not_started |
| 3.3 | Phase 3 | Trim `src/api.py` to app factory only | not_started |
| 3.T | Phase 3 | `pytest tests/ -v` → 349 passed | not_started |
| 4.1 | Phase 4 | Extract `src/pipeline/signal_forward.py` | not_started |
| 4.2 | Phase 4 | Extract `src/pipeline/trade_entry.py` | not_started |
| 4.3 | Phase 4 | Extract `src/pipeline/trade_exit.py` | not_started |
| 4.4 | Phase 4 | Trim `src/logic.py` to thin dispatcher | not_started |
| 4.T | Phase 4 | `pytest tests/ -v` → 349 passed | not_started |
| 5.1 | Phase 5 | Extract `src/adapters/execution/http_retry.py` | not_started |
| 5.2 | Phase 5 | Extract `src/adapters/execution/order_submitter.py` | not_started |
| 5.3 | Phase 5 | Extract `src/adapters/execution/order_manager.py` | not_started |
| 5.4 | Phase 5 | Extract `src/adapters/execution/account_info.py` | not_started |
| 5.5 | Phase 5 | Extract `src/adapters/execution/position_reader.py` | not_started |
| 5.6 | Phase 5 | Trim `src/adapters/execution/meta_api_adapter.py` to skeleton | not_started |
| 5.T | Phase 5 | `pytest tests/ -v` → 349 passed | not_started |
| 6.1 | Phase 6 | Extract `src/core/risk_models.py` | not_started |
| 6.2 | Phase 6 | Extract `src/core/position_sizer.py` | not_started |
| 6.3 | Phase 6 | Extract `src/core/risk_guardian.py` | not_started |
| 6.4 | Phase 6 | Trim `src/core/risk_engine.py` to re-export shim | not_started |
| 6.T | Phase 6 | `pytest tests/ -v` → 349 passed | not_started |
| 7.1 | Phase 7 | Extract `src/core/guard_rails/currency_utils.py` + `correlation_db.py` | not_started |
| 7.2 | Phase 7 | Extract `src/core/time_rules.py` | not_started |
| 7.3 | Phase 7 | Extract `src/services/notification_formatters.py` + `notification_utils.py` | not_started |
| 7.4 | Phase 7 | Extract `src/services/liquidity_threshold.py` | not_started |
| 7.5 | Phase 7 | Extract `src/core/guard_rails/pine_filters.py` | not_started |
| 7.T | Phase 7 | `pytest tests/ -v` → 349 passed | not_started |
| F.1 | Final | Update `docs/registry.md` with new module map | not_started |
| F.2 | Final | Close DEV-100 | not_started |
