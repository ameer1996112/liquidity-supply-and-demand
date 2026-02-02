# Legacy / archived scripts

Items here were moved from the main tree during workspace reorg (see `WORKSPACE_REORG_PLAN.md`). They are kept for reference and are not used by runtime entrypoints.

- **backend_Procfile** — Old Procfile (`web: python trading_bot.py`). Railway uses `start.sh` instead.
- **backend_start_bot.sh** — Legacy shell helper; `start.sh` is the canonical entrypoint.
- **backend_start_api_and_worker.sh** — Legacy shell helper; `start.sh` runs API + worker.

To run any of these from repo root you would need to adjust paths (e.g. `cd backend` for scripts that assumed backend cwd).
