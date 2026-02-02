# Execution-Ready Work Plan

**Input context:** RiskEngine contract + rollout flags + exit spec; Execution layer design + Prompt 3.1 implementation plan; Key corrections: do not mark status active before submit success; LIVE exits close DB only on confirmed close; kill switch default `block_entries_only`.

**Goal:** Ticket list (8–12) + file-by-file checklist + phase mapping (A/B/C) + final decisions. No code implementation—plan only.

---

## A) Ticket List (9 tickets)

### Phase A: DRY_RUN + PAPER only (no network)

---

#### Ticket 1: Add execution-related columns to `trading_signals`

| Field                   | Value                                                                                                                                                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Add execution-related columns to `trading_signals`                                                                                                                                                                                                                        |
| **Scope**               | New nullable columns for execution lifecycle and broker ids. No code behavior change.                                                                                                                                                                                     |
| **Files touched**       | `scripts/sql/migrations/001_execution_columns.sql` (new), `backend/supabase_db.py`, `backend/config.py`                                                                                                                                                                   |
| **Acceptance criteria** | (1) `trading_signals` has columns: `execution_status`, `broker_order_id`, `submitted_at`, `filled_at` (optional), `last_error`, `close_broker_order_id`. (2) Existing rows unchanged (new cols NULL). (3) API and Worker start without errors. (4) Dashboards still work. |
| **Manual test steps**   | 1. Run migration in Supabase SQL Editor. 2. `uvicorn backend.main:app` and `python -m backend.worker`. 3. Send one entry webhook. 4. In Supabase, confirm new row has new columns NULL.                                                                                   |
| **Rollback**            | Revert migration (drop new columns or restore from backup). Revert changes in `backend/supabase_db.py` and `backend/config.py`.                                                                                                                                           |

---

#### Ticket 2: Add partial unique index on `trade_key` for active/pending rows

| Field                   | Value                                                                                                                                                                                                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Add partial unique index on `trade_key` for active/pending rows                                                                                                                                                                                                         |
| **Scope**               | One unique index so only one row per `trade_key` can be `pending` or `active`. Enforces idempotency at DB level.                                                                                                                                                        |
| **Files touched**       | `scripts/sql/migrations/002_unique_trade_key_active.sql` (new), optionally `scripts/sql/supabase_schema.sql` (comment only)                                                                                                                                             |
| **Acceptance criteria** | (1) Index exists: `UNIQUE (trade_key) WHERE status IN ('pending','active')`. (2) Insert of second row with same `trade_key` and status in that set fails with unique violation. (3) Rows with `status='closed'` or other values can share `trade_key` if schema allows. |
| **Manual test steps**   | 1. Run migration. 2. In SQL Editor, insert two rows with same `trade_key`, both `status='pending'`; second insert must fail. 3. Insert with `status='closed'` and same `trade_key` (if allowed by product rules) should succeed.                                        |
| **Rollback**            | `DROP INDEX IF EXISTS idx_unique_trade_key_active;` (or name used). Revert migration file.                                                                                                                                                                              |

---

#### Ticket 3: Execution interfaces and adapters (no wiring)

| Field                   | Value                                                                                                                                                                                                                                                                                         |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Create Execution Layer interfaces and adapter stubs                                                                                                                                                                                                                                           |
| **Scope**               | Define `OrderRequest`, `CloseRequest`, `ExecutionResult`, `ExecutionAdapter`; implement `DryRunAdapter`, `PaperAdapter`, `LiveAdapter` (stub), and `get_adapter()` router. No imports from worker/logic yet.                                                                                  |
| **Files touched**       | `backend/execution/__init__.py` (new), `backend/execution/interfaces.py` (new), `backend/execution/dry_run_adapter.py` (new), `backend/execution/paper_adapter.py` (new), `backend/execution/live_adapter.py` (new), `backend/execution/router.py` (new)                                      |
| **Acceptance criteria** | (1) All new modules exist and are importable. (2) Unit tests: DryRunAdapter returns `status="submitted"`, message `"DRY_RUN"`. (3) Unit tests: PaperAdapter wraps `PaperTrader.open_position` / `close_position` and returns `ExecutionResult`. (4) No runtime behavior change in API/Worker. |
| **Manual test steps**   | Run unit tests only. No webhook/DB checks.                                                                                                                                                                                                                                                    |
| **Rollback**            | `git revert <commit>` or delete `backend/execution/` directory.                                                                                                                                                                                                                               |

