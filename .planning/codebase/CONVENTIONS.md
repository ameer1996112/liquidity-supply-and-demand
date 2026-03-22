# Coding Conventions

The codebase follows professional standards for both Python (Backend) and TypeScript (Frontend), prioritizing maintainability, type safety, and structured error handling.

## Python (Backend)

### Code Style
- **Indentation**: 4 spaces
- **Formatting**: PEP 8 compliant, strictly enforced by `ruff`
- **Linting**: `ruff` is used for linting and formatting. `mypy` is used for static type checking.

### Naming Conventions
- **Files/Folders**: `snake_case`
- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private members**: Internal/private helpers are prefixed with a single underscore (e.g., `_validate_webhook_payload`)

### Error Handling Patterns
- **Logging**: Centralized logging via a custom `get_logger` utility that provides structured output.
- **Exceptions**: Extensive use of `try...except` blocks. Critical errors are logged with stack traces, while user-facing errors use FastAPI's `HTTPException`.
- **Fail-Fast**: Critical infrastructure (like Redis) is checked immediately upon backend startup to prevent cascading failures.

### Common Patterns
- **Async/Await**: Modern asynchronous patterns are used for all API endpoints and many service-level background tasks.
- **Decorators**: Used for cross-cutting concerns such as rate limiting and event handling.
- **Context Managers**: FastAPI's `lifespan` context manager handles application initialization and cleanup.
- **Type Hints**: Professional-grade type hinting (`typing` module) is used across the entire codebase for better IDE support and safety.
- **Dependency Injection**: Heavy reliance on FastAPI's `Depends` for injecting configurations and low-level services.

### Import Organization
Grouped by Standard Library → Third-party → Local modules.

## TypeScript (Frontend)

### Code Style
- **Indentation**: 2 spaces
- **Formatting**: Managed by ESLint and Prettier
- **Framework**: Next.js 16 (App Router), React 19

### Naming Conventions
- **Folders**: `kebab-case` for consistency with Web URL standards
- **Component Files**: `PascalCase.tsx` (e.g., `SignalCard.tsx`)
- **Functions/Variables**: `camelCase`
- **Types/Interfaces**: `PascalCase`

### Patterns
- **Functional Components**: React functional components using the modern Hooks API
- **Directory Structure**: Feature-based organization under `src/components/`, with utility directories for `hooks`, `services`, `types`, and `lib`
- **State Management**: React Context for global state (Theme, Sidebar, Timezone) and TanStack Query (React Query) for server-state/API interactions
- **Styling**: Tailwind CSS 4 with Radix UI / Shadcn UI for accessible primitives

### Import Organization
Uses the `@/` path alias pointing to the `src` directory to avoid complex relative paths.
