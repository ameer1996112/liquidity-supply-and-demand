# Technical Concerns & Debt Analysis

This document outlines the security, performance, reliability, and technical debt concerns identified during the codebase mapping process.

## 1. Security Concerns

### 🚩 Webhook Authentication Gaps
- **Fragile Validation**: The `validate_webhook_secret` function in `src/api.py` checks `settings.webhook_secret`. If this is not explicitly set in `.env`, it defaults to an empty string and the validation logic allows **all** incoming signals to pass without authentication.
- **Risk**: Any actor discovering the webhook URL could inject malicious trade signals if the environment is misconfigured.

### 🚩 Hardcoded CORS Origins
- **Production Leak**: `src/api.py` contains hardcoded production URLs for CORS (`https://frontend-production-a7cf.up.railway.app`).
- **Recommendation**: These should be moved to an environment variable (`CORS_ALLOWED_ORIGINS`).

### 🚩 Input Sanitization
- **Date Handling Hack**: `src/api.py` contains custom logic to "fix" unquoted ISO dates from TradingView. This approach is fragile and could break if TradingView changes its payload format slightly.

## 2. Performance & Latency

### 🚩 Blocking I/O in Async Contexts
- **MetaApi Adapter**: `src/adapters/execution/meta_api_adapter.py` uses the standard `requests` library (synchronous/blocking) for trade execution. In a high-concurrency event, this blocks the worker's execution thread, increasing latency for subsequent signals.
- **Startup Block**: `src/api.py` uses `time.sleep(3)` in a loop during the `_fail_fast_config` check, which blocks the event loop on startup.

### 🚩 Supabase Overhead
- **Rotation Hack**: The worker recreates its Supabase client every 90 seconds to avoid HTTP/2 connection staleness issues. This is a workaround for a documented `httpx` limitation but adds constant instantiation overhead.

### 🚩 Cache Pressure
- **Aggressive TTLs**: Many Redis caches use extremely short TTLs (30s). This may lead to "thundering herd" issues or high database load when many account threads wake up simultaneously.

## 3. Reliability & Risk Management

### 🚩 Dangerous "Fail-Open" Logic
- **Risk Gaps**: Almost all protective filters in `src/worker.py` (Daily Trade Limit, Spread Gate, Monthly/Weekly Loss limits, Circuit Breakers) are wrapped in broad `except Exception: pass` blocks.
- **Behavior**: If a check fails due to a network error or bug, the trade **proceeds anyway**. In a high-risk financial system, the default should be to "fail-closed" (block the trade).

### 🚩 Idempotency Race Conditions
- **Non-Atomic Checks**: The signal idempotency check (`_exists_trade_key`) happens before the signal is processed. Because the worker uses `ThreadPoolExecutor` to handle accounts in parallel, it is possible for two threads to pass the "exists" check for the same signal simultaneously.

### 🚩 "Shadow" Protection (AI Guardrails)
- **Trading Council**: The "Trading Council" (Protective AI Layer) runs in a background thread and does not block the main trade execution path. This means AI safety guards are effectively "shadow mode" only and cannot prevent a bad trade from being placed in real-time.

## 4. Technical Debt

### 🚩 Stale & Inconsistent Documentation
- **Inaccurate README**: The root `README.md` describes a project structure (`backend/`, `scripts/`) that does not exist in the current filesystem (`src/`, `config/`). It references non-existent files like `backend/trading_bot.py`.
- **Missing Infrastructure**: `AGENTS.md` and `Makefile` reference a `docker-compose.test.yml` which is missing from the repository.

### 🚩 Quality Gaps
- **Linting Fatigue**: The backend has 98 pre-existing `ruff` warnings. The frontend has several ESLint errors/warnings. This "broken window" effect makes it hard to identify new issues.
- **Failing Tests**: `tradingMetrics.test.ts` in the frontend is explicitly known to be failing.

### 🚩 Hardcoded Business Logic
- **Symbol Whitelist**: `PROFITABLE_SYMBOLS` is hardcoded directly inside `src/worker.py` instead of being managed via DB or configuration.
- **Hardcoded Pips**: Minimum SL/TP offsets for Forex/Indices are hardcoded in `config/settings.py`.

### 🚩 Logic Fragmentation
- **Pine Script Synchronization**: Much of the risk logic (R:R ratios, etc.) is handled on the TradingView side in Pine Script. If the Pine Script is changed without a corresponding update to the Python worker, the system may operate under incorrect risk assumptions.

### 🚩 Settings Cache Gotcha
- **`@lru_cache` on `get_settings()`**: Changes to `.env` values require a full backend process restart to take effect. This is documented in AGENTS.md but easy to miss during development.
