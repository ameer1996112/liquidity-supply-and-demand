Sprint 6.3 – Production Gate Checklist
======================================

Purpose
-------

This checklist defines the **release gates** that must pass before enabling
**LIVE execution** for the Trinity Trading Bot (MetaAPI / real broker mode).

It is intentionally conservative. All items should be treated as **must‑have**
for production, not best‑effort.


1. Core infrastructure healthy
------------------------------

- **Backend API**
  - `/` health endpoint returns 200.
  - `/admin/health` shows green for:
    - API process
    - Worker process heartbeat
    - Supabase connectivity
    - Redis connectivity

- **Redis**
  - Single Redis instance reachable from API and worker.
  - `REDIS_URL` configured in `.env` and matches deployment.
  - Latency is stable (no frequent timeouts in logs).

- **Supabase**
  - Database migrations applied up to and including:
    - `037_signal_actions.sql`
  - `trading_signals` table reachable; basic SELECT works from deployed app.

- **MetaAPI / Broker**
  - `META_API_TOKEN`, `META_API_ACCOUNT_ID` set in `.env` (for LIVE).
  - Test account is funded and can place **small** orders.


2. Configuration sanity
-----------------------

- **Environment**
  - `run_mode=LIVE` only in the live deployment environment.
  - `live_trading_enabled=true` set **only** on the live backend.
  - `AI_FILTER_ENABLED`, `ML_GUARDIAN_ENABLED`, `TRINITY_ENABLED` configured
    according to risk appetite; default is **ON** for production.

- **Risk**
  - `account_balance` and `risk_percent` in `.env` match the actual account.
  - `max_lot_size` is set to a conservative value for the broker.
  - Per‑account kill switch Redis keys (`trading:kill_switch:*`) verified OFF
    before go‑live.

- **Webhooks**
  - `WEBHOOK_SECRET` set and matches TradingView alert configuration.
  - TradingView strategy sends both **entry** and **exit** webhooks
    (`event_type: "entry" | "exit"`).


3. Test suite gates
-------------------

All tests are run from the project root with `PYTHONPATH=/workspace` (or the
equivalent in CI).

- **Unit + integration tests**
  - `pytest tests -v --tb=short --ignore=tests/test_sprint55_reliability.py`
  - Must complete with **0 failures**.

- **Chaos / reliability tests**
  - `pytest tests/test_sprint55_reliability.py -v --tb=short`
  - Confirms:
    - Redis transport reset semantics (simulated Redis restart mid‑run).
    - MetaApi adapter retry behaviour on temporary failures
      (timeouts / connection errors then recovery).
    - Worker idempotency on duplicate `trade_key` (duplicate webhook /
      crash + replay).
    - Worker queue resilience: crash after first message, restart drains
      remaining messages without duplicates.
    - Invariants:
      - No double order placement for same `client_order_id` / `trade_key`.
      - No `ACTIVE` / `OPEN` position without broker confirmation
        (`broker_order_id` present).
      - Every guard/reject path records a reason string and audit hook.

- **Optional – full suite**
  - `pytest tests -v` for a full run before major releases.


4. Observability & logging
--------------------------

- **Trade events**
  - `trade_events` / audit tables in Supabase are receiving events from:
    - Worker guards (symbol whitelist, size/max-lot, futures model, account guards).
    - Logic execution (`execution_started`, `execution_filled`, `execution_failed`).

- **Dashboards**
  - Frontend dashboard shows:
    - Recent signals stream updating.
    - Open trades panel populated for PAPER/PREVIEW runs.
    - Risk / kill‑switch status correct.

- **Alerts**
  - Discord / Telegram webhooks (if configured) receive at least one
    PAPER test trade notification.
  - No persistent ERROR‑level spam in logs (e.g. repeated Redis/MetaAPI
    connection errors).


5. Dry‑run validation (PAPER mode)
----------------------------------

Before enabling LIVE execution, run at least **one full trading session**
in **PAPER** mode with production‑like settings:

- TradingView strategy enabled with small size and same symbol universe.
- Backend `run_mode=PAPER`, `live_trading_enabled=false`.
- Verify for multiple trades:
  - Signals arrive and are stored in `trading_signals`.
  - Guards behave as expected (reject low‑quality / oversized trades).
  - PAPER trades open and close correctly, with PnL recorded.
  - No unexpected rejects without clear reasons in the UI.


6. Live switch procedure
------------------------

When all preceding gates pass:

1. **Freeze changes**
   - Merge window closed; only hotfixes allowed.

2. **Enable LIVE execution**
   - Set `run_mode=LIVE` and `live_trading_enabled=true` in the **live** env.
   - Confirm environment reload / deployment succeeded.

3. **Smoke test with minimal risk**
   - Use smallest allowed lot size and conservative `risk_percent`.
   - Trigger a single LIVE test trade from TradingView.
   - Confirm:
     - Signal recorded in `trading_signals` with correct metadata.
     - Broker position opened with matching `client_order_id` / `trade_key`.
     - UI shows trade as ACTIVE / OPEN only after broker confirmation.

4. **Monitor**
   - For the first 24–48 hours:
     - Watch Redis, API, worker logs.
     - Verify no duplicate executions for the same signal.
     - Confirm exits (TP/SL/manual) correctly close positions and update PnL.


7. Emergency rollback
---------------------

Define and document a **rollback plan** before enabling LIVE:

- How to immediately disable live execution:
  - Set `live_trading_enabled=false` and/or `run_mode=PAPER`.
  - Engage per‑account kill switch via API or direct Redis key:
    - `trading:kill_switch` or `trading:kill_switch:{account_name}`.

- How to verify rollback:
  - Confirm no new trades are opened after rollback.
  - Frontend reflects kill‑switch / mode status.


If any gate in this document fails, **do not** enable LIVE trading until the
issue is understood, fixed, and re‑validated through the same checklist.

