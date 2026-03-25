# Testing Practices

## Backend Testing (Python)
- **Framework**: `pytest` is used for the Python API and Worker.
- **Location**: Test files reside in the `/tests` directory.
- **Coverage**: Includes unit tests and end-to-end (E2E) tests (`e2e_test.py`).
- **Execution**: Can be run via `PYTHONPATH=/workspace pytest tests/ -v`.
- **Mocking**: Database (Supabase) and external APIs (TradingView/MetaApi) are typically mocked or tested against a staging environment using `unittest.mock`.

## Frontend Testing (Next.js)
- **Framework**: `vitest` is set up for running frontend logic tests.
- **Execution**: Run via `cd frontend && npx vitest run`.

## Trading Logic Testing
- **Backtesting**: Pine Script strategies are backtested directly within TradingView using historical data.
- **Python Backtesting Engine**: The `/src/backtest` module contains a custom event-driven/vectorized framework building on `backtesting.py` to evaluate algorithmic filters securely over historical CSV data.
- **Paper Trading**: Built-in `PAPER_TRADING_ENABLED` mode simulates execution on live signals without committing capital.
