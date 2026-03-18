# Coding Conventions

**Analysis Date:** 2026-03-18

## Naming Patterns

**Files:**
- Python files: `snake_case` — `risk_engine.py`, `execution_engine.py`, `account_orchestrator.py`
- Python modules: `snake_case` with `_observer`, `_adapter`, `_service` suffixes — `auditor_observer.py`, `metaapi_adapter.py`, `alert_service.py`
- React/TypeScript components: `PascalCase` — `AccountCard.tsx`, `SignalInspector.tsx`, `AnalyticsTab.tsx`
- React/TypeScript hooks: `use` prefix + `PascalCase` — `useAccountsSupabase.ts`, `useTradingSignals.ts`, `usePortfolioRisk.ts`
- Test files: `*.test.ts` or `*.test.tsx` for frontend; `test_*.py` or `*_test.py` for backend — `tradingMetrics.test.ts`, `test_api.py`

**Functions:**
- Python: `snake_case` — `calculate_max_position_size()`, `get_account_performance()`, `extract_currencies()`
- TypeScript: `camelCase` for utility functions, `PascalCase` for components/types — `fetchPairStats()`, `computeTradeKpis()`
- Private/internal Python functions: `_leading_underscore_snake_case` — `_get_cached_balance()`, `_get_supabase()`, `_payload_hash()`
- Factory/builder functions: `create_*` prefix — `create_correlation_manager_from_settings()`, `create_market_adapter_from_settings()`

**Variables:**
- Python: `snake_case` — `account_balance`, `risk_percent`, `symbol_overrides`, `correlation_id`
- TypeScript: `camelCase` — `accountName`, `riskPercent`, `symbolOverrides`, `correlationId`
- Constants: `UPPER_SNAKE_CASE` — `DEFAULT_MAX_DAILY_LOSS_PCT`, `BALANCE_CACHE_TTL`, `TCA_LATENCY_THRESHOLD_MS`
- Cache/state globals: `_leading_underscore` to indicate module-level — `_balance_cache`, `_paper_trader`, `_BALANCE_CACHE_TTL`

**Types & Classes:**
- Python Pydantic models: `PascalCase` ending in model purpose — `TradeRiskParams`, `RiskCheckResult`, `AccountResponse`, `EntryWebhookPayload`
- Python enum classes: `PascalCase` — `RiskRejectionReason`, `AssetClass`, `RejectionReason`
- Python dataclasses: `PascalCase` — `AccountPerformance`, `AllocationRecommendation`, `TradeEvent`
- TypeScript interfaces: `PascalCase` with optional `*Props`, `*Api` suffix — `AnalyticsTabProps`, `AccountComparisonApi`, `PairStats`
- TypeScript types: `camelCase` or domain-specific — `TradingMode`, `FilterTab`, `LosingStreak`

## Code Style

**Formatting:**
- Python: 4-space indentation (PEP 8 standard)
- TypeScript/React: 2-space indentation (Next.js/Prettier standard)
- Line length: Python ~100-120 chars (long expressions acceptable for readability), TypeScript ~80-100 chars
- Trailing commas in multiline structures (Python/TS)

**Linting:**
- Frontend: ESLint with Next.js core-web-vitals + TypeScript configuration (`frontend/eslint.config.mjs`)
  - Uses `eslint-config-next` core-web-vitals and TypeScript presets
  - Run: `npm run lint` (from frontend directory)
- Backend: No formal linter configured, but follows PEP 8 conventions
  - Imports use `from __future__ import annotations` for forward compatibility
  - Type hints required for function signatures
  - Logger names use `__name__` convention: `logger = logging.getLogger(__name__)`

## Import Organization

**Order (Python):**
1. Future imports: `from __future__ import annotations`
2. Standard library: `import logging`, `from typing import ...`, `from datetime import ...`
3. Third-party: `import fastapi`, `from pydantic import ...`, `import requests`
4. Local: `from src.adapters.supabase_api import ...`, `from config import ...`

**Order (TypeScript/React):**
1. React imports: `import { useState, useMemo } from 'react'`
2. Third-party hooks/utilities: `import { useQuery } from '@tanstack/react-query'`
3. Icon libraries: `import { TrendingUp, TrendingDown } from 'lucide-react'`
4. Local components: `import { Button } from '@/components/ui/button'`
5. Local hooks: `import { useAccountsSupabase } from '@/hooks/useAccountsSupabase'`
6. Local types/interfaces: `import type { TradingSignal } from '@/types/trading'`
7. Utilities/helpers: `import { cn } from '@/lib/utils'`

**Path Aliases:**
- TypeScript: `@/*` → `./src/*` (defined in `frontend/tsconfig.json`)
  - Use `@/components/...`, `@/hooks/...`, `@/lib/...`, `@/types/...` throughout codebase
  - No relative imports (`../../..`); always use alias paths

## Error Handling

**Python Patterns:**
- Use `try/except` blocks for recoverable failures (network calls, database queries)
- Bare `except` with `# noqa: BLE001` for generic exception handling when recovering gracefully
- Log errors with `logger.error()` or `logger.warning()` with context
- Return graceful defaults or empty collections instead of raising in service/adapter layers
- Example from `api_webhook_read.py`:
  ```python
  try:
      resp = q.execute()
      signals = resp.data or []
      return {"signals": signals, "count": len(signals)}
  except Exception as e:
      logger.warning("Failed to fetch recent signals: %s", e)
      return {"signals": [], "count": 0}
  ```

