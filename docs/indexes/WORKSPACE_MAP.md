# Workspace Map

## Main folders
- `src/` — backend API, services, worker logic
- `frontend/` — UI and dashboard
- `scripts/` — maintenance, utilities, backfills, diagnostics
- `tests/` — automated tests
- `migrations/` — database schema changes
- `data/` — datasets and exports
- `docs/` — plans, contracts, guides, notes
- `ml/` — local models and ML assets

## Rules
- Frontend tasks stay in `frontend/`
- Backend tasks stay in `src/`, `tests/`, `migrations/`
- Script/debug tasks stay in `scripts/`
- Do not scan large data folders unless requested
- Do not scan archived docs unless requested