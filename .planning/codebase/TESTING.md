# Testing

## Frameworks

### Backend (Python)
- **pytest** — primary test runner
- **unittest.mock** — mocking/patching
- **pytest fixtures** — shared test infrastructure via `tests/conftest.py`

### Frontend (TypeScript/React)
- **Vitest** — test runner (configured in `frontend/vitest.config.ts`)
- **jsdom** — browser environment simulation
- Tests are co-located with components: `<Component>.test.tsx`

## Backend Test Structure

### Location
All Python tests live in `tests/` directory.

### Test Files
```
tests/
├── conftest.py                     # Global fixtures and env setup
├── test_signal_transport.py
├── test_worker_observers.py
├── test_ai_mode_api.py
├── test_account_routing.py
├── test_llm_client.py
├── test_ai_brain.py
├── test_prop_firm_phase1.py
├── test_graduation.py
├── test_sprint55_reliability.py
├── test_backtests.py
├── test_strategy_config.py
├── test_sprint23_api_filters.py
├── test_e2e.py
├── test_metaapi_auth.py
├── test_reflection_memory.py
├── test_pipeline.py
├── test_pipeline_traces.py
├── test_consumer_validation.py
├── test_pnl_broker_fetch.py
├── test_debate.py
└── ...
```

### Conftest Pattern (`tests/conftest.py`)
```python
# Dummy env vars set BEFORE any src.* imports
os.environ.setdefault("SUPABASE_URL", "http://dummy.supabase.test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SIGNAL_TRANSPORT", "memory")  # in-memory transport

# Global autouse fixture mocks Redis
@pytest.fixture(autouse=True)
def _mock_redis_client(monkeypatch):
    mock_redis = MagicMock()
    import src.adapters.redis_queue as rq
    monkeypatch.setattr(rq, "_redis", mock_redis)
    yield mock_redis
```

Key pattern: **env vars set at module level** (before imports) to prevent `config.Settings` `ValidationError`.

### Mocking Strategy
- `monkeypatch` for module-level singletons (Redis, settings)
- `unittest.mock.patch` for external API calls (MetaAPI, OpenAI)
- **No real Redis or Supabase** in standard tests — `SIGNAL_TRANSPORT=memory` bypasses Redis
- Tests needing specific behavior must patch at finer scope themselves
- **Philosophy:** Integration tests can hit real services; unit tests mock at adapter boundary

## Frontend Test Structure

### Location
Co-located with components: `frontend/src/components/**/*.test.tsx`

### Config (`frontend/vitest.config.ts`)
```typescript
export default defineConfig({
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  test: { environment: 'jsdom' },
});
```

### Known Test Files
- `frontend/src/components/SignalInspector.test.tsx`

## Running Tests

### Backend
```bash
# Run all tests
pytest tests/

# Run specific file
pytest tests/test_pipeline.py -v

# Run with output
pytest tests/ -s
```

### Frontend
```bash
cd frontend
npm test
# or
npx vitest
```

## Coverage

No formal coverage thresholds are configured. Tests are feature/sprint-named (e.g., `test_sprint23_api_filters.py`) suggesting incremental coverage tied to sprint work.

## Gaps / Notes

- Most tests are backend unit/integration tests; frontend test coverage appears limited (only one confirmed `.test.tsx` file found)
- Some tests are named `test_sprint<N>_*` suggesting sprint-driven (not regression-first) coverage
- `test_e2e.py` exists but true E2E requires live services (MetaAPI, Supabase)
- No CI configuration found in the repo (tests likely run manually or via Railway deploy hooks)