---

#### Ticket 4: Wire DryRunAdapter and pending→active lifecycle for entries

| Field                   | Value                                                                                                                                                                                                                                                                                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Integrate DryRunAdapter for entries and enforce pending→active only after submit success                                                                                                                                                                                                                                                        |
| **Scope**               | `save_alert` sets `status='pending'`, `execution_status='pending'`. After `adapter.submit_order` success → set `status='active'`, `execution_status='active'`; on failure → `status='execution_failed'`, `execution_status='execution_failed'`, `last_error`. For RUN_MODE=DRY_RUN use DryRunAdapter; do not mark active before submit success. |
| **Files touched**       | `backend/logic.py`, `backend/supabase_db.py`, `backend/config.py`                                                                                                                                                                                                                                                                               |
| **Acceptance criteria** | (1) RUN_MODE=DRY_RUN: new rows inserted with `status='pending'`, `execution_status='pending'`. (2) After DryRunAdapter.submit_order (always success): row updated to `status='active'`, `execution_status='active'`. (3) No paper/live orders. (4) Logs show DryRunAdapter activity.                                                            |
| **Manual test steps**   | 1. Set `RUN_MODE=DRY_RUN` in `.env`. 2. Start API + Worker. 3. Send entry webhook. 4. DB: row has `pending` then `active` and `execution_status='active'`. 5. Logs contain DryRunAdapter messages.                                                                                                                                              |
| **Rollback**            | `git revert <commit>`. Optionally set env to previous behavior if any fallback flag exists.                                                                                                                                                                                                                                                     |

---

#### Ticket 5: Wire PaperAdapter for entry execution

| Field                   | Value                                                                                                                                                                                                                      |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Integrate PaperAdapter for entry execution                                                                                                                                                                                 |
| **Scope**               | When RUN_MODE=PAPER (and paper enabled), use PaperAdapter instead of direct `PaperTrader.open_position`. Entry path: save_alert (pending) → adapter.submit_order → on success set active; on failure set execution_failed. |
| **Files touched**       | `backend/logic.py`, `backend/worker.py` (pass run_mode/adapter if needed)                                                                                                                                                  |
| **Acceptance criteria** | (1) RUN_MODE=PAPER: paper positions created via PaperAdapter. (2) DB lifecycle: pending → active on success. (3) Behavior matches previous paper trading (same positions and DB outcome).                                  |
| **Manual test steps**   | 1. Set `RUN_MODE=PAPER`, `PAPER_TRADING_ENABLED=true`. 2. Start API + Worker. 3. Send entry webhook. 4. DB: row pending → active. 5. PaperTrader has open position.                                                        |
| **Rollback**            | `git revert <commit>`.                                                                                                                                                                                                     |

---

#### Ticket 6: Enable exit processing and wire PaperAdapter for exits (DB closed only on confirmed close)

