# Testing Patterns

**Analysis Date:** 2025-01-09

## Overview

This document describes the testing strategy, frameworks, and patterns used across the Trading System codebase. The project uses **pytest** for Python backend testing and **Vitest** with **React Testing Library** for frontend testing.

## Test Frameworks & Tools

### Python Backend

| Tool | Purpose | Version |
|------|---------|---------|
| pytest | Test runner and framework | Core testing infrastructure |
| pytest-asyncio | Async test support | For testing async FastAPI and MetaApi code |
| pytest-mock | Mocking utilities | Wrapper around unittest.mock |
| unittest | Standard library testing | Base for TestCase pattern |

### Frontend (Next.js/TypeScript)

| Tool | Purpose | Configuration |
|------|---------|---------------|
| Vitest | Test runner | `frontend/vitest.config.ts` |
| jsdom | DOM environment | For component testing |
| React Testing Library | Component testing | DOM queries and user interactions |
| @testing-library/jest-dom | DOM assertions | `toBeInTheDocument()`, etc. |

## Python Testing Patterns

### Test File Structure

**Location:** `tests/` directory at project root  
**Naming:** `test_*.py` for all test files  
**Total:** 36 test files covering backend components

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_api.py              # API endpoint tests
├── test_ai_brain.py         # AI/ML component tests
├── test_execution_engine.py # Trading execution tests
├── test_guardrails.py       # Risk management tests
├── test_integration.py      # Integration tests
└── ...
```

### Test Class Pattern

**Standard `unittest.TestCase` structure:**

```python
# tests/test_ai_brain.py
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock
from src.ai.ai_brain import AIBrain, evaluate_signal_quality

