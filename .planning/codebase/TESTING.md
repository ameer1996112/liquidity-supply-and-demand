# Testing Patterns

## Backend Testing (Python)
- **Framework**: `pytest` is the primary test runner.
- **Test Structure**: Tests are organized into `tests/unit`, `tests/integration`, and `tests/e2e`.
  - **Unit Tests**: Fast tests with mocked dependencies (no database/redis required). Run via `make test-unit`.
  - **Integration Tests**: Tests involving the database and Redis interactions. Requires the test infrastructure to be running. Run via `make test-int`.
  - **E2E Tests**: Full system tests checking end-to-end flows. Run via `make test-e2e`.
- **Fixtures**: Heavy use of `pytest` fixtures for setup/teardown, defined in `conftest.py`. Mocking is used extensively for external APIs (e.g. MetaApi adapters, OpenAI).
- **Automation**: Executed via custom `Makefile` commands to spin up test infrastructure (`make setup-test` spins up a Redis docker container, `make teardown-test` shuts it down).

## Frontend Testing (Next.js)
- **Framework**: `vitest` configured with `jsdom` for simulating browser environments.
- **Execution**: Can be run via `npm run test` or `npx vitest run`.
- **Scope**: Focuses on unit testing React components and core domain logic, with hooks and integrations mocked out where necessary.

## Continuous Integration (CI)
- Handled via `scripts/run_test_suite.sh`, which is invoked via `make test-ci`. This handles the bootstrapping of test environments and running the full suite with proper logging and coverage reporting.