| Field                   | Value                                                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Enable exit processing and close DB only on confirmed close                                                                                                                                                                                                                                                                                                                                                      |
| **Scope**               | Worker routes `event_type=exit` to exit handler. Handler resolves active row by trade_key (or zone_id); calls adapter.close_order; **only on success** calls `update_alert_exit` to set `status='closed'`, `execution_status='closed'`. On failure: keep `status='active'`, set `last_error`. `update_alert_exit` must filter by `status='active'`. No_match/duplicate: log only (no analytics rows).            |
| **Files touched**       | `backend/worker.py`, `backend/logic.py` (or `backend/execution/exit_handler.py` new), `backend/supabase_db.py`, `backend/config.py`                                                                                                                                                                                                                                                                              |
| **Acceptance criteria** | (1) EXIT_PROCESSING_ENABLED=true, PAPER: entry then exit for same trade_key → row goes active→closed, paper position closed. (2) Duplicate exit (already closed) → no DB update, no double close_order; logged. (3) Exit before entry (no match) → logged, no row created. (4) Two entries, one exit: exit closes correct row by trade_key. (5) LIVE semantics: DB marked closed only when close_order succeeds. |
| **Manual test steps**   | 1. Set EXIT_PROCESSING_ENABLED=true, RUN_MODE=PAPER. 2. Entry webhook (e.g. trade_key TK-S1). 3. Exit webhook (TK-S1) → row closed, paper closed. 4. Send same exit again → row still closed, log "duplicate ignored". 5. Send exit (TK-S3) then entry (TK-S3) → entry becomes active; first exit logged no-match.                                                                                               |
| **Rollback**            | Set `EXIT_PROCESSING_ENABLED=false`; revert commit.                                                                                                                                                                                                                                                                                                                                                              |

---

### Phase B: LIVE shadow mode (still no network)

---

#### Ticket 7: LiveAdapter shadow mode

| Field                   | Value                                                                                                                                                                                                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Title**               | Implement and wire LiveAdapter in shadow mode                                                                                                                                                                                                                      |
| **Scope**               | LiveAdapter when LIVE_SHADOW=true: log order/close payloads, return ExecutionResult(status="submitted", message="LIVE_SHADOW"). No broker API calls. Router returns LiveAdapter when RUN_MODE=LIVE and LIVE_TRADING_ENABLED=true and LIVE_SHADOW=true.             |
| **Files touched**       | `backend/execution/live_adapter.py`, `backend/execution/router.py`, `backend/config.py`                                                                                                                                                                            |
| **Acceptance criteria** | (1) RUN_MODE=LIVE, LIVE_TRADING_ENABLED=true, LIVE_SHADOW=true: entry → pending→active, broker_order_id NULL, logs show "would submit" and payload. (2) Exit → active→closed, close_broker_order_id NULL, logs show "would close". (3) No network calls to broker. |
| **Manual test steps**   | 1. Set RUN_MODE=LIVE, LIVE_TRADING_ENABLED=true, LIVE_SHADOW=true (optional dummy broker env). 2. Entry webhook → DB pending→active, logs shadow submit. 3. Exit webhook → DB closed, logs shadow close.                                                           |
| **Rollback**            | Set RUN_MODE=DRY_RUN or LIVE_SHADOW=true with LIVE_TRADING_ENABLED=false; revert commit.                                                                                                                                                                           |

---

### Phase C: LIVE real (network), gated

---

#### Ticket 8: Real LiveAdapter and safety gates (1 symbol, max size, kill switch default block_entries_only)

| Field                   | Value                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Title**               | Implement live broker adapter with gates and kill switch default                                                                                                                                                                                                                                                                                                                           |
| **Scope**               | LiveAdapter when LIVE_SHADOW=false: real broker API (e.g. MetaAPI). Router: enforce ALLOWED_LIVE_SYMBOLS, MAX_LIVE_SIZE; if not met, downgrade to dry-run or reject. KILL_SWITCH_MODE default `block_entries_only`: when kill switch ON, block new entries only; exits still allowed. Optional `block_all` for full freeze.                                                                |
| **Files touched**       | `backend/requirements.txt`, `backend/execution/live_adapter.py`, `backend/execution/router.py`, `backend/config.py`, `backend/worker.py` (or risk layer)                                                                                                                                                                                                                                   |
| **Acceptance criteria** | (1) RUN_MODE=LIVE, LIVE_SHADOW=false, allowed symbol/size: real order placed, DB has broker_order_id, submitted_at. (2) Exit: real close, DB closed, close_broker_order_id set. (3) Disallowed symbol/size → blocked or dry-run. (4) KILL_SWITCH_MODE=block_entries_only and kill ON → entries blocked, exits processed. (5) LIVE_TRADING_ENABLED=false or missing creds → no live orders. |
| **Manual test steps**   | **CAUTION: REAL MONEY.** 1. Use one allowed symbol and tiny MAX_LIVE_SIZE (e.g. 0.01). 2. Set RUN_MODE=LIVE, LIVE_SHADOW=false, broker creds. 3. Entry → real order, DB updated. 4. Exit → real close, DB closed. 5. Entry for disallowed symbol → blocked. 6. Enable kill switch, block_entries_only → new entry blocked, existing exit still closes.                                     |
| **Rollback**            | Set LIVE_TRADING_ENABLED=false and restart worker immediately; git revert.                                                                                                                                                                                                                                                                                                                 |

