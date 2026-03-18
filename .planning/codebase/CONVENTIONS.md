# Coding Conventions

## Python Backend

### Style
- **Linter**: Ruff (98 pre-existing warnings)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Type hints**: Used in settings and data models (Pydantic), inconsistent in services
- **Docstrings**: Present on Settings class and key functions, sparse in services

### Configuration Pattern
- Centralized via `config/settings.py` using Pydantic `BaseSettings`
- Environment variables with `AliasChoices` for flexible naming
- `@lru_cache` singleton pattern for `get_settings()`
- All features have enable/disable flags (e.g., `ai_filter_enabled`, `ml_guardian_enabled`)

### API Pattern
- Main app in `src/api.py` with route modules included via `app.include_router()`
- Each `api_*.py` file defines a FastAPI `APIRouter` with related endpoints
- CORS configured for frontend origins
- Rate limiting via slowapi
- Health check at `GET /health`

### Service Pattern
- Services are typically class-based with methods, instantiated in worker
- No dependency injection framework — services constructed manually
- Many services accept `settings` as constructor parameter
- Background services use APScheduler for periodic tasks

### Error Handling
- Try/except blocks with logging in most services
- Guard rails return PASS/FAIL/WARNING with reasons
- Circuit breaker pattern for catastrophic failures
- Worker continues on individual signal failure (resilient loop)

### Guard Rail Pattern
- Each guard in `src/core/guard_rails/` follows a consistent interface
- Returns decision (PASS/FAIL/WARNING) with reason string
- Pipeline chains multiple guards — any FAIL blocks execution
- Can be individually enabled/disabled via settings

## TypeScript Frontend

### Style
- **Framework**: Next.js 16 App Router (server components default)
- **Styling**: TailwindCSS 4 with custom utility classes
- **State**: TanStack Query for server state, React state for UI
- **Icons**: Lucide React
- **Linter**: ESLint 9 with next config (pre-existing warnings)

### Component Pattern
- Functional components with hooks
- Components organized by domain (accounts, analytics, positions, etc.)
- Shared UI primitives in `components/ui/` (Radix-based)
- `"use client"` directive for interactive components

### Data Fetching Pattern
- Custom hooks wrapping TanStack Query (`useQuery`, `useMutation`)
- Dual data sources:
  - `lib/api.ts` — REST calls to backend API
  - `lib/supabase.ts` — Direct Supabase queries from frontend
- Polling intervals for real-time data updates

### File Organization
- Pages: `app/[route]/page.tsx`
- Components: `components/[domain]/[Component].tsx`
- Hooks: `hooks/use[Feature].ts`
- Lib: `lib/[utility].ts`
