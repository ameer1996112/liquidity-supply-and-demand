# /add-endpoint

Add a new API endpoint to the FastAPI backend.

## Usage
`/add-endpoint <domain> <method> <path>`

## Procedure

1. Read `src/api_{domain}.py` (or note "new domain file" if it doesn't exist)
2. Read `.planning/codebase/CONVENTIONS.md` → "API Contract Rules" section
3. Read `.planning/codebase/MODULE_MAP.md` → "API Endpoints" section

## Implementation Steps

1. Create Pydantic request/response schemas in the endpoint file
2. Implement the endpoint with proper:
   - Type hints on all parameters
   - `async def` handler
   - Error handling (422 validation, 404 not found, 500 internal)
3. Register the router in `src/api.py` if it's a new domain file
4. Add corresponding TypeScript type in `frontend/src/types/` if frontend will consume it
5. Add test in `tests/` covering happy path + validation error

## Constraints
- Follow `kebab-case` for URL paths
- All list responses must include data array + count
- Do NOT put business logic in the endpoint — delegate to `src/services/`
- **STOP and wait for user approval** before applying changes
