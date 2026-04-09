# Coding Conventions

**Analysis Date:** 2025-01-09

## Overview

This document defines the coding standards and conventions for the Trading System codebase, which consists of a Python FastAPI backend and a Next.js TypeScript frontend.

## Python Backend Conventions

### Type Hints

**Mandatory typing on all function signatures:**

```python
from typing import Any, Dict, List, Optional, Tuple
from __future__ import annotations  # Enables postponed evaluation of annotations

def calculate_position_size(
    symbol: str,
    entry_price: float,
    risk_percent: float,
    account_balance: float
) -> Optional[float]:
    """Calculate position size based on risk parameters."""
    if not all([symbol, entry_price > 0, risk_percent > 0]):
        return None
    # ... implementation
```

**Key typing patterns observed:**
- Use `from typing import ...` imports (not modern `|` union syntax for compatibility)
- Always include `from __future__ import annotations` at top of files
- Return `Optional[T]` for functions that may return None
- Use `Dict[str, Any]` for configuration objects, not bare `dict`
- Type all function parameters, including `self` and `cls` where applicable

### Naming Conventions

| Construct | Pattern | Example |
|-----------|---------|---------|
| Functions | snake_case | `calculate_risk_adjusted_position()` |
| Variables | snake_case | `entry_price`, `stop_loss_pips` |
| Classes | PascalCase | `ExecutionEngine`, `TradingCouncil` |
| Constants | UPPER_SNAKE_CASE | `MAX_POSITION_SIZE`, `DEFAULT_TIMEFRAME` |
| Private methods | _leading_underscore | `_validate_signal()` |
| Protected methods | _leading_underscore | `_calculate_margin()` |
| Type aliases | PascalCase | `SignalDict = Dict[str, Any]` |

### Docstring Standards

**Google-style/NumPy-style docstrings with explicit sections:**

```python
def evaluate_signal_quality(
    signal: SignalDict,
    market_context: Optional[MarketContext] = None
) -> SignalQualityScore:
    """
    Evaluate the quality of a trading signal using multi-agent consensus.

    Args:
        signal: Dictionary containing signal parameters
            - symbol: Trading pair (e.g., 'EURUSD')
            - entry: Entry price
            - side: 'BUY' or 'SELL'
            - timeframe: Chart timeframe (e.g., '1H', '4H')
        market_context: Optional market regime information

    Returns:
        SignalQualityScore object with confidence rating and veto status

    Side Effects:
        - Logs evaluation results to Supabase
        - Sends Discord notification if signal is vetoed
        - Updates internal metrics counters

    Raises:
        ValueError: If signal is missing required fields
        ConnectionError: If LLM services are unavailable
    """
```

**Required sections for public functions:**
1. One-line description
2. `Args:` - Parameter descriptions with types implied
3. `Returns:` - Return value description
4. `Side Effects:` - External state changes (DB writes, notifications)
5. `Raises:` - Exceptions that callers should handle

### Import Organization

**Standard import order:**

```python
# 1. Future annotations (always first)
from __future__ import annotations

# 2. Standard library
import logging
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

# 3. Third-party libraries
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

# 4. Local imports (lazy loading pattern for circular dependency avoidance)
from src.core.config import get_settings
from src.utils.supabase_client import get_supabase_client
```

**Lazy Import Pattern (Critical for circular dependencies):**

```python
def _get_execution_engine():
    """Lazy import to avoid circular dependencies."""
    from src.services.execution_engine import ExecutionEngine
    return ExecutionEngine()

async def process_signal(signal_data: dict) -> bool:
    engine = _get_execution_engine()  # Import at call time, not module load
    return await engine.execute(signal_data)
```

### Code Organization Patterns

**Section dividers using Unicode box-drawing:**

