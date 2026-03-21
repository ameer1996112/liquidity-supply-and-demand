# CONVENTIONS.md — Code Style & Patterns

## Python (Backend)

### Naming
- **Modules:** lowercase snake_case — `risk_engine.py`, `prop_guard.py`
- **Classes:** PascalCase — `Settings`, `EntryWebhookPayload`, `WorkerSubject`
- **Functions:** snake_case — `get_settings()`, `calculate_max_position_size()`
- **Constants:** UPPER_SNAKE — `MAX_OPEN_POSITIONS`, `ML_MIN_CONFIDENCE`
- **Private helpers:** leading underscore `_` — `_fetch_closed_signals()`, `_bucket()`
- **Logger naming:** `get_logger("trinity.[module]")` — e.g. `trinity.worker`, `trinity.api`

### FastAPI Router Pattern

Each API feature lives in its own `src/api_[name].py` file:

```python
# src/api_[feature].py
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

class MyResponse(BaseModel):
    field: str
    count: int

@router.get("/my-endpoint", response_model=MyResponse)
def get_something(
    period: str = Query("30d", pattern="^(24h|7d|30d|all)$"),
    mode: str = Query("LIVE"),
):
    ...
```

Then mounted in `src/api.py`:
```python
from src.api_[feature] import router as [feature]_router
app.include_router([feature]_router, prefix="/analytics")
```

### Pydantic Model Pattern

```python
# src/core/signal.py pattern
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EntryWebhookPayload(BaseModel):
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float
    size: float
    # Optional extras from TradingView
    bar_time: Optional[datetime] = None
    zone_id: Optional[str] = None
    rr_ratio: Optional[float] = None
    run_mode: Optional[str] = None
```

### Settings Pattern

```python
# Always use get_settings() — never instantiate Settings() directly
from config import get_settings
settings = get_settings()  # cached via @lru_cache

# After .env changes: process must restart (lru_cache persists)
```

### Error Handling

```python
# API: raise HTTPException with status code
from fastapi import HTTPException
raise HTTPException(status_code=400, detail="Signal rejected: RR ratio below minimum")

# Guard rails: return tuple (allowed: bool, reason: str)
def check_something(payload, settings) -> tuple[bool, str]:
    if bad:
        return False, "reason for rejection"
    return True, ""

# Worker: fail-open pattern — on infrastructure errors, allow trade
try:
    result = check_consecutive_losses(...)
except Exception:
    logger.warning("Guard check failed, failing open")
    return True, ""
```

### Logging Pattern

```python
from config.logging_config import get_logger
logger = get_logger("trinity.module_name")

logger.info("Signal received", extra={"symbol": symbol, "side": side})
logger.warning("Guard check failed — failing open")
logger.error("Trade execution failed", exc_info=True)
```

## Frontend (Next.js / TypeScript)

### Component Naming
- Files: PascalCase — `SignalCard.tsx`, `StatsTicker.tsx`
- Components: PascalCase matching filename — `export default function SignalCard`
- Feature components grouped in subdirectories: `components/dashboard/`, `components/analytics/`

### Hook Pattern

```typescript
// frontend/src/hooks/useFeature.ts
import { useQuery } from "@tanstack/react-query"

export function useFeature(options?: { period?: string }) {
  return useQuery({
    queryKey: ["feature", options?.period],
    queryFn: async () => {
      const url = `${process.env.NEXT_PUBLIC_API_URL}/feature?period=${options?.period ?? "30d"}`
      const res = await fetch(url)
      if (!res.ok) throw new Error("Failed to fetch feature data")
      return res.json()
    },
    refetchInterval: 30_000,  // poll every 30s
  })
}
```

### Page Pattern

```typescript
// frontend/src/app/[route]/page.tsx
"use client"
import { useFeature } from "@/hooks/useFeature"

export default function FeaturePage() {
  const { data, isLoading, error } = useFeature()
  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error loading data</div>
  return <div>{/* render data */}</div>
}
```

### Styling
- Tailwind CSS v4 utility classes throughout
- Dark theme — slate/zinc/neutral color palette
- No global CSS for component styles — co-located Tailwind classes
- `className` uses `clsx` + `tailwind-merge` for conditional classes:
  ```tsx
  import { cn } from "@/lib/utils"
  <div className={cn("base-class", condition && "conditional-class")} />
  ```

## Testing Conventions

See `TESTING.md` for full details.
