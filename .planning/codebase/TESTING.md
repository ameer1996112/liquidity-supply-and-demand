# Testing Patterns

**Analysis Date:** 2026-03-18

## Test Framework

**Frontend (React/TypeScript):**
- **Runner:** Vitest 3.2.4
- **Config:** Not present in committed config files; uses package.json scripts + implicit defaults
- **Environment:** jsdom (`/** @vitest-environment jsdom */` pragma in tests)
- **Assertion Library:** Vitest built-in `expect()`

**Backend (Python):**
- **Framework:** pytest (inferred from `.pytest_cache` directory; no pytest.ini present)
- **Config:** Uses environment-driven testing; settings injected via dependency
- **Test files:** Loose test files in root (`test_api.py`, `test_brain.py`, etc.) and potentially in `tests/` directory (not explored)

**Run Commands:**

Frontend:
```bash
npm run test              # Run all tests (vitest run)
npm run test:watch       # Watch mode (if configured)
npm run lint             # ESLint check
```

Backend:
```bash
pytest                    # Run all test files (implicit discovery of test_*.py)
pytest -v                # Verbose output
pytest --co              # Show collected tests
```

## Test File Organization

**Frontend:**
- **Location:** Co-located with component/utility files
- **Naming:** `{name}.test.ts` or `{name}.test.tsx`
- **Structure:** One test file per component/utility (e.g., `tradingMetrics.test.ts` in `domain/metrics/` directory)
- **Examples:**
  - `frontend/src/domain/metrics/tradingMetrics.test.ts` — Tests for trading KPI calculations
  - `frontend/src/components/SignalInspector.test.tsx` — Tests for SignalInspector component
  - `frontend/src/components/dashboard/RecentSignalsPanel.test.tsx` — Tests for RecentSignalsPanel component

**Backend:**
- **Location:** Mixed; loose test files in project root (`test_api.py`, `test_supabase_keys.py`, `test_brain.py`)
- **Naming:** `test_*.py` prefix convention
- **No formal test directory:** Tests appear ad-hoc, potentially for manual verification or CI/CD checks
- **Examples:**
  - `test_api.py` — Manual API endpoint verification
  - `test_brain.py` — Brain/AI module testing
  - `test_supabase_adapter_live.py` — Live adapter testing

## Test Structure

**Frontend (Vitest + React):**

Standard structure using `describe()` suite with `it()` test cases:

```typescript
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react'; // or createRoot for manual testing

describe('componentName', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it('should render with props', () => {
    const component = mkComponent({ id: 'test-1' });
    act(() => {
      root.render(<TestComponent data={component} />);
    });
    expect(container.textContent).toContain('expected text');
  });
});
```

**Patterns:**
- Use `beforeEach()`/`afterEach()` for setup/teardown (DOM cleanup, React unmounting)
- Wrap render calls in `act()` for React state updates
- Helper functions to create fixtures: `mkSignal()`, `mkComponent()` (reduces boilerplate)
- Use `expect().toBe()`, `expect().toContainEqual()`, `expect().toBeCloseTo()` for assertions

**Backend (pytest):**

No formal test structure observed; appears to be manual scripts rather than framework-based tests:

```python
# test_api.py
import requests

try:
    print("Testing local API...")
    res = requests.get("http://localhost:8000/api/portfolio-control/accounts/comparison")
    print(res.status_code)
    print(res.json())
except Exception as e:
    print(f"Error: {e}")
```

This pattern (basic HTTP requests, print-based verification) suggests tests are:
- Manual verification scripts
- CI/CD step checkers
- Development helpers, not unit tests

## Test Structure (Frontend Examples)

**From `tradingMetrics.test.ts`:**

