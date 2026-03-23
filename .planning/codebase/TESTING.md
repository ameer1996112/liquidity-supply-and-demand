# TESTING.md — Test Structure & Practices

## Framework & Configuration

- **Backend**: `pytest` with `PYTHONPATH=/workspace`
- **Frontend**: `vitest` v3
- **Run backend**: `PYTHONPATH=/workspace pytest tests/ -v`
- **Run frontend**: `cd frontend && npx vitest run`
- **Backend lint**: `ruff check src/ config/ tests/`
- **Frontend lint**: `cd frontend && npx eslint`

## Test File Organization

### Backend (`tests/`)
```
tests/
├── conftest.py                   # Global fixtures (mocks Redis, sets env vars)
├── test_e2e.py                   # End-to-end signal pipeline tests (21KB)
├── test_pipeline.py              # Worker pipeline unit tests (11KB)
├── test_pipeline_traces.py       # Pipeline trace/audit tests (19KB)
├── test_worker_observers.py      # Observer pattern tests (17KB)
├── test_sprint55_reliability.py  # Reliability/resilience tests (18KB)
├── test_ai_brain.py              # AI ensemble tests (14KB)
├── test_debate.py                # TradingCouncil debate tests (11KB)
├── test_llm_client.py            # LLM client tests (11KB)
├── test_account_routing.py       # Multi-account routing (20KB)
├── test_signal_transport.py      # Redis/memory transport (9KB)
├── test_consumer_validation.py   # Payload validation (7.7KB)
├── test_api_tickets.py           # Ticket API integration (9.4KB)
├── test_ai_mode_api.py           # AI mode API tests (4.6KB)
├── test_backtests.py             # Backtest engine (15KB)
├── test_prop_firm_phase1.py      # Prop firm compliance (3.6KB)
├── test_graduation.py            # AI graduation/promotion (3.1KB)
├── test_strategy_config.py       # Strategy config (3.8KB)
├── test_reflection_memory.py     # Memory/reflection (6.4KB)
├── test_sprint23_api_filters.py  # API filter endpoint tests (12KB)
├── test_metaapi_auth.py          # MetaAPI auth (3.2KB)
└── test_pnl_broker_fetch.py      # PnL fetch (trivially small)
```

**Total**: 22 test files | 11 tests currently passing (full suite runs)

### Frontend (`frontend/`)
- Tests live alongside components or in `__tests__/` subdirectories
- **Vitest** + **jsdom** for React component testing
- 1 pre-existing failure in `tradingMetrics.test.ts` (known issue)

## conftest.py Patterns

```python
# tests/conftest.py — global setup before any src.* imports
import os
os.environ.setdefault("SUPABASE_URL", "http://dummy.supabase.test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SIGNAL_TRANSPORT", "memory")  # in-memory queue for tests
os.environ.setdefault("AI_API_KEY", "dummy-ai-key")

# autouse fixture mocks Redis globally
@pytest.fixture(autouse=True)
def _mock_redis_client(monkeypatch):
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    # ... configure returns
    monkeypatch.setattr(rq, "_redis", mock_redis)
    yield mock_redis
```

Key patterns from conftest:
- Dummy env vars set **before** any `src.*` imports (avoids ValidationError)
- `SIGNAL_TRANSPORT=memory` — tests never touch real Redis
- `SUPABASE_KEY=""` — Supabase init block skipped (guarded by `if key:`)
- **autouse** Redis mock prevents all TCP connections in tests

## Mocking Strategy

### External Services
- **Redis**: Mocked globally via `monkeypatch.setattr(rq, "_redis", MagicMock())`
- **Supabase**: Tests needing DB must patch `src.adapters.supabase.SupabaseAdapter` directly
- **MetaAPI**: `META_API_TOKEN=""` disables it; tests mock execution adapter
- **LLM APIs**: `AI_API_KEY="dummy-ai-key"` — tests mock at `llm_client` level

### Common Patterns
```python
# Mock get_settings() for specific test values
from unittest.mock import patch
with patch("config.settings.get_settings") as mock_settings:
    mock_settings.return_value.ai_filter_enabled = False
    ...

# Mock Supabase adapter
with patch("src.adapters.supabase.SupabaseAdapter") as MockAdapter:
    MockAdapter.return_value.get_signals.return_value = [...]
    ...
```

## Test Categories

| Category | Test Files | What's Tested |
|---|---|---|
| Pipeline | `test_pipeline.py`, `test_e2e.py` | Full signal flow, guard rails |
| AI/ML | `test_ai_brain.py`, `test_debate.py`, `test_llm_client.py` | AI ensemble, debate, LLM client |
| Worker | `test_worker_observers.py`, `test_sprint55_reliability.py` | Observer events, resilience |
| Infra | `test_signal_transport.py`, `test_consumer_validation.py` | Transport, payload validation |
| API | `test_api_tickets.py`, `test_ai_mode_api.py`, `test_sprint23_api_filters.py` | HTTP endpoints |
| Domain | `test_account_routing.py`, `test_strategy_config.py` | Business logic |
| Prop Firm | `test_prop_firm_phase1.py`, `test_graduation.py` | Compliance rules |
| Data | `test_backtests.py`, `test_reflection_memory.py` | Backtest, memory |

## Known Test State

- **Backend**: 11 of 22+ test files pass; `PYTHONPATH=/workspace pytest tests/ -v` is the command
- **Frontend**: 1 pre-existing failure in `tradingMetrics.test.ts` (metric calculation edge case)
- **No CI pipeline**: Makefile references `docker-compose.test.yml` that doesn't exist; use local Redis directly
- Test coverage is functional but not comprehensive — many services lack unit tests

## Frontend Test Pattern (Vitest)

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: { environment: "jsdom" }
});

// Component test pattern
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

describe("SignalCard", () => {
  it("displays signal symbol", () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
  });
});
```