---

#### Ticket 9 (optional): Wire RiskEngine.evaluate() in worker (feature-flagged)

| Field                   | Value                                                                                                                                                                                                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Title**               | Integrate RiskEngine in worker with rollout flags                                                                                                                                                                                                                                                   |
| **Scope**               | When USE_RISK_ENGINE=true, worker calls RiskEngine.evaluate(signal, state_snapshot) and uses result (accepted, reason_code, computed_size, risk_metrics, flags). Replace or wrap existing inline guards so one path uses RiskEngine. Shadow mode can write to guard_decisions table for comparison. |
| **Files touched**       | `backend/worker.py`, `backend/risk_engine.py` (or risk module), `backend/config.py`, optionally `backend/supabase_db.py` (guard_decisions table)                                                                                                                                                    |
| **Acceptance criteria** | (1) USE_RISK_ENGINE=false: behavior unchanged. (2) USE_RISK_ENGINE=true: accept/reject and size come from RiskEngine; logs or guard_decisions show reason_code. (3) No regression on DRY_RUN/PAPER flows.                                                                                           |
| **Manual test steps**   | 1. USE_RISK_ENGINE=false → replay, same outcomes. 2. USE_RISK_ENGINE=true → replay, decisions logged or stored; accepted trades execute as before.                                                                                                                                                  |
| **Rollback**            | Set USE_RISK_ENGINE=false; revert commit.                                                                                                                                                                                                                                                           |

---

## B) File-by-file checklist per ticket

### Ticket 1: Schema columns

| File                                               | Change                                                                                                                                                                      |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/sql/migrations/001_execution_columns.sql` | New file. `ALTER TABLE trading_signals ADD COLUMN execution_status TEXT;` (and broker_order_id, submitted_at, filled_at, last_error, close_broker_order_id). Defaults NULL. |
| `backend/supabase_db.py`                           | In `save_alert` (later ticket) and any insert/update helpers: add type hints or comments for new columns. No logic change in this ticket.                                   |
| `backend/config.py`                                | Add `execution_status_null_is_legacy: bool = True` (treat NULL as legacy row).                                                                                              |

---

### Ticket 2: Partial unique index

| File                                                     | Change                                                                                                                           |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/sql/migrations/002_unique_trade_key_active.sql` | New file. `CREATE UNIQUE INDEX idx_unique_trade_key_active ON trading_signals (trade_key) WHERE status IN ('pending','active');` |

---

### Ticket 3: Execution interfaces and adapters

| File                                   | Change                                                                                                                     |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `backend/execution/__init__.py`        | New. Export interfaces and router.                                                                                         |
| `backend/execution/interfaces.py`      | New. Define `OrderRequest`, `CloseRequest`, `ExecutionResult`, `ExecutionAdapter` (Protocol): submit_order, close_order.   |
| `backend/execution/dry_run_adapter.py` | New. DryRunAdapter: submit_order → log, return submitted/DRY_RUN; close_order → same.                                      |
| `backend/execution/paper_adapter.py`   | New. PaperAdapter(paper_trader): submit_order → open_position, return result; close_order → close_position, return result. |
| `backend/execution/live_adapter.py`    | New. LiveAdapter stub: submit_order/close_order → log LIVE_SHADOW, return submitted.                                       |
| `backend/execution/router.py`          | New. get_adapter(run_mode, settings, paper_trader) → return appropriate adapter by RUN_MODE and flags.                     |

---