```typescript
import { describe, expect, it } from 'vitest';
import { computeTradeKpis, formatWinRate, isSignalClosed, isSignalOpen } from './tradingMetrics';
import type { TradingSignal } from '@/types/trading';

// Helper factory
function mkSignal(partial: Partial<TradingSignal>): TradingSignal {
  return {
    id: partial.id ?? 's1',
    created_at: partial.created_at ?? '2026-01-01T10:00:00.000Z',
    symbol: partial.symbol ?? 'XAUUSD',
    side: partial.side ?? 'buy',
    status: partial.status ?? 'active',
    ...partial,
  };
}

describe('tradingMetrics', () => {
  // Test cases using mkSignal helper
  it('classifies executed with no exit/pnl as open', () => {
    const signal = mkSignal({ status: 'executed' });
    expect(isSignalOpen(signal)).toBe(true);
  });

  it('computes consistent kpis and handles empty trades winrate as null', () => {
    const open = mkSignal({ id: 'a', status: 'active' });
    const win = mkSignal({ id: 'b', status: 'closed', pnl: 100 });
    const loss = mkSignal({ id: 'c', status: 'closed', pnl: -40 });

    const kpis = computeTradeKpis([open, win, loss]);
    expect(kpis.totalTrades).toBe(3);
    expect(kpis.winRatePct).toBeCloseTo(33.333, 2);
  });
});
```

**From `SignalInspector.test.tsx`:**

```typescript
/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { SignalInspector } from './SignalInspector';
import type { TradingSignal } from '@/types/trading';

describe('SignalInspector decision summary', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it('renders NO_GO summary and breakdown from decision_trace', () => {
    const signal: TradingSignal = {
      id: 'sig-1',
      created_at: '2026-02-20T10:00:00.000Z',
      symbol: 'XAUUSD',
      side: 'sell',
      status: 'ai_rejected',
      ai_reasoning: { decision: 'NO_GO', decision_trace: { /* ... */ } },
    };

    act(() => {
      root.render(
        <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
      );
    });

    expect(container.textContent).toContain('NO_GO');
  });
});
```

## Mocking

**Frontend:**
- **Framework:** Vitest built-in `vi.mock()` + fetch mocking
- **Pattern:** Mock external API calls; avoid mocking component internals
- **React Query:** Mocking handled through `useQuery` test wrappers or mock HTTP interceptors

**Example (inferred from patterns):**
```typescript
// Mock fetch
global.fetch = vi.fn(async (url, options) => {
  if (url.includes('/api/accounts')) {
    return { ok: true, json: async () => ({ accounts: [] }) };
  }
  throw new Error('Unknown URL');
});
```

**Backend:**
- **Mocking:** No explicit mocking libraries detected (no `unittest.mock` imports in test files)
- **Live Testing:** Tests appear to call actual endpoints (`requests.get("http://localhost:8000/...")`)
- **Approach:** Integration tests against running server, not unit tests with mocks

