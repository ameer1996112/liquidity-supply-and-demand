# Testing Patterns

The project utilizes automated testing for both backend and frontend, with dedicated configurations for local development and CI/CD pipelines.

## Backend Testing

### Framework
`pytest` with `conftest.py` for global fixtures.

### Directory Structure
All tests are located in the `tests/` directory at the project root.

### Organization
- Files are named `test_*.py`
- The `Makefile` categorizes tests into `unit`, `integration`, and `e2e` using pytest markers (`-m unit`, etc.)

### Fixtures and Mocking
- **`conftest.py`**: Central configuration that sets up global fixtures, dummy environment variables, and mocks before tests run.
- **Infrastructure Mocking**: Automatic fixture (`_mock_redis_client`) replaces the live Redis client with a mock for all backend tests unless explicitly overridden.
- **Isolated Transport**: `SIGNAL_TRANSPORT` is set to `memory` by default in the test environment to prevent tests from hitting production-like queues.
- **Unit Mocking**: Extensive use of `unittest.mock.MagicMock` to isolate the logic being tested from its dependencies.

### How to Run
- **All tests**: `PYTHONPATH=/workspace pytest tests/ -v`
- **With Coverage**: `pytest tests --cov=src --cov-report=term-missing`
- **By Suite**: `make test-unit`, `make test-integration`, or `make test-e2e`

### Status
- **11 tests, all pass** (as of last run)

## Frontend Testing

### Framework
`Vitest` with `jsdom` environment.

### Organization
- **Co-location**: Tests are stored alongside the code they verify, using `*.test.tsx` or `*.test.ts` naming convention (e.g., `src/components/SignalInspector.test.tsx`).

### Mocking and Setup
- **React Act**: Tests use the `act` utility from `react` for proper event and state update wrapping.
- **Manual Mounting**: Tests often mount components into a real DOM node provided by `jsdom` and clean up after each test.
- **Provider Wrappers**: Components are wrapped in necessary providers (like `QueryProvider`) during test setup to simulate the production application tree.

### How to Run
- `cd frontend && npx vitest run`

### Known Gaps & Issues
- **Pre-existing Failure**: There is a known pre-existing failure in `tradingMetrics.test.ts` that requires attention.
- **Mock Coverage**: Some complex 3rd party components (charts, terminals) may be stubbed rather than fully integrated in tests.
