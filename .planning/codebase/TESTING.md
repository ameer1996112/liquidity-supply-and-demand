# TESTING.md — Testing Structure & Practices

## Framework & Tooling

### Backend (Python)
- **Framework**: `pytest` with conftest fixtures
- **Runner**: `PYTHONPATH=/workspace pytest tests/ -v`
- **Coverage**: No coverage config present — manual verification
- **Pre-existing state**: 11 tests passing per AGENTS.md; full suite has 24 test files

### Frontend (TypeScript)
- **Framework**: Vitest 3.2.4
- **Runner**: `cd frontend && npx vitest run`
- **Environment**: jsdom 27.0.1
- **Config**: `frontend/vitest.config.ts`
- **Pre-existing state**: 1 pre-existing failure in `tradingMetrics.test.ts`

---

## Test Data / Fixture Strategy

### Backend Fixtures (`tests/conftest.py`)
```python
# InMemoryTransport for isolated queue testing
@pytest.fixture
def transport():
    return InMemoryTransport()

# Supabase client mocked via pytest monkeypatch or fixture
```

### Signal Payload Factory Pattern
Tests construct signal dicts directly:
```python
signal = {
    "symbol": "EURUSD",
    "side": "buy",
    "entry": 1.0800,
    "sl": 1.0780,
    "tp": 1.0840,
    "size": 0.1,
    "run_mode": "PAPER",
}
```

---

## Test Categories

### End-to-End Tests (`test_e2e.py` — 21KB)
- Full signal pipeline from webhook receipt to execution
- Uses `InMemoryTransport` to bypass Redis
- Validates signal flows through guard rails and into execution

### Pipeline Tests (`test_pipeline.py`, `test_pipeline_traces.py`)
- Worker pipeline stage-by-stage validation
- Latency trace recording verification

### Guard Rail Tests
- `test_pine_guardian_adaptive.py` — PineGuardian adaptive limits, streak bonuses, session slots
- `test_consumer_validation.py` — Webhook payload schema edge cases
- `test_signal_transport.py` — Transport abstraction correctness

### AI/ML Tests
- `test_ai_brain.py` (14KB) — EnsembleBrain decision paths
- `test_debate.py` (11KB) — Trading Council debate flow
- `test_llm_client.py` (11KB) — LLM client provider fallback

### Business Logic Tests
- `test_account_routing.py` (20KB) — Multi-account symbol routing
- `test_backtests.py` (15KB) — Backtest engine validation
- `test_graduation.py` — AI shadow→enforce graduation criteria
- `test_reflection_memory.py` — Post-trade memory retrieval
- `test_strategy_config.py` — Strategy-as-data validation

### Reliability Tests
- `test_sprint55_reliability.py` (18KB) — Regression suite for key reliability behaviors
- `test_worker_observers.py` (17KB) — Observer pattern correctness

### Integration Tests
- `test_metaapi_auth.py` — MetaAPI authentication
- `test_api_tickets.py` (9KB) — Jira proxy integration
- `test_pnl_broker_fetch.py` — Broker PnL retrieval (minimal)

---

## Mocking Patterns

### Transport Isolation
```python
# Use InMemoryTransport instead of Redis in tests
from src.core.transport import InMemoryTransport
transport = InMemoryTransport()
```

### Supabase Mocking
- Tests typically mock `supabase.table()` via `monkeypatch` or test doubles

### LLM Mocking
```python
# llm_client tests use provider-specific mocks
# AI guardian tests mock llm_client.call()
```

---

## Running Tests

```bash
# Full suite
PYTHONPATH=/workspace pytest tests/ -v

# Single file
PYTHONPATH=/workspace pytest tests/test_pipeline.py -v

# Frontend
cd frontend && npx vitest run

# Backend lint
ruff check src/ config/ tests/
```

---

## Known Test Gaps

- `test_pnl_broker_fetch.py` — only 61 bytes, effectively empty
- Frontend has 1 persistent failure in `tradingMetrics.test.ts`
- No integration tests running against real Redis or Supabase (all use mocks/in-memory)
- No performance/load tests
- ML model training and drift tests not automated
