# Testing

## Backend Tests

### Framework
- **Runner**: pytest
- **Location**: `tests/` (21 test files)
- **Config**: `tests/conftest.py` (2.4KB) — shared fixtures
- **Run command**: `PYTHONPATH=/workspace pytest tests/ -v`
- **Status**: 11 tests pass (many test files contain multiple test functions)

### Test Files

| File | Focus | Size |
|------|-------|------|
| `test_e2e.py` | End-to-end signal pipeline | 21KB |
| `test_account_routing.py` | Multi-account routing | 21KB |
| `test_sprint55_reliability.py` | Reliability features | 18KB |
| `test_pipeline_traces.py` | Pipeline tracing | 19KB |
| `test_worker_observers.py` | Worker observer pattern | 17KB |
| `test_backtests.py` | Backtesting engine | 15KB |
| `test_ai_brain.py` | AI brain ensemble | 14KB |
| `test_sprint23_api_filters.py` | API filter features | 13KB |
| `test_debate.py` | Bull/Bear debate | 12KB |
| `test_llm_client.py` | LLM client | 12KB |
| `test_pipeline.py` | Signal pipeline | 11KB |
| `test_signal_transport.py` | Signal transport | 9KB |
| `test_consumer_validation.py` | Consumer validator | 8KB |
| `test_reflection_memory.py` | Reflection/memory | 6KB |
| `test_ai_mode_api.py` | AI mode API | 5KB |
| `test_strategy_config.py` | Strategy config | 4KB |
| `test_prop_firm_phase1.py` | Prop firm phase 1 | 4KB |
| `test_graduation.py` | Strategy graduation | 3KB |
| `test_metaapi_auth.py` | MetaAPI auth | 3KB |
| `test_pnl_broker_fetch.py` | PnL broker fetch | 0.2KB |
| `conftest.py` | Shared fixtures | 2.4KB |

### Mocking Pattern
- Manual mocking (no `unittest.mock` framework preference documented)
- Settings overridden via test fixtures
- In-memory signal transport for tests (`SIGNAL_TRANSPORT=memory`)

### Root-level Test Scripts
- Multiple ad-hoc test scripts at project root (`test_age.py`, `test_api.py`, `test_brain.py`, `test_db.py`, `test_sync.py`, etc.)
- These appear to be one-off verification scripts, not part of the formal test suite

## Frontend Tests

### Framework
- **Runner**: Vitest ^3.2.4
- **DOM**: jsdom ^27.0.1
- **Config**: `frontend/vitest.config.ts`
- **Run command**: `cd frontend && npx vitest run`
- **Status**: 1 pre-existing failure in `tradingMetrics.test.ts`

### Test Files
- `frontend/src/components/SignalInspector.test.tsx` (5.5KB) — component test
- `frontend/src/domain/metrics/` — domain logic tests
- Limited frontend test coverage overall

## Coverage

- **Backend**: Moderate coverage on core pipeline, AI brain, guard rails, transport
- **Frontend**: Minimal — only a few component/domain tests
- **Integration**: E2E test covers full signal pipeline
- **No CI/CD test pipeline** visible in repository