```python
# ─────────────────────────────────────────────────────────────────────────────
# Configuration & Setup
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Type Definitions
# ─────────────────────────────────────────────────────────────────────────────

SignalDict = Dict[str, Any]
PositionSize = Tuple[float, float, float]  # (lots, margin, risk_amount)

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def evaluate_and_execute(signal: SignalDict) -> ExecutionResult:
    """Main entry point for signal processing."""
    # ...

# ─────────────────────────────────────────────────────────────────────────────
# Internal Implementation
# ─────────────────────────────────────────────────────────────────────────────

async def _validate_signal(signal: SignalDict) -> ValidationResult:
    """Internal validation logic."""
    # ...
```

### Error Handling

**Consistent error handling pattern:**

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def fetch_market_data(symbol: str) -> Optional[MarketData]:
    """Fetch with structured error logging."""
    try:
        response = await meta_api.get_symbol_price(symbol)
        return MarketData(response)
    except ConnectionError as e:
        logger.error(f"Connection failed for {symbol}: {e}")
        await _alert_ops_team(f"MetaApi connection error: {symbol}")
        return None
    except ValueError as e:
        logger.warning(f"Invalid symbol data: {symbol} - {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error fetching {symbol}: {e}")
        raise  # Re-raise unexpected errors
```

### Environment Variables

**Always use `get_settings()` singleton, never `os.environ` directly:**

```python
from src.core.config import get_settings

# CORRECT
settings = get_settings()
redis_url = settings.redis_url
api_key = settings.meta_api_key

# INCORRECT - Never do this
import os
api_key = os.environ["META_API_KEY"]  # Wrong!
```

**Config class pattern in `src/core/config.py`:**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    redis_url: str = "redis://localhost:6379"
    meta_api_key: str
    supabase_url: str
    supabase_key: str
    
    # Feature flags
    paper_trading: bool = True
    ai_filter_enabled: bool = True
    
@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

## Frontend (Next.js/TypeScript) Conventions

### ESLint Configuration

**ESLint rules defined in `frontend/eslint.config.mjs`:**

```javascript
export default [
  {
    files: ["src/**/*.{js,ts,tsx}"],
    rules: {
      // Disabled rules (intentionally relaxed)
      "@typescript-eslint/no-explicit-any": "off",           // Allow any for flexibility
      "@typescript-eslint/no-unused-vars": "off",           // Allow unused vars during dev
      "@typescript-eslint/no-unsafe-assignment": "off",     // Allow unsafe assignments
      "@typescript-eslint/no-unsafe-member-access": "off", // Allow unsafe member access
      "@typescript-eslint/no-unsafe-call": "off",         // Allow unsafe function calls
      "@typescript-eslint/no-unsafe-argument": "off",       // Allow unsafe arguments
      "@typescript-eslint/no-unsafe-return": "off",        // Allow unsafe returns
      "@typescript-eslint/require-await": "off",          // Don't require await in async
      "@typescript-eslint/restrict-template-expressions": "off", // Allow template expressions
      "react-hooks/exhaustive-deps": "off",               // Don't require exhaustive deps
    },
  },
];
```

**Key points:**
- Type safety rules are intentionally relaxed for rapid development
- Focus on functional correctness over strict type safety
- `react-hooks/exhaustive-deps` disabled to avoid noise during iteration

### TypeScript Patterns

**Strict typing encouraged despite relaxed ESLint:**

```typescript
// Prefer explicit types over any
interface SignalData {
  symbol: string;
  entry: number;
  side: 'BUY' | 'SELL';
  timeframe: string;
}

// Use proper React types
import { ReactNode, useState, useEffect } from 'react';

interface SignalInspectorProps {
  signal: SignalData;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  children?: ReactNode;
}
```

### Server vs Client Components

**Pattern for Next.js 14 App Router:**

```typescript
// Server Component (default) - for data fetching
// app/signals/page.tsx
import { SignalList } from '@/components/SignalList';
import { getSupabaseClient } from '@/lib/supabase';

