# CONVENTIONS.md — Code Style & Patterns

## Backend (Python)

### Style & Linting
- **Linter:** Ruff (`ruff check src/ config/ tests/`)
- **98 pre-existing warnings** at baseline (not zero-warning)
- No `pyproject.toml` with ruff config found — likely using defaults
- Type hints used throughout (Pydantic models enforce types at runtime)

### Code Style
- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- Pydantic `BaseModel` for all data transfer objects
- `pydantic-settings` `BaseSettings` for configuration (`config/settings.py`)
- `@lru_cache` on `get_settings()` — config is loaded once per process

### Patterns

**Adapter Pattern**
All external services are wrapped in adapters under `src/adapters/`:
```python
# Example pattern
class SupabaseAdapter:
    def __init__(self, settings: Settings):
        self.client = create_client(settings.supabase_url, settings.supabase_key)
    
    async def get_signals(self, limit: int = 100) -> list[dict]:
        ...
```

**Guard Rail Pattern**
Guards are discrete, independently-fail-open modules:
```python
# Guards return (allow: bool, reason: str, metadata: dict)
async def check_staleness(signal: Signal) -> GuardResult:
    if signal_age > MAX_AGE:
        return GuardResult(allow=False, reason="Signal too old")
    return GuardResult(allow=True)
```

**FastAPI Router Pattern**
Sub-routers are defined as modules and mounted in `api.py`:
```python
# In api_risk.py
router = APIRouter(prefix="/risk", tags=["risk"])

@router.get("/summary")
async def get_risk_summary():
    ...

# In api.py
from src.api_risk import router as risk_router
app.include_router(risk_router)
```

### Error Handling
- Guards fail open on unexpected errors (allow trade to proceed)
- Adapters propagate exceptions upward (caller handles)
- API endpoints return structured JSON errors with status codes
- Worker catches per-signal exceptions and logs, continues processing

### Configuration Access
```python
from config.settings import get_settings
settings = get_settings()  # Cached via @lru_cache — restart to pick up .env changes
```

### Async Patterns
- FastAPI async route handlers (`async def`)
- `asyncio.gather()` for parallel async operations
- APScheduler for background recurring tasks (broker reconciliation, etc.)
- MetaAPI SDK is async-native

---

## Frontend (TypeScript / React)

### Style & Linting
- **Linter:** ESLint with `eslint-config-next` (`frontend/eslint.config.mjs`)
- **TypeScript:** Strict mode
- Pre-existing warnings/errors in baseline
- Zero-warning goal was target of Phase 3 work

### Code Style
- `PascalCase` for React components
- `camelCase` for variables, functions, props
- `kebab-case` for CSS class names (Tailwind utilities)
- `UPPER_SNAKE_CASE` for constants

### Patterns

**React Query for Server State**
```typescript
// Preferred data fetching pattern
const { data, isLoading, error } = useQuery({
    queryKey: ['signals', filters],
    queryFn: () => fetchSignals(filters),
    refetchInterval: 5000,  // polling for real-time updates
});
```

**Supabase Realtime Subscriptions**
```typescript
// Real-time signal feed
useEffect(() => {
    const channel = supabase.channel('signals')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'signals' }, (payload) => {
            // handle real-time update
        })
        .subscribe();
    return () => supabase.removeChannel(channel);
}, []);
```

**Component Structure**
```tsx
// Co-located test files: Component.tsx + Component.test.tsx
// Props typed with TypeScript interfaces
interface TraceTableProps {
    traces: TraceRecord[];
    isLoading: boolean;
}

export function TraceTable({ traces, isLoading }: TraceTableProps) { ... }
```

**Domain-Driven Models**
- `frontend/src/domain/` contains pure TypeScript business logic
- No React dependencies in domain — testable in isolation
- `frontend/src/domain/metrics/tradingMetrics.ts` — trade metric calculations

### Radix UI + shadcn/ui Component Pattern
- Raw Radix primitives are wrapped in shadcn/ui components
- Components are in `frontend/src/components/ui/` (shadcn generated)
- Custom components use shadcn primitives and Tailwind classes

### API Client
- Backend API called via HTTP from frontend React Query hooks
- `frontend/src/lib/` contains API client utilities
- `NEXT_PUBLIC_API_URL` configures API base URL

---

## Configuration Boundary Rules

**Critical: Backend vs Frontend secrets**
| Variable Type | Backend .env | Frontend .env |
|---------------|-------------|---------------|
| `NEXT_PUBLIC_*` | ❌ Not needed | ✅ Safe (baked at build) |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ Backend only | ❌ NEVER |
| `REDIS_URL` | ✅ Backend only | ❌ NEVER |
| `META_API_TOKEN` | ✅ Backend only | ❌ NEVER |
| `WEBHOOK_SECRET` | ✅ Backend only | ❌ NEVER |
