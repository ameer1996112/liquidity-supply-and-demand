# TESTING.md — Test Structure & Practices

## Backend Tests (pytest)

### Running Tests

```bash
# Full suite (259 tests)
PYTHONPATH=/Users/ameeramer/dev/projects/galilsoftware/sources/trading \
  venv/bin/python3 -m pytest tests/ -v

# Quick pass (quiet)
PYTHONPATH=/workspace venv/bin/python3 -m pytest tests/ -q

# Single file
PYTHONPATH=/workspace pytest tests/test_prop_firm_phase1.py -v
```

**Note:** Use `venv/bin/python3` not system python. `PYTHONPATH` must be set.

### Test Files

```
tests/
├── conftest.py                     # Global fixtures + env setup
├── test_account_routing.py         # AccountRouter logic
├── test_ai_brain.py                # AI guardian
├── test_ai_mode_api.py             # AI mode API endpoints
├── test_backtests.py               # Backtest endpoints
├── test_consumer_validation.py     # Worker payload validation
├── test_debate.py                  # AI debate/council
├── test_e2e.py                     # End-to-end pipeline tests
├── test_graduation.py              # Prop firm graduation logic
├── test_llm_client.py              # LLM client abstraction
├── test_metaapi_auth.py            # MetaAPI authentication
├── test_pipeline.py                # Worker pipeline flow
├── test_pipeline_traces.py         # Trace logging
├── test_pnl_broker_fetch.py        # PnL fetching from broker
├── test_prop_firm_phase1.py        # Phase 1 prop firm tests
├── test_reflection_memory.py       # AI reflection/memory
├── test_signal_transport.py        # Redis/memory transport
├── test_sprint23_api_filters.py    # API filter regression tests
└── test_sprint55_reliability.py    # Reliability/resilience tests
```

### conftest.py — Global Setup

`tests/conftest.py` sets dummy env vars BEFORE any `src.*` imports:

```python
os.environ.setdefault("SUPABASE_URL", "http://dummy.supabase.test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SIGNAL_TRANSPORT", "memory")  # No real Redis in tests
os.environ.setdefault("META_API_TOKEN", "")
os.environ.setdefault("AI_API_KEY", "dummy-ai-key")
```

**Important:** `SIGNAL_TRANSPORT=memory` means tests use in-memory queue, never touch Redis.

### Key Fixtures

```python
# conftest.py provides:
@pytest.fixture(autouse=True)
def _mock_redis_client(monkeypatch):
    """Replace Redis client with MagicMock for every test."""

# Use in tests:
def test_something(monkeypatch):
    monkeypatch.setattr("src.module.get_settings", lambda: mock_settings)
```

### Mocking Pattern

Tests mock external services at the adapter boundary:

```python
from unittest.mock import MagicMock, patch, AsyncMock

# Mock Supabase
def test_analytics(monkeypatch):
    mock_sb = MagicMock()
    mock_sb.table().select().execute.return_value.data = [...]
    monkeypatch.setattr("src.api_analytics._get_supabase", lambda: mock_sb)

# Mock MetaAPI
with patch("src.adapters.metaapi.execute_trade") as mock_trade:
    mock_trade.return_value = {"order_id": "123"}
    ...

# Mock settings
mock_settings = MagicMock()
mock_settings.live_trading_enabled = False
mock_settings.min_rr_ratio = 1.5
```

### FastAPI TestClient Pattern

```python
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_webhook():
    response = client.post("/webhook", json={
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.10,
        "sl": 1.09,
        "tp": 1.12,
        "size": 0.1
    })
    assert response.status_code == 200
```

## Frontend Tests (vitest)

### Running Tests

```bash
cd frontend
npx vitest run       # Run once
npx vitest           # Watch mode
```

**Note:** 1 pre-existing failure in `tradingMetrics.test.ts` — known issue, not a regression.

### Test Location

- Co-located: `frontend/src/components/SignalInspector.test.tsx`
- Utility-level: `frontend/src/lib/tradingMetrics.test.ts`

### Vitest Pattern

```typescript
import { describe, it, expect, vi } from "vitest"

describe("MyComponent", () => {
  it("renders correctly", () => {
    // ...
  })
})
```

## Coverage Gaps (known)

- `src/core/guard_rails/` — guard rails have partial coverage
- `src/adapters/metaapi.py` — MetaAPI adapter mostly mocked
- Frontend hooks — not systematically tested (only component-level tests)
- `src/services/trailing_stop_manager.py` — limited test coverage
