# TESTING.md — Test Structure & Practices

## Backend Tests (Python)

### Framework
- **pytest** (inferred from test file structure + conftest.py)
- `PYTHONPATH=/workspace pytest tests/ -v` to run
- **11 tests pass** baseline (as of AGENTS.md)
- 21 test files in `tests/` directory

### Structure

```
tests/
├── conftest.py                     # Shared fixtures
├── test_account_routing.py         # Account router logic (20KB)
├── test_ai_brain.py                # AI ensemble brain (14KB)
├── test_ai_mode_api.py             # AI mode API endpoints (4KB)
├── test_backtests.py               # Backtest functionality (15KB)
├── test_consumer_validation.py     # Webhook validation (7KB)
├── test_debate.py                  # Council debate (11KB)
├── test_e2e.py                     # End-to-end pipeline tests (21KB)
├── test_graduation.py              # AI graduation logic (3KB)
├── test_llm_client.py              # LLM client (11KB)
├── test_metaapi_auth.py            # MetaAPI authentication (3KB)
├── test_pipeline.py                # Signal pipeline (11KB)
├── test_pipeline_traces.py         # Pipeline trace recording (19KB)
├── test_pnl_broker_fetch.py        # PnL fetch (61 bytes — empty/stub)
├── test_prop_firm_phase1.py        # Prop firm phase 1 rules (3KB)
├── test_reflection_memory.py       # AI memory/reflection (6KB)
├── test_signal_transport.py        # Redis/memory transport (9KB)
├── test_sprint23_api_filters.py    # API filter endpoints (12KB)
├── test_sprint55_reliability.py    # Reliability tests (18KB)
├── test_strategy_config.py         # Strategy configuration (3KB)
└── test_worker_observers.py        # Worker observer pattern (17KB)
```

### Key Patterns

**Mocking External Dependencies**
All external services (Supabase, Redis, MetaAPI, LLMs) are mocked in unit tests:
```python
from unittest.mock import AsyncMock, patch, MagicMock

@patch('src.adapters.supabase.SupabaseAdapter')
@patch('src.adapters.redis_queue.RedisQueue')
async def test_signal_processing(mock_redis, mock_supabase):
    mock_supabase.return_value.get_accounts.return_value = [...]
    mock_redis.return_value.pop_signal.return_value = test_signal
    ...
```

**Signal Transport Abstraction** (`SIGNAL_TRANSPORT=memory`)
Tests use in-memory transport instead of Redis:
```python
# conftest.py pattern
os.environ['SIGNAL_TRANSPORT'] = 'memory'
```

**Disabling AI Guards in Tests**
```python
# Guards can be disabled per test
os.environ['AI_FILTER_ENABLED'] = 'false'
os.environ['ML_GUARDIAN_ENABLED'] = 'false'
```

**Test Classes (unittest.TestCase mixed with pytest)**
Some test files use hybrid approach:
```python
class TestAIBrain(unittest.TestCase):
    def setUp(self):
        self.brain = AIBrain(settings=mock_settings)
    
    def test_confidence_threshold(self):
        ...
```

**conftest.py Fixtures**
- Likely provides common settings, Supabase client mocks, test signal factories
- 2378 bytes — lightweight fixture file

### Running Tests
```bash
# All tests
PYTHONPATH=/workspace pytest tests/ -v

# Specific test file
PYTHONPATH=/workspace pytest tests/test_pipeline.py -v

# With coverage (if configured)
PYTHONPATH=/workspace pytest tests/ --cov=src
```

---

## Frontend Tests (TypeScript)

### Framework
- **Vitest** — test runner (Vite-native, Jest-compatible API)
- **@testing-library/react** — component testing
- Config: `frontend/vitest.config.ts`
- Run: `cd frontend && npx vitest run`

### Test Files

```
frontend/src/
├── components/
│   ├── SignalInspector.test.tsx             # Component test
│   └── dashboard/
│       └── RecentSignalsPanel.test.tsx      # Component test
└── domain/
    └── metrics/
        └── tradingMetrics.test.ts           # ⚠️ Known pre-existing failure
```

### Known Failures

**`tradingMetrics.test.ts`** — 1 pre-existing test failure  
- Documented in AGENTS.md as baseline known failure
- Relates to trade metric calculations in `domain/` layer
- Not a regression — exists before current work

### Test Patterns

**Component Tests**
```tsx
import { render, screen } from '@testing-library/react';
import { SignalInspector } from './SignalInspector';

it('renders signal inspector', () => {
    render(<SignalInspector signal={mockSignal} />);
    expect(screen.getByText('Signal Inspector')).toBeInTheDocument();
});
```

**Domain Unit Tests**
```typescript
import { calculateWinRate } from './tradingMetrics';

it('calculates win rate from trades', () => {
    const trades = [{ pnl: 100 }, { pnl: -50 }, { pnl: 200 }];
    expect(calculateWinRate(trades)).toBe(0.667);
});
```

### Running Frontend Tests
```bash
cd frontend
npx vitest run                  # Run all tests once
npx vitest                      # Watch mode
npx vitest run --reporter=verbose  # Verbose output
```

---

## Test Coverage Gaps

Notable areas with little or no test coverage:
- `src/api_portfolio_control.py` (83KB) — no dedicated test file
- Frontend pages in `app/` — not unit tested (would need E2E/Cypress)
- MetaAPI adapter live execution — mocked only
- `test_pnl_broker_fetch.py` — empty stub file (61 bytes)