**What to Mock:**
- External APIs (fetch, HTTP calls in React)
- Event handlers and callbacks
- Expensive operations (don't mock Redux/Supabase client in React tests — test integration instead)

**What NOT to Mock:**
- Component render logic
- React hooks (useQuery, useState, etc.) — test effects
- Database layer — can use test database or fixtures
- Core business logic (risk calculations, KPI computations)

## Fixtures and Factories

**Frontend Test Data:**

Factories are simple TypeScript functions that generate test objects with defaults:

```typescript
// tradingMetrics.test.ts
function mkSignal(partial: Partial<TradingSignal>): TradingSignal {
  return {
    id: partial.id ?? 's1',
    created_at: partial.created_at ?? '2026-01-01T10:00:00.000Z',
    symbol: partial.symbol ?? 'XAUUSD',
    side: partial.side ?? 'buy',
    status: partial.status ?? 'active',
    ...partial,
  };
}

// Usage
const signal = mkSignal({ status: 'closed', pnl: 100 });
```

**Location:** Defined at test file top, before `describe()` block

**Backend Test Data:**

No formal fixtures detected; tests use inline data or manual API payloads.

## Coverage

**Requirements:** Not enforced (no `.nyc_config.js`, no coverage thresholds in configuration)

**View Coverage (Frontend):**
```bash
npm run test -- --coverage        # If configured
# or manually
vitest run --coverage
```

**View Coverage (Backend):**
```bash
pytest --cov=src --cov-report=html
```

**Current State:**
- Frontend: Limited test coverage; only a few component/utility tests present
- Backend: Ad-hoc testing; no systematic test suite

## Test Types

**Frontend Unit Tests:**
- **Scope:** Utility functions (KPI calculations, formatters) and component rendering
- **Approach:** Test single function/component in isolation with mocked dependencies
- **Example:** `tradingMetrics.test.ts` tests `computeTradeKpis()` with hardcoded signal data
- **Frequency:** Low (only a few test files present)

**Frontend Integration Tests:**
- **Scope:** Hook behavior (useQuery with Supabase), component + hook interaction
- **Approach:** Render component with real hooks; mock fetch/HTTP layer
- **Example:** Component that fetches and displays account data with `useQuery`
- **Frequency:** Low

**Backend Unit Tests:**
- **Scope:** Risk calculations, signal validation, business logic
- **Implementation:** Not formally structured; logic testable via imports/manual verification
- **Example:** `calculate_max_position_size()` can be unit tested with hardcoded symbols/balances
- **Frequency:** Rare (logic typically tested via integration tests or live endpoints)

**Backend Integration Tests:**
- **Scope:** API endpoints, webhook processing, database operations
- **Approach:** HTTP requests to running server, verify response and database state
- **Example:** `test_api.py` calls `http://localhost:8000/api/...` and checks JSON response
- **Frequency:** Medium (loose test files for verification and CI/CD checks)

**E2E Tests:**
- **Framework:** Not detected (no Playwright, Cypress, or Selenium config)
- **Current:** Functionality tested manually or via API integration tests
- **Approach needed:** Would require browser automation or headless testing framework

## Common Patterns

**Async Testing (Frontend):**

React state updates in tests must be wrapped in `act()`:

```typescript
it('updates when signal arrives', async () => {
  act(() => {
    root.render(<Component />);
  });

  // Simulate async update
  await act(async () => {
    // await some promise
  });

  expect(container.textContent).toContain('updated');
});
```

With React Query hooks:
```typescript
const { data, isLoading } = useQuery({
  queryKey: ['signals'],
  queryFn: async () => {
    // Mocked to return immediately
    return [{ id: 's1', status: 'active' }];
  },
});
```

**Async Testing (Backend):**

Python async tests use `@pytest.mark.asyncio` decorator (if async tests exist):

```python
@pytest.mark.asyncio
async def test_webhook_processing():
    result = await process_webhook(payload)
    assert result.status == "success"
```

**Error Testing:**

Frontend pattern (expected to throw):
```typescript
it('throws on invalid input', () => {
  expect(() => {
    computeTradeKpis(null);
  }).toThrow();
});
```

Backend pattern (catch and verify):
```python
def test_invalid_payload():
    try:
        validate_webhook_payload({})
        assert False, "Should have raised"
    except ValidationError as e:
        assert "symbol" in str(e)
```

**Boundary Testing:**

Frontend example (limit values):
```typescript
it('formats winrate with dash/zero behavior when trades=0', () => {
  expect(formatWinRate(null, 0, 'dash')).toBe('—');
  expect(formatWinRate(null, 0, 'zero')).toBe('0.0%');
  expect(formatWinRate(50, 2, 'dash')).toBe('50.0%');
});
```

## Test-Driven Conventions

**Before Writing Code:**
- Identify what needs testing: API contracts, business logic (risk calcs), edge cases
- Create minimal test that fails
- Write implementation to pass test

**Test Naming:**
- Describe the behavior, not the implementation
- Use `it('should...')` or `it('...')` format
- Examples:
  - ✅ `it('classifies executed with no exit/pnl as open')`
  - ✅ `it('computes consistent kpis and handles empty trades winrate as null')`
  - ❌ `it('test function')`

**Test Independence:**
- Each test should run in isolation; no shared state between tests
- Use `beforeEach()`/`afterEach()` for setup/teardown
- Avoid relying on test execution order

---

*Testing analysis: 2026-03-18*
