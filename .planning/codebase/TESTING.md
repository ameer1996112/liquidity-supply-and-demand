# TESTING

## Backend Testing
- **Framework**: `pytest`
- **Execution**: Can be run via `PYTHONPATH=/workspace pytest tests/ -v`
- **Coverage**: Currently has 11 existing backend tests that cover APIs, database adapters, synchronization, and RAG components. All 11 tests are passing.
- **Location**: `/tests/` directory. 

## Frontend Testing
- **Framework**: `vitest`
- **Execution**: Run via `cd frontend && npx vitest run`
- **Status**: There is currently 1 pre-existing failure in `tradingMetrics.test.ts`.

## Infrastructure Testing
- Local tests use local Redis instances. The Makefile references a `docker-compose.test.yml` which does not actually exist in the repo (use local Redis server directly instead).
