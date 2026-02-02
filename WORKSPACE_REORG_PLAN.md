# Workspace Reorganization Plan (PLAN ONLY — DO NOT APPLY YET)

**Goal:** Reorganize the repo to reduce clutter without breaking runtime behavior, imports, or deployment. Small, reversible changes only. No logic/behavior changes except where required to preserve imports after moves.

**Constraints:** No big rewrite; keep all entrypoints working; idempotency and behavior unchanged; use `git mv` for moves; do not delete code (archive unused/legacy); add compatibility shims at old paths if a move would break external imports.

---

## 1) Inventory & runtime map

### 1.1 Runtime-critical files and how the app runs

| Role                           | File(s)                         | How it runs                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------ | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Entrypoint (local/Railway)** | `start.sh`                      | Sets `PYTHONPATH=$ROOT_DIR`, runs `uvicorn backend.main:app`, then `python -m backend.worker`. Requires `backend` package at repo root.                                                                                                                                                                                                                       |
| **API**                        | `backend/main.py`               | FastAPI app; validates webhook → pushes to Redis → 200. Imports: `backend.config.get_settings`, `get_redis` (local).                                                                                                                                                                                                                                          |
| **Worker**                     | `backend/worker.py`             | Redis BLPOP loop; guards → `logic.process_trade` or `save_result`. Imports: `backend.config` (lazy), `backend.logic` (dynamic), supabase/redis/pandas/pickle (local).                                                                                                                                                                                         |
| **Config**                     | `backend/config.py`             | Pydantic Settings; required by main, worker, logic, execution router, guardians.                                                                                                                                                                                                                                                                              |
| **Docker Compose**             | `docker-compose.yml`            | Builds `backend/Dockerfile.api`, `backend/Dockerfile.worker`; context `./backend`, copies **flat** files into image (`config.py`, `main.py`, `logic.py`, `paper_trader.py`, `supabase_db.py`, `worker.py`, `news_filter.py`). In container there is **no** `backend` package; CMD runs `uvicorn main:app` and `python worker.py` (so `import logic` is used). |
| **Railway**                    | `railway.json`, `nixpacks.toml` | Deploy uses `./start.sh` from repo root (not Docker); so Railway runs with `backend` package layout.                                                                                                                                                                                                                                                          |

**Env (critical):** `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY`; optional: `WEBHOOK_SECRET`, `PAPER_*`, `LIVE_TRADING`, etc. Loaded via `backend/config` (Pydantic) and worker `load_dotenv(backend/.env)`.

### 1.2 Active path (worker → logic → supabase → paper_trader)

| Step | Module                    | Usage                                                                                                                                                                                                                         |
| ---- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `backend/worker.py`       | Inline guards (kill-switch, idempotency, risk size, correlation count, ML prediction); then `logic.process_trade(payload, dry_run)` or `save_result(...)`. Own Supabase client for guards and save_result.                    |
| 2    | `backend/logic.py`        | `process_trade`: entry → `should_forward_alert` → `db.save_alert` (lazy `backend.supabase_db`) → optional `pt.open_position` (lazy `backend.paper_trader.get_paper_trader`), Discord/Telegram. Exit → `db.update_alert_exit`. |
| 3    | `backend/supabase_db.py`  | `save_alert`, `update_alert_status`, `update_alert_exit`, etc. Used by logic (lazy) and by `daily_report` (`from backend import supabase_db`).                                                                                |
| 4    | `backend/paper_trader.py` | `open_position`, `close_position`, `get_paper_trader(None)`. Used by logic only (lazy).                                                                                                                                       |

**Not on hot path today:** `backend/execution/*` (no imports from logic/worker yet). Guardians (`risk_guardian`, `correlation_manager`, `pine_guardian`, `ai_guardian`, `ml_guardian`, `market_adapter`) are **not** imported by worker; worker has inline guards. Guardians are used by tests and by `create_*_from_settings()` helpers.

### 1.3 Legacy / unused or script-only code

| Location                                                  | Description                                                                                                                 |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `_archive/20260131_113613/`                               | Old snapshot: `trading_bot.py`, `test_bot.py`, `test_news_logic.py`. Already archived.                                      |
| `backend/Procfile`                                        | `web: python trading_bot.py` — legacy; Railway uses `start.sh`, not this.                                                   |
| `backend/start_bot.sh`, `backend/start_api_and_worker.sh` | Shell helpers; may duplicate start.sh or old workflow.                                                                      |
| `backend/backtest_ai_filter.py`                           | Backtest/ML script; not used by API/worker.                                                                                 |
| `backend/convert_notion_data.py`                          | Notion → CSV for ML pipeline; not used by API/worker.                                                                       |
| `backend/reclassify_imported.py`                          | Reclassify imported data; CLI script.                                                                                       |
| `backend/train_model.py`                                  | Train ML model; standalone script.                                                                                          |
| `backend/migrate_database.py`                             | SQLite migration; standalone.                                                                                               |
| `backend/monitor_shadow_mode.py`                          | Uses `import supabase_db` (run from `backend/` dir).                                                                        |
| `backend/export_training_data.py`                         | Uses `import supabase_db` (run from `backend/` dir).                                                                        |
| `backend/daily_report.py`                                 | Uses `from backend import supabase_db`; run from repo root.                                                                 |
| `backend/scripts/`                                        | `analyze_all_pairs.py`, `combine_all_data.py`, `prepare_enhanced_training.py`, `train_enhanced_model.py` — ML/data scripts. |
| `scripts/` (root)                                         | Test/verify scripts: `simulate_tv_event.py`, `test_*.py`, `run_test_suite.sh`, etc.                                         |