export default async function SignalsPage() {
  const supabase = getSupabaseClient();
  const { data: signals } = await supabase
    .from('signals')
    .select('*')
    .order('created_at', { ascending: false });
  
  return <SignalList initialSignals={signals} />;
}

// Client Component - for interactivity
// components/SignalInspector.tsx
'use client';

import { useState } from 'react';

export function SignalInspector({ signal, onApprove }: SignalInspectorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <div>
      {/* Interactive UI here */}
    </div>
  );
}
```

**Rules:**
- Use Server Components by default (no directive needed)
- Add `'use client'` only when using hooks or browser APIs
- Pass initial data as props from Server to Client components
- Never mix async data fetching with client-side interactivity in one component

### Testing File Structure

```typescript
// src/components/SignalInspector.test.tsx
/** @vitest-environment jsdom */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SignalInspector } from './SignalInspector';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false } }
});

describe('SignalInspector', () => {
  it('renders signal details', () => {
    const queryClient = createTestQueryClient();
    const mockSignal = {
      symbol: 'EURUSD',
      entry: 1.0850,
      side: 'BUY' as const,
    };
    
    render(
      <QueryClientProvider client={queryClient}>
        <SignalInspector 
          signal={mockSignal}
          onApprove={vi.fn()}
          onReject={vi.fn()}
        />
      </QueryClientProvider>
    );
    
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
  });
});
```

## Git Commit Conventions

**Conventional Commits format:**

```
<type>: <description>

[optional body]

[optional footer]
```

**Types used in this project:**

| Type | Use for | Example |
|------|---------|---------|
| `feat` | New features | `feat: add kill switch per account` |
| `fix` | Bug fixes | `fix: correct PnL calculation for shorts` |
| `refactor` | Code restructuring | `refactor: consolidate risk dashboard` |
| `chore` | Maintenance | `chore: update dependencies` |
| `docs` | Documentation | `docs: add API endpoint examples` |
| `test` | Test changes | `test: add coverage for execution engine` |

**Commit message format:**

```bash
# Format: type(scope): description
# Or with ticket: DEV-XX: type(scope): description

feat(api): add webhook retry logic with exponential backoff

fix(worker): handle MetaApi timeout gracefully

refactor(guardrails): extract AI council to separate module

chore(deps): bump fastapi to 0.115.0

test(services): add unit tests for position sizing
```

**Branch naming:**

```
feature/DEV-XX-short-description
fix/DEV-XX-bug-name
refactor/DEV-XX-component-name
```

Examples:
- `feature/DEV-94-per-account-kill-switch`
- `fix/DEV-101-pnl-calculation-precision`
- `refactor/DEV-88-consolidate-risk-dashboard`

## Linting & Formatting

### Python

**ruff** is used for linting (98 pre-existing warnings currently ignored):

```bash
# Run linter
ruff check src/ config/ tests/

# Auto-fix issues
ruff check src/ --fix
```

**Key ruff settings (implied from patterns):**
- Line length: 100 characters
- Python version: 3.12+
- Enforce type hints on public functions
- No bare `except:` clauses
- No unused imports

### Frontend

**ESLint with Next.js rules:**

```bash
# Run linter (from frontend/ directory)
cd frontend && npm run lint

# Auto-fix
npx eslint src/ --fix
```

**No Prettier configuration found** - rely on ESLint auto-fix for formatting.

## Anti-Patterns to Avoid

1. **Don't use `os.environ` directly** - Always use `get_settings()`
2. **Don't import at module level if circular dependencies possible** - Use lazy import pattern
3. **Don't use bare `except:`** - Always catch specific exceptions
4. **Don't forget `from __future__ import annotations`** - Required for postponed evaluation
5. **Don't mix sync and async code** - MetaApi calls must be awaited
6. **Don't use `any` type in TypeScript unless necessary** - Prefer interfaces
7. **Don't poll Supabase in frontend** - Use realtime subscriptions
8. **Don't forget to check `paper_trading` flag** - Before any trade execution

---

*Convention analysis: 2025-01-09*
