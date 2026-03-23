# CONVENTIONS.md — Code Style & Patterns

## Python Code Style

### Linting
- **Ruff** for linting: `ruff check src/ config/ tests/`
- 98 pre-existing warnings accepted as baseline
- No formatter (black/autopep8) specified; ruff-only

### Naming Conventions
- **Modules**: `snake_case` (e.g., `risk_engine.py`, `pine_guardian.py`)
- **Classes**: `PascalCase` (e.g., `PineGuardian`, `RiskEngine`, `AIGuardian`)
- **Functions/methods**: `snake_case` (e.g., `validate_signal`, `get_settings`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `TRADING_KILL_SWITCH`, `SIGNAL_TRANSPORT`)
- **Private helpers**: leading underscore `_helper_fn()`

### Configuration Pattern
```python
# Always use get_settings() — cached singleton
from config.settings import get_settings

settings = get_settings()  # @lru_cache — same instance always returned

# Feature flags are plain bool settings
if settings.ai_filter_enabled:
    result = await ai_guardian.validate(signal)
```

### Guard Rail Return Pattern
Each guard returns a result object with a decision field:
```python
# Pattern: APPROVE | REJECT | WARNING with reason
class GuardResult:
    decision: Literal["APPROVE", "REJECT", "WARNING"]
    reason: str
    metadata: dict
```

### FastAPI Router Pattern
API endpoints are split into router modules and mounted in `api.py`:
```python
# Each src/api_*.py exports: router = APIRouter(prefix="/...", tags=["..."])
from src.api_positions import router as positions_router
app.include_router(positions_router)
```

### Supabase Access Pattern
All database operations go through `src/adapters/supabase.py`:
```python
# No raw SQL in business logic — all through supabase adapter
from src.adapters.supabase import SupabaseAdapter
adapter = SupabaseAdapter()
signals = await adapter.get_signals(limit=100)
```

### Async vs Sync
- FastAPI endpoints: `async def`
- Background services: mix of `async def` and threading
- Supabase SDK calls: synchronous (wrapped in async context)
- MetaAPI calls: async (HTTP adapter)

## Error Handling

### Guard Rail Failures
Guards fail-safe: if a guard raises an exception, it defaults to APPROVE (trading continues):
```python
try:
    result = guard.validate(signal)
except Exception as e:
    logger.error(f"Guard {guard.__class__.__name__} failed: {e}")
    result = GuardResult(decision="APPROVE", reason="guard_error_fallthrough")
```

### API Error Responses
FastAPI uses standard HTTP status codes:
```python
from fastapi import HTTPException
raise HTTPException(status_code=422, detail="Invalid signal payload")
```

### Logging Convention
```python
import logging
logger = logging.getLogger(__name__)

# Structured logging with context
logger.info("Signal approved", extra={"signal_id": signal.id, "symbol": signal.symbol})
logger.warning("ML Guardian below threshold", extra={"confidence": 0.45})
logger.error("MetaAPI execution failed", exc_info=True)
```

## TypeScript / Frontend Patterns

### Component Style
- **App Router** with mix of Server Components and Client Components (`"use client"`)
- Client components fetch via `fetch()` to `localhost:8000/api/...`
- Server components use direct Supabase client

### Data Fetching
```typescript
// React Query for API data
import { useQuery } from "@tanstack/react-query";

const { data, isLoading } = useQuery({
  queryKey: ["signals"],
  queryFn: () => fetch("/api/signals").then(r => r.json()),
  refetchInterval: 5000,  // 5s polling
});
```

### Type Safety
- All domain types in `frontend/src/types/`
- Domain logic in `frontend/src/domain/`
- Hooks in `frontend/src/hooks/` (e.g., `useSignals`, `usePositions`)

### Supabase Realtime (Frontend)
```typescript
// Realtime subscription pattern
const channel = supabase
  .channel("signals")
  .on("postgres_changes", { event: "*", schema: "public", table: "signals" }, 
    (payload) => handleUpdate(payload))
  .subscribe();
```

## Environment Variables Pattern

- All env vars documented in `.env.example` (11KB)
- Required vars checked on startup (`SUPABASE_URL`, `REDIS_URL`)
- AI/ML guardrails (`AI_FILTER_ENABLED`, `ML_GUARDIAN_ENABLED`, `TRINITY_ENABLED`) can be disabled for local dev
- Feature flags follow the pattern `FEATURE_ENABLED=true/false`
- Secrets use `SecretStr` in Pydantic settings

## Git / Commit Convention

- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
- Planning artifacts use: `docs: map existing codebase`
- Feature work: `feat(worker): add staleness guard`

## Module Organization Principles

1. **Adapters** (`src/adapters/`) — only know about external services, no business logic
2. **Core** (`src/core/`) — domain models, guard rails, signal transport; no direct I/O
3. **Services** (`src/services/`) — business services that coordinate adapters + core
4. **AI** (`src/ai/`) — ML and LLM logic; may call external LLM APIs
5. **API routers** (`src/api_*.py`) — thin HTTP layer; delegates to services/adapters
6. **Worker** (`src/worker.py`) — orchestrates the full pipeline; reads from Redis

## Settings Anti-Patterns (Gotchas)

- **DO NOT** import `Settings` directly — always use `get_settings()` for the cached instance
- **DO NOT** mutate settings at runtime — they're frozen after first load
- **DO NOT** expect `.env` changes to take effect without process restart (`@lru_cache`)