### Ticket 4: DryRunAdapter + lifecycle

| File                     | Change                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/supabase_db.py` | save_alert: set `status='pending'`, `execution_status='pending'` in insert_data. Add update_execution_status(alert_id, status, execution_status, broker_order_id, submitted_at, last_error) to update row after execution.                                                                                                                                 |
| `backend/logic.py`       | process_trade (entry branch): get adapter via router for RUN_MODE=DRY_RUN; after save_alert, call \_handle_entry_execution(alert_id, data, computed_size, run_mode, adapter, db). \_handle_entry_execution: build OrderRequest, adapter.submit_order; on success update status/execution_status to active; on failure set execution_failed and last_error. |
| `backend/config.py`      | Add RUN_MODE (or use existing live_trading_enabled to derive DRY_RUN). Add DRY_RUN_ROW_STATUS if needed (recommended: use pending→active).                                                                                                                                                                                                                 |

---

### Ticket 5: PaperAdapter entries

| File                | Change                                                                                                                                                                                                     |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/logic.py`  | In process_trade entry path: when mode=paper, get PaperAdapter from router; use \_handle_entry_execution with PaperAdapter instead of direct pt.open_position. Remove direct open_position call for paper. |
| `backend/worker.py` | Ensure run_mode/mode and paper_trader are available where get_adapter is called (e.g. pass settings and paper_trader into logic or resolve inside logic).                                                  |

---

### Ticket 6: Exit processing (DB closed only on confirmed close)

| File                                                      | Change                                                                                                                                                                                                                                                                                                                                                                                           |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `backend/worker.py`                                       | Remove "if event_type==exit: continue". When EXIT_PROCESSING_ENABLED and event_type==exit, call exit handler (e.g. handle_exit(payload, settings, adapter, db)).                                                                                                                                                                                                                                 |
| `backend/logic.py` or `backend/execution/exit_handler.py` | handle_exit(exit_payload, settings, adapter, db): get active row by trade_key (get_active_alert_by_trade_key) or zone_id; if none, log no_match and return. Build CloseRequest, adapter.close_order. On success: db.update_alert_exit (sets status=closed, execution_status=closed). On failure: keep status=active, set last_error. Duplicate exit (row already closed): skip close_order, log. |
| `backend/supabase_db.py`                                  | get_active_alert_by_trade_key(trade_key): select where trade_key and status='active'. get_active_alert_by_zone_id(zone_id): same for zone_id. update_alert_exit: add .eq('status','active') to update so only active rows can be closed (and avoid overwriting already-closed rows).                                                                                                             |
| `backend/config.py`                                       | EXIT_PROCESSING_ENABLED: bool = True.                                                                                                                                                                                                                                                                                                                                                            |

---

### Ticket 7: LiveAdapter shadow

| File                                | Change                                                                                                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/execution/live_adapter.py` | submit_order: if LIVE_SHADOW, log full request, return ExecutionResult(submitted, message=LIVE_SHADOW). close_order: same. Accept settings in constructor. |
| `backend/execution/router.py`       | When RUN_MODE=LIVE and LIVE_TRADING_ENABLED=true, return LiveAdapter(settings).                                                                            |
| `backend/config.py`                 | LIVE_SHADOW: bool = True. METAAPI_TOKEN, METAAPI_ACCOUNT_ID placeholders (optional for shadow).                                                            |

---

### Ticket 8: Real LiveAdapter + gates

| File                                | Change                                                                                                                                                                                     |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `backend/requirements.txt`          | Add metaapi-cloud-sdk (or chosen broker SDK).                                                                                                                                              |
| `backend/execution/live_adapter.py` | When LIVE_SHADOW=false, call real broker API (submit_order → create_order, close_order → close_position). Map broker response to ExecutionResult, set broker_order_id.                     |
| `backend/execution/router.py`       | If LIVE_SHADOW=false, check ALLOWED_LIVE_SYMBOLS and MAX_LIVE_SIZE; if symbol/size not allowed, return DryRunAdapter or reject.                                                            |
| `backend/config.py`                 | LIVE_SHADOW default False for production. KILL_SWITCH_MODE: Literal["block_entries_only","block_all"] = "block_entries_only". ALLOWED_LIVE_SYMBOLS (comma-sep), MAX_LIVE_SIZE.             |
| `backend/worker.py`                 | Before calling entry execution: if trading_kill_switch and KILL_SWITCH_MODE=block_entries_only, skip submit (save as kill_switch_blocked or skip); if block_all, skip both entry and exit. |

---

### Ticket 9: RiskEngine wiring

| File                              | Change                                                                                                                                                                                                                              |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/worker.py`               | If USE_RISK_ENGINE: build Signal and StateSnapshot from payload/DB, call RiskEngine.evaluate(); use result.accepted, result.computed_size, result.reason_code; optionally write to guard_decisions. Else: keep current guard logic. |
| `backend/risk_engine.py` (or new) | RiskEngine.evaluate(signal, state_snapshot) → RiskEngineResult. Implement using existing guardians (risk_guardian, pine_guardian, etc.) per RiskEngine blueprint.                                                                   |
| `backend/config.py`               | USE_RISK_ENGINE: bool = False. LOG_GUARD_DETAILS, etc.                                                                                                                                                                              |