class TestAIBrain(unittest.TestCase):
    """Test suite for AI decision making components."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.brain = AIBrain()
        self.sample_signal = {
            'symbol': 'EURUSD',
            'entry': 1.0850,
            'side': 'BUY',
            'sl': 1.0800,
            'tp': 1.0950,
            'size': 0.01
        }
    
    def tearDown(self):
        """Clean up after each test method."""
        pass
    
    @patch('src.ai.ai_brain.get_openai_client')
    def test_evaluate_signal_quality_returns_score(self, mock_client):
        """Test that signal evaluation returns quality score."""
        # Arrange
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "85"
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        # Act
        result = evaluate_signal_quality(self.sample_signal)
        
        # Act
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 85)
        self.assertFalse(result.vetoed)
    
    @patch('src.ai.ai_brain.get_openai_client')
    def test_low_quality_signal_gets_vetoed(self, mock_client):
        """Test that signals below threshold are vetoed."""
        # Arrange
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "45"  # Below 50 threshold
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        # Act
        result = evaluate_signal_quality(self.sample_signal)
        
        # Assert
        self.assertTrue(result.vetoed)
        self.assertEqual(result.reason, "Quality score below threshold")
```

### Async Testing Pattern

**Testing async functions with pytest-asyncio:**

```python
# tests/test_execution_engine.py
import pytest
from unittest.mock import AsyncMock, patch
from src.services.execution_engine import ExecutionEngine

@pytest.mark.asyncio
async def test_execute_trade_success():
    """Test successful trade execution."""
    # Arrange
    engine = ExecutionEngine()
    signal = {
        'symbol': 'EURUSD',
        'side': 'BUY',
        'entry': 1.0850,
        'size': 0.01
    }
    
    with patch('src.services.execution_engine.MetaApiClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.execute_trade.return_value = {
            'orderId': '12345',
            'status': 'filled'
        }
        mock_client.return_value = mock_instance
        
        # Act
        result = await engine.execute(signal)
        
        # Assert
        assert result['status'] == 'filled'
        assert result['orderId'] == '12345'
        mock_instance.execute_trade.assert_called_once()

@pytest.mark.asyncio
async def test_execute_trade_handles_timeout():
    """Test graceful handling of MetaApi timeout."""
    engine = ExecutionEngine()
    
    with patch('src.services.execution_engine.MetaApiClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.execute_trade.side_effect = TimeoutError("Connection timeout")
        mock_client.return_value = mock_instance
        
        # Act & Assert - should raise or return error state
        with pytest.raises(TimeoutError):
            await engine.execute({'symbol': 'EURUSD', 'side': 'BUY'})
```

### Mocking Patterns

**1. SimpleNamespace for mock objects:**

```python
from types import SimpleNamespace

def test_process_signal_with_valid_data():
    """Test signal processing with mocked dependencies."""
    # Create mock objects with SimpleNamespace
    mock_redis = SimpleNamespace(
        get=MagicMock(return_value=None),
        setex=MagicMock(return_value=True),
        ping=MagicMock(return_value=True)
    )
    
    mock_supabase = SimpleNamespace(
        table=MagicMock(return_value=SimpleNamespace(
            insert=MagicMock(return_value={'data': []})
        ))
    )
    
    with patch('src.api.redis_client', mock_redis):
        with patch('src.api.get_supabase_client', return_value=mock_supabase):
            # Test code here
            pass
```

**2. Patch decorator stacking:**

```python
@patch('src.services.execution_engine.get_settings')
@patch('src.services.execution_engine.MetaApiClient')
@patch('src.services.execution_engine.logger')
async def test_execute_with_all_dependencies_mocked(
    mock_logger, mock_client, mock_settings
):
    """Test with full dependency injection."""
    # Mocks are passed in reverse order of decorators
    mock_settings.return_value.paper_trading = True
    mock_client.return_value.execute_trade.return_value = {'status': 'success'}
    
    engine = ExecutionEngine()
    result = await engine.execute({'symbol': 'EURUSD'})
    
    assert result['status'] == 'success'
    mock_logger.info.assert_called()  # Verify logging occurred
```

**3. AsyncMock for async dependencies:**

```python
from unittest.mock import AsyncMock

async def test_async_operations():
    """Test with async mocks."""
    mock_service = AsyncMock()
    
    # Configure async return values
    mock_service.fetch_data.return_value = {'price': 1.0850}
    mock_service.save_record.return_value = {'id': 'abc123'}
    
    # Use in test
    data = await mock_service.fetch_data('EURUSD')
    assert data['price'] == 1.0850
```

### conftest.py Shared Fixtures

**Global configuration in `tests/conftest.py`:**

```python
# tests/conftest.py
import pytest
import os
from unittest.mock import MagicMock, patch

# Force test environment variables before any imports
os.environ['REDIS_URL'] = 'redis://localhost:6379/1'  # Use DB 1 for tests
os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
os.environ['SUPABASE_KEY'] = 'test-key'
os.environ['PAPER_TRADING'] = 'true'
os.environ['AI_FILTER_ENABLED'] = 'false'
os.environ['ML_GUARDIAN_ENABLED'] = 'false'

@pytest.fixture(autouse=True)
def mock_redis():
    """Auto-mock Redis for all tests to avoid external dependencies."""
    with patch('redis.asyncio.from_url') as mock:
        mock_client = MagicMock()
        mock_client.get = MagicMock(return_value=None)
        mock_client.setex = MagicMock(return_value=True)
        mock_client.delete = MagicMock(return_value=1)
        mock_client.ping = MagicMock(return_value=True)
        mock_client.pubsub = MagicMock(return_value=MagicMock())
        mock.return_value = mock_client
        yield mock

@pytest.fixture
def mock_supabase():
    """Provide mock Supabase client."""
    with patch('src.utils.supabase_client.create_client') as mock:
        client = MagicMock()
        client.table = MagicMock(return_value=MagicMock(
            select=MagicMock(return_value=MagicMock(
                eq=MagicMock(return_value=MagicMock(
                    execute=MagicMock(return_value={'data': []})
                ))
            ))
        ))
        mock.return_value = client
        yield client

@pytest.fixture
def sample_signal():
    """Provide a valid sample trading signal."""
    return {
        'symbol': 'EURUSD',
        'entry': 1.0850,
        'sl': 1.0800,
        'tp': 1.0950,
        'side': 'BUY',
        'size': 0.01,
        'timeframe': '1H'
    }

@pytest.fixture
def mock_metaapi():
    """Mock MetaApi client for trading tests."""
    with patch('src.adapters.meta_api.MetaApi') as mock:
        instance = MagicMock()
        instance.connect = MagicMock(return_value=True)
        instance.get_account = MagicMock(return_value=MagicMock(
            get_positions=MagicMock(return_value=[]),
            place_order=MagicMock(return_value={'orderId': '12345'})
        ))
        mock.return_value = instance
        yield instance
```

### Test Naming Conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| `test_<function>_<scenario>` | `test_calculate_position_valid_input` | Unit tests |
| `test_<function>_raises_<exception>` | `test_execute_trade_raises_timeout` | Error cases |
| `test_<function>_returns_<type>` | `test_fetch_data_returns_dict` | Return type verification |
| `test_<component>_<behavior>` | `test_guardrail_veto_high_risk` | Component behavior |

### Running Python Tests

```bash
# All tests
PYTHONPATH=/workspace pytest tests/ -v

# Specific test file
PYTHONPATH=/workspace pytest tests/test_ai_brain.py -v

# Specific test method
PYTHONPATH=/workspace pytest tests/test_ai_brain.py::TestAIBrain::test_evaluate_signal -v

# With coverage (if configured)
PYTHONPATH=/workspace pytest tests/ --cov=src --cov-report=html

# Async tests only
PYTHONPATH=/workspace pytest tests/ -v -k "async"
```

**Current test status:** 11 tests passing (from AGENTS.md context)

## Frontend Testing Patterns

### Test File Structure

**Location:** `frontend/src/**/*.test.tsx` (co-located with components)  
**Naming:** `<ComponentName>.test.tsx`  
**Total:** 3 test files found

```
frontend/src/
├── components/
│   ├── SignalInspector.tsx
│   ├── SignalInspector.test.tsx    # Co-located test
│   └── RiskDashboard.test.tsx
├── lib/
│   └── utils.test.ts
└── ...
```

### Vitest Configuration

**Config in `frontend/vitest.config.ts`:**

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',        // Browser-like environment
    globals: true,              // Enable global test APIs (describe, it, expect)
    setupFiles: './src/test/setup.ts',  // Setup file for test utilities
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),  // Path alias matching tsconfig
    },
  },
});
```

### Component Test Pattern

**Testing React components with hooks:**

```typescript
// src/components/SignalInspector.test.tsx
/** @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SignalInspector } from './SignalInspector';

// Helper to create isolated QueryClient for each test
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,  // Don't retry failed queries in tests
      staleTime: 0,
    },
  },
});

describe('SignalInspector', () => {
  const mockSignal = {
    id: '123',
    symbol: 'EURUSD',
    entry: 1.0850,
    side: 'BUY' as const,
    status: 'pending' as const,
  };
  
  const mockOnApprove = vi.fn();
  const mockOnReject = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders signal symbol and entry price', () => {
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <SignalInspector 
          signal={mockSignal}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      </QueryClientProvider>
    );
    
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.getByText('1.0850')).toBeInTheDocument();
  });

  it('calls onApprove when approve button clicked', async () => {
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <SignalInspector 
          signal={mockSignal}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      </QueryClientProvider>
    );
    
    const approveButton = screen.getByRole('button', { name: /approve/i });
    fireEvent.click(approveButton);
    
    await waitFor(() => {
      expect(mockOnApprove).toHaveBeenCalledWith('123');
    });
  });

  it('displays veto reason when signal is vetoed', () => {
    const queryClient = createTestQueryClient();
    const vetoedSignal = { ...mockSignal, status: 'vetoed' as const, vetoReason: 'High risk' };
    
    render(
      <QueryClientProvider client={queryClient}>
        <SignalInspector 
          signal={vetoedSignal}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      </QueryClientProvider>
    );
    
    expect(screen.getByText('High risk')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /approve/i })).toBeDisabled();
  });
});
```

### Testing with React 19 createRoot

**Pattern for React 19 compatibility:**

```typescript
import { createRoot } from 'react-dom/client';
import { act } from 'react';

it('renders without crashing', async () => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  
  const root = createRoot(container);
  
  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <SignalInspector signal={mockSignal} onApprove={vi.fn()} onReject={vi.fn()} />
      </QueryClientProvider>
    );
  });
  
  expect(container.textContent).toContain('EURUSD');
  
  // Cleanup
  root.unmount();
  container.remove();
});
```

### Running Frontend Tests

```bash
# From frontend directory
cd frontend

# All tests
npx vitest run

# Watch mode
npx vitest

# Specific test file
npx vitest run src/components/SignalInspector.test.tsx

# With UI
npx vitest --ui
```

**Current test status:** 1 pre-existing failure in tradingMetrics.test.ts (to ignore per AGENTS.md)

## Test Coverage Requirements

### Current Coverage

**Backend:** 11 tests passing  
**Frontend:** Vitest configured but specific coverage thresholds not defined

### Recommended Coverage Areas

**Critical paths requiring tests:**

1. **API Layer** (`tests/test_api.py`)
   - Webhook validation (all required fields)
   - Rate limiting behavior
   - Authentication middleware
   - Error response formatting

2. **Execution Engine** (`tests/test_execution_engine.py`)
   - Position size calculations
   - Trade execution flow
   - Kill switch functionality
   - Paper trading vs live trading modes
   - MetaApi timeout handling

3. **AI/ML Components** (`tests/test_ai_brain.py`, `tests/test_guardrails.py`)
   - Trading Council consensus logic
   - Signal quality scoring
   - Veto conditions
   - LLM error handling

4. **Risk Management** (`tests/test_guardrails.py`)
   - Maximum position size enforcement
   - Daily drawdown limits
   - Kill switch per account
   - Margin requirement checks

5. **Data Persistence**
   - Supabase signal logging
   - Redis queue operations
   - State synchronization

## CI/CD Integration

**Current State:** No CI/CD workflows configured  
**No `.github/workflows/` directory found**

### Recommended CI Setup

```yaml
# .github/workflows/test.yml (recommended)
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: PYTHONPATH=/workspace pytest tests/ -v

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: cd frontend && npm ci
      - run: cd frontend && npx vitest run
```

## Testing Best Practices

### Do's

1. **Use `PYTHONPATH=/workspace`** when running Python tests (matches production)
2. **Mock external services** (Redis, MetaApi, Supabase, OpenAI) in unit tests
3. **Use `AsyncMock`** for all async dependencies
4. **Set autouse fixtures** for environment setup in `conftest.py`
5. **Test error paths** not just happy paths
6. **Use `act()`** for all state updates in React 19 component tests
7. **Create isolated QueryClient** instances for each test

### Don'ts

1. **Don't run tests without mocks** against real MetaApi or live trading accounts
2. **Don't share mutable state** between tests (use fresh fixtures)
3. **Don't skip tearDown** if resources are allocated in setUp
4. **Don't test implementation details** - test behavior and outputs
5. **Don't use real timers** - use vitest fake timers for time-dependent code
6. **Don't ignore async warnings** - always await promises in tests

## Debugging Failed Tests

### Python

```bash
# Verbose output
PYTHONPATH=/workspace pytest tests/test_specific.py -vvv

# Stop at first failure
PYTHONPATH=/workspace pytest tests/ -x

# With logging visible
PYTHONPATH=/workspace pytest tests/ -v --log-cli-level=DEBUG

# PDB on failure
PYTHONPATH=/workspace pytest tests/ --pdb
```

### Frontend

```bash
# Verbose mode
cd frontend && npx vitest run --reporter=verbose

# Debug specific test
cd frontend && npx vitest run --reporter=verbose src/components/SignalInspector.test.tsx

# With browser-like debugging
cd frontend && npx vitest --ui
```

---

*Testing analysis: 2025-01-09*