---

## 2) Target folder structure (minimal)

Keep layout recognizable; only add structure where it clearly reduces clutter.

```
(unchanged)
├── start.sh
├── docker-compose.yml
├── Makefile
├── pytest.ini
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── worker.py
│   ├── logic.py
│   ├── supabase_db.py
│   ├── paper_trader.py
│   ├── news_filter.py
│   ├── execution/           # already exists
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── requirements.txt
│   ├── Procfile
│   ├── .env.example
│   └── ...
├── tests/
├── scripts/
├── docs/
├── _archive/
└── ...
```

**Optional, low-clutter additions (only if you do moves):**

- **docs/** — Already exists. Move root-level design/operational docs here (see Move Plan).
- **\_archive/** — Already exists. Move clearly legacy scripts here (timestamped or `legacy/`) so they remain runnable but out of the way.
- **backend/guards/** — **Not recommended in phase 1.** Would group risk_guardian, correlation_manager, pine_guardian, ai_guardian, ml_guardian, market_adapter. Requires shims at `backend/risk_guardian.py` etc. and Docker/test updates; higher risk.

**Do not introduce** `backend/state/` or `backend/core/` unless you are ready to update Dockerfiles (flat COPY list) and all `backend.*` imports.

---

## 3) Move Plan table

Only moves that are **reversible** and **low/medium risk**. Use `git mv` for each.

| #   | From                              | To                                                | Why                                                         | Risk | Shim at old path? | Import updates? |
| --- | --------------------------------- | ------------------------------------------------- | ----------------------------------------------------------- | ---- | ----------------- | --------------- |
| 1   | `EXECUTION_WORK_PLAN.md`          | `docs/EXECUTION_WORK_PLAN.md`                     | Consolidate design docs in docs/                            | Low  | No                | No (doc only)   |
| 2   | `RISK_MANAGEMENT_UPDATE.md`       | `docs/RISK_MANAGEMENT_UPDATE.md`                  | Same                                                        | Low  | No                | No              |
| 3   | `AUDIT_REPORT.md`                 | `docs/AUDIT_REPORT.md`                            | Same                                                        | Low  | No                | No              |
| 4   | `DEPLOYMENT_GUIDE.md`             | `docs/DEPLOYMENT_GUIDE.md`                        | Same                                                        | Low  | No                | No              |
| 5   | `RAILWAY_SETUP.md`                | `docs/RAILWAY_SETUP.md`                           | Same                                                        | Low  | No                | No              |
| 6   | `TESTING_GUIDE.md`                | `docs/TESTING_GUIDE.md`                           | Same                                                        | Low  | No                | No              |
| 7   | `TESTING.md`                      | `docs/TESTING.md`                                 | Same                                                        | Low  | No                | No              |
| 8   | `QUICK_REFERENCE.md`              | `docs/QUICK_REFERENCE.md`                         | Same                                                        | Low  | No                | No              |
| 9   | `QUICKSTART.md`                   | `docs/QUICKSTART.md`                              | Same                                                        | Low  | No                | No              |
| 10  | `backend/Procfile`                | `_archive/legacy/backend_Procfile`                | Procfile references removed trading_bot; keep for reference | Low  | No                | No              |
| 11  | `backend/start_bot.sh`            | `_archive/legacy/backend_start_bot.sh`            | Legacy; start.sh is canonical                               | Low  | No                | No              |
| 12  | `backend/start_api_and_worker.sh` | `_archive/legacy/backend_start_api_and_worker.sh` | Same                                                        | Low  | No                | No              |

**Explicitly do NOT move in this plan:**

- Any of: `backend/main.py`, `backend/worker.py`, `backend/logic.py`, `backend/config.py`, `backend/supabase_db.py`, `backend/paper_trader.py`, `backend/news_filter.py` — **do not touch.** Moving them would break Docker (flat COPY) and/or `backend.*` and `import logic` paths.
- `backend/execution/` — Already in place; no move.
- Guardian modules (`risk_guardian`, `correlation_manager`, `pine_guardian`, `ai_guardian`, `ml_guardian`, `market_adapter`) — Moving to `backend/guards/` would require shims and test/Docker updates; **omit from phase 1.**
- `backend/monitor_shadow_mode.py`, `backend/export_training_data.py` — Use `import supabase_db` (run from backend/). Moving would require changing to `from backend import supabase_db` and running from repo root; **optional later**, not in table.
- `README.md` — Keep at root (repo front door).

---

## 4) Safety checklist

### 4.1 Before applying any move

- [ ] From repo root: `pytest tests/unit -v -m unit --tb=short` → all pass.
- [ ] From repo root: `./scripts/run_test_suite.sh` (or `make test-ci`) → unit + integration + e2e pass (if Redis available).
- [ ] From repo root: `python -c "from backend.config import get_settings; from backend.main import app; from backend import logic; print('OK')"` → no import errors.
- [ ] Note current git state: `git status`, `git rev-parse HEAD`.

### 4.2 After each move (or batch of doc moves)

- [ ] `pytest tests/unit -v -m unit --tb=short` → all pass.
- [ ] `python -c "from backend.config import get_settings; from backend.main import app; from backend import logic; print('OK')"` → OK.
- [ ] If you moved only docs (no Python): no import updates needed. If you moved scripts to \_archive: no production code should import them; tests still pass.

### 4.3 Smoke run (after all moves)

- [ ] `./start.sh` (or equivalent): start API + worker; leave running a few seconds.
- [ ] Logs show: `[start.sh] Import check: OK`, API listening, worker "WORKER ... STARTED".
- [ ] Optional: send one webhook to `/webhook` (e.g. with `scripts/simulate_tv_event.py`); expect 200 and one row in `trading_signals` if Supabase is configured.
- [ ] Docker (optional): `docker compose build api worker` then `docker compose up -d`; same checks. **Note:** Docker uses flat backend files; this plan does not change those files, so Docker should be unchanged.

### 4.4 Supabase (if applicable)

- This plan does not change DB writes. If you run a webhook after moves: same columns and behavior as before (save_alert, update_alert_exit, etc.).

### 4.5 Rollback

- **Per move:** `git revert <commit>` or `git mv <To> <From>` and commit.
- **Full rollback:** `git revert --no-commit <range>` or `git checkout <previous_HEAD> -- .` then re-run tests and smoke.

---

## 5) “Do not touch” list

Do **not** move, rename, or refactor these in this reorg:

| File / path                                                                                                                                                               | Reason                                                                                                                               |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `start.sh`                                                                                                                                                                | Entrypoint for local and Railway; sets PYTHONPATH and starts API + worker.                                                           |
| `backend/main.py`                                                                                                                                                         | FastAPI app; Docker CMD and tests use `backend.main` or `main:app`.                                                                  |
| `backend/worker.py`                                                                                                                                                       | Worker entrypoint; Docker and tests depend on it.                                                                                    |
| `backend/logic.py`                                                                                                                                                        | Hot path; worker and tests import `backend.logic` or `logic`.                                                                        |
| `backend/config.py`                                                                                                                                                       | Used by main, worker, logic, execution, guardians.                                                                                   |
| `backend/supabase_db.py`                                                                                                                                                  | Hot path; logic and daily_report import it.                                                                                          |
| `backend/paper_trader.py`                                                                                                                                                 | Hot path; logic uses get_paper_trader.                                                                                               |
| `backend/news_filter.py`                                                                                                                                                  | Copied by Dockerfile.worker; logic may use later.                                                                                    |
| `backend/execution/*`                                                                                                                                                     | New layer; already structured; no move.                                                                                              |
| `backend/Dockerfile.api`, `backend/Dockerfile.worker`                                                                                                                     | Define COPY list; changing structure would require full backend tree COPY and PYTHONPATH.                                            |
| `docker-compose.yml`, `docker-compose.test.yml`                                                                                                                           | Compose and test layout.                                                                                                             |
| `railway.json`, `nixpacks.toml`                                                                                                                                           | Railway deploy; start.sh is start command.                                                                                           |
| `pytest.ini`, `tests/`                                                                                                                                                    | Test layout and markers.                                                                                                             |
| `Makefile`                                                                                                                                                                | References scripts and pytest; no structural change in this plan.                                                                    |
| `README.md`                                                                                                                                                               | Keep at repo root.                                                                                                                   |
| `backend/risk_guardian.py`, `backend/correlation_manager.py`, `backend/pine_guardian.py`, `backend/ai_guardian.py`, `backend/ml_guardian.py`, `backend/market_adapter.py` | Tests and create\_\*\_from_settings() use `backend.<module>`. Moving would require shims or broad import updates. Omit from phase 1. |

---

## 6) Summary

- **Repo runtime:** start.sh → backend.main (API) + backend.worker (Redis); worker → logic → supabase_db + paper_trader. Docker builds flat backend copy; Railway runs start.sh with backend package.
- **Target structure:** Keep backend layout; optionally move root-level docs to `docs/` and legacy scripts/Procfile to `_archive/legacy/`.
- **Move plan:** 12 low-risk moves (docs + 3 legacy items); no Python hot-path or guardian moves.
- **Safety:** Run unit (and full) tests before/after; smoke start.sh; rollback via git revert or git mv back.
- **Do not touch:** All runtime entrypoints, hot-path modules, Dockerfiles, and guardian modules in this phase.

**STOP — Do not implement the plan in this prompt.**