---

## C) Phase mapping (A / B / C)

| Phase | Description                                         | Tickets                        |
| ----- | --------------------------------------------------- | ------------------------------ |
| **A** | DRY_RUN + PAPER only (no network)                   | 1, 2, 3, 4, 5, 6 (optional: 9) |
| **B** | LIVE shadow mode (still no network)                 | 7                              |
| **C** | LIVE real (network), gated to 1 symbol and max size | 8                              |

- **Phase A** can be deployed and tested end-to-end with DRY_RUN and PAPER; no broker or network.
- **Phase B** validates LIVE path and logging without sending orders.
- **Phase C** requires broker credentials and strict gates (ALLOWED_LIVE_SYMBOLS, MAX_LIVE_SIZE, kill switch default block_entries_only).

---

## D) Final decisions checklist (recommended defaults)

| Decision                               | Option A                                                            | Option B                                                               | Recommended              | Notes                                                                        |
| -------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------- |
| **DRY_RUN row status**                 | Keep rows as `pending` only (never set active)                      | Use full lifecycle `pending` → `active` after “virtual” submit         | **Option B**             | Consistent semantics across RUN_MODE; dashboards filter status the same way. |
| **Partial unique index for trade_key** | No index                                                            | Unique partial index on trade_key WHERE status IN ('pending','active') | **Partial unique index** | Prevents duplicate active/pending rows per trade_key; supports idempotency.  |
| **Exit no_match / duplicate**          | Create analytics rows (e.g. exit_received_no_match, duplicate_exit) | Log only (WARNING), no extra DB rows                                   | **Log only**             | Keeps trading_signals for real lifecycles; use logs/metrics for analytics.   |

- **Status semantics (reminder):** Do not mark status active before submit success. LIVE exits: close DB only on confirmed close_order success; on failure keep status=active and set last_error.
- **Kill switch default:** `KILL_SWITCH_MODE=block_entries_only` (entries blocked when ON; exits still allowed).

---

## Quick reference: key paths

- **Migration SQL:** `scripts/sql/migrations/001_execution_columns.sql`, `002_unique_trade_key_active.sql`
- **Execution module:** `backend/execution/` (interfaces, dry_run_adapter, paper_adapter, live_adapter, router)
- **Entry wiring:** `backend/logic.py` (`process_trade`, `_handle_entry_execution`)
- **Exit wiring:** `backend/worker.py` (route exit to handler), `backend/logic.py` or `backend/execution/exit_handler.py` (`handle_exit`)
- **DB:** `backend/supabase_db.py` (`save_alert`, `update_alert_exit`, `update_execution_status`, `get_active_alert_by_trade_key`)
- **Config:** `backend/config.py` (RUN_MODE, LIVE_SHADOW, EXIT_PROCESSING_ENABLED, KILL_SWITCH_MODE, etc.)
