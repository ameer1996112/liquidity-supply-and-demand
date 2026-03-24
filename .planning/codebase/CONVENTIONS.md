# CONVENTIONS.md — Code Conventions & Patterns

## Language & Style

### Python
- **Target**: Python 3.11+
- **Linter**: `ruff check src/ config/ tests/` (98 pre-existing warnings; treat new violations as errors)
- **Type hints**: Consistently used throughout — `from typing import Any, Literal`, Pydantic models for schema
- **Docstrings**: Module-level triple-quoted strings on most key files; function docstrings on public APIs
- **Import order**: stdlib → third-party → local (enforced by ruff)

### TypeScript / Frontend
- **Strict mode**: `tsconfig.json` strict
- **ESLint**: `eslint.config.mjs` (Next.js recommended rules)
- **Component naming**: PascalCase for components, camelCase for hooks/utils
- **File naming**: kebab-case for routes and directories, PascalCase for component files

---

## Python Code Patterns

### Settings Access
```python
# Always use the cached factory — never instantiate Settings() directly
from config import get_settings
s = get_settings()
redis_url = s.redis_url
```

### Logger Creation
```python
from config.logging_config import get_logger
logger = get_logger("trinity.module_name")
# Namespaced with "trinity." prefix throughout
```

### Error Handling Philosophy
- **Guard rails**: return `str` reason (not None) on rejection, `None` on pass
  ```python
  def check(self, signal: dict) -> str | None:
      if condition_fails:
          return "Rejection reason string"
      return None  # pass
  ```
- **API endpoints**: raise `HTTPException` with explicit status codes; use `RequestValidationError` for schema errors
- **Non-fatal errors**: `logger.warning(...)` + continue (esp. for non-critical adapters like Discord)
- **Fatal errors at startup**: `raise RuntimeError(...)` — crash fast rather than accept requests

### FastAPI Router Pattern
```python
from fastapi import APIRouter
router = APIRouter()

@router.get("/endpoint")
def handler():
    ...

# In api.py:
from src.api_module import router as module_router
app.include_router(module_router)
```

### Async vs Sync
- API endpoints: mix of `async def` (for I/O heavy) and `def` (for CPU-bound / sync calls)
- WebSocket handler: `async def`
- Worker: mostly sync with threading for background tasks

### Dependency Injection (FastAPI)
```python
async def get_webhook_payload(
    request: Request,
    x_webhook_secret: str | None = Header(None),
) -> dict[str, Any]:
    validate_webhook_secret(request, x_webhook_secret)
    ...
```

### Signal Validation (shared API + Worker)
```python
# Core validator in src/core/signal.py — used by both API and Worker
from src.core.signal import validate_webhook_payload
validated = validate_webhook_payload(raw_dict)
```

### Settings Feature Flags Pattern
Feature flags are checked inline:
```python
s = get_settings()
if s.ml_guardian_enabled:
    result = ml_guardian.evaluate(signal)
if s.ai_filter_enabled:
    result = ai_guardian.evaluate(signal)
```

---

## Naming Conventions

### Python
| Entity | Convention | Example |
|--------|-----------|---------|
| Module | `snake_case` | `api_risk_monitor.py` |
| Class | `PascalCase` | `PineGuardian`, `RiskEngine` |
| Function | `snake_case` | `validate_webhook_payload` |
| Private | `_underscore` prefix | `_fail_fast_config()`, `_build_cors_origins()` |
| Constants | `UPPER_SNAKE_CASE` | `_RATE_LIMIT_AVAILABLE` |
| Logger name | `trinity.{module}` | `trinity.api`, `trinity.worker` |
| Guard rail result | `str \| None` | `None` = pass, `"reason"` = reject |

### TypeScript / React
| Entity | Convention | Example |
|--------|-----------|---------|
| Component | `PascalCase` | `TradingHealthWidget` |
| Hook | `useCamelCase` | `useSignalFeed` |
| Utility | `camelCase` | `formatPnl` |
| Type/Interface | `PascalCase` | `SignalPayload` |
| Route directory | `kebab-case` | `execution-quality/` |

---

## Configuration Patterns

### Environment Variables
- Required: `SUPABASE_URL`, `REDIS_URL`
- Optional with fallbacks documented in `settings.py` with Field descriptions
- Pydantic `AliasChoices` handles backward-compatible renames:
  ```python
  validation_alias=AliasChoices("LIVE_TRADING", "LIVE_TRADING_ENABLED")
  ```

### Feature Toggle Hierarchy
1. `.env` hard setting (restart required)
2. DB override via `ai_mode_toggles` table (runtime toggle)
3. Per-signal payload flags (e.g., `force_paper`)

---

## Guard Rail Return Contract

All guard rail classes in `src/core/guard_rails/`:
```python
class SomeguardGuard:
    def check(self, signal: dict) -> str | None:
        """Returns None (pass) or rejection reason string."""
```

The worker iterates guards sequentially; first non-None result rejects the signal.

---

## Observer Registration

Worker pipeline observers registered in `src/core/observers/`:
```python
# base.py pattern
class SignalObserver:
    def on_signal_received(self, signal: dict) -> None: ...
    def on_signal_executed(self, signal: dict, result: dict) -> None: ...
    def on_signal_rejected(self, signal: dict, reason: str) -> None: ...
```

---

## Supabase Access Pattern

```python
# Singleton client via module-level import
from src.adapters.supabase import supabase

# All DB ops through supabase table API
result = supabase.table("trading_signals").insert(row).execute()
resp = supabase.table("alerts").select("*").eq("status", "active").execute()
data = resp.data or []
```

---

## Frontend Conventions

### API Calls
- All backend calls go through lib utilities in `frontend/src/lib/`
- React Query for server state with appropriate stale times
- Direct Supabase subscriptions for real-time feeds

### Components
- Radix UI primitives as base layers
- TailwindCSS 4 utility classes
- `clsx` + `tailwind-merge` for conditional classes:
  ```tsx
  import { cn } from "@/lib/utils"
  className={cn("base-class", condition && "conditional-class")}
  ```

### Data Fetching Hooks
- Custom hooks in `frontend/src/hooks/` wrap React Query
- Named `use[Domain][Action]` e.g., `useSignals`, `usePortfolio`