**TypeScript/React Patterns:**
- Use `.then().catch()` or `try/catch` in async functions
- Log errors but don't crash the component; show user-facing error state
- Provide fallback UI: loading states, empty states, error boundaries
- Example from `AnalyticsTab.tsx`:
  ```typescript
  const { data, isLoading, error } = useQuery({
    queryKey: ['account-analytics-pairs', accountName],
    queryFn: () => fetchPairStats(accountName),
    staleTime: 60_000,
  });
  // Later: show loading, error, or empty state based on above
  ```

**Risk-Critical Validation:**
- Database validation uses Pydantic models with Field constraints
- Example from `signal.py`:
  ```python
  class EntryWebhookPayload(BaseModel):
      symbol: str = Field(..., min_length=1, description="Instrument symbol")
      entry: float = Field(..., description="Entry price")
  ```
- Custom validators with `@model_validator(mode="after")`

## Logging

**Framework:** Python's built-in `logging` module

**Configuration:**
- Logger: `logger = logging.getLogger(__name__)` at module top
- Custom logger in some modules: `from config.logging_config import get_logger` → `logger = get_logger("trinity.logic")`
- Log levels used:
  - `logger.info()`: Important state changes (balance cache updated, position saved)
  - `logger.warning()`: Recoverable errors (fetch failed, retrying)
  - `logger.error()`: Critical errors (order submission failed)
  - `logger.debug()`: Low-level details (cache hits, decision branches)

**Patterns:**
- Always include context: `logger.error("order submission failed: %s", error_object)`
- Format structured data inline: `logger.info("Balance cache updated: balance=%.2f equity=%.2f", bal, eq)`
- No print statements; use logging exclusively
- Example from `logic.py`:
  ```python
  logger.debug("Balance cache hit: balance=%.2f equity=%.2f (age=%.1fs)",
               cached_bal, cached_eq, now - _balance_cache["fetched_at"])
  logger.info("Balance cache updated: balance=%.2f equity=%.2f", bal, eq)
  ```

## Comments

**When to Comment:**
- **Always**: Non-obvious algorithms or domain logic (position sizing formulas, risk calculations)
- **Always**: Design decisions with rationale (why cache instead of fetch, why skip external call on hot path)
- **When**: Complex conditional logic or multiple validation layers
- **Avoid**: Obvious code (e.g., "increment counter by 1" comments)

**Style:**
- Single-line comments: `# Comment text` (Python), `// Comment text` (TypeScript)
- Multi-line docstrings: Triple quotes for Python functions/classes, TSDoc for TypeScript
- Comments above code block (not inline after code)

**Examples from codebase:**
```python
# OPT-2 (latency): Balance cache to avoid an HTTP round-trip on every live trade.
# Balance/equity are re-fetched from broker only when the cached value is older than
# BALANCE_CACHE_TTL seconds. This removes ~100-300ms per signal on the hot path.

# Per-symbol overrides from DB (if provided and enabled)
if symbol_overrides and symbol_overrides.get("enabled", True):
    # ...
else:
    # Hardcoded fallback for unknown symbols
    # IMPORTANT: Check indices and crypto FIRST before forex
```

**JSDoc/TSDoc:**
- Used sparingly in TypeScript; primarily for hook return types and complex utilities
- Example from `useAccountsSupabase.ts`:
  ```typescript
  export interface AddAccountStrategyInput {
    account_name: string;
    strategy_type?: string;
    // ...
  }
  ```

## Function Design

**Size:** Prefer functions < 50 lines
- Helpers and factories can be longer (75-100 lines) for context
- Observer/adapter classes can be 100-200 lines with clear sections
- Use helper functions to break up logic

**Parameters:**
- Python: positional + keyword-only after `*` separator
- TypeScript: props object pattern for components, individual params for utilities
- Always provide type hints: `def function(param: Type) -> ReturnType:`
- Default parameters for optional settings: `lookback_days: int = 30`

**Return Values:**
- Single return type per function (no inconsistent None vs empty list)
- Use Pydantic models for complex returns: `-> AccountPerformance` not `-> Dict`
- Observable pattern: observers have `-> None` return; events are passed via callback

**Example from `account_orchestrator.py`:**
```python
def get_account_performance(
    self,
    account_name: str,
    lookback_days: int = 30
) -> Optional[AccountPerformance]:
    """Calculate performance metrics for an account.

    Args:
        account_name: Name of the account
        lookback_days: Days to look back for metrics

    Returns:
        AccountPerformance object or None if account not found.
    """
```

## Module Design

**Exports:** Explicit exports from each module
- Python: No wildcard imports (`from module import *`); always named imports
- TypeScript components: Default export for single component, named exports for utilities
- Public vs private: `_leading_underscore` for internal/helper functions

**Barrel Files:**
- Not used extensively; most imports are direct from module files
- Example: `src/adapters/__init__.py` exists but minimal re-exports

**Pattern: Classes with Single Responsibility**
- `ExecutionEngine`: Wraps adapter calls with TCA metrics
- `RiskGuardian`: Guards trades against account limits
- `AuditorObserver`: Logs events to audit trail
- Each has focused `__init__` taking dependencies: `def __init__(self, supabase_client, settings):`

**Pattern: Factory Functions**
- Create instances with full dependency injection
- Example: `create_correlation_manager_from_settings() -> CorrelationManager`
- Centralizes config reading logic

---

*Convention analysis: 2026-03-18*
