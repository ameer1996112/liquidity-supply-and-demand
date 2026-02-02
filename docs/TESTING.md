# Trading System Test Suite

Comprehensive automated test suite for the Trinity Engine trading system.

## Quick Start

```bash
# 1. Start test infrastructure (Redis)
make setup-test

# 2. Run all tests
make test-all

# 3. Stop test infrastructure
make teardown-test
```

## Test Categories

### Unit Tests (`pytest -m unit`)

Fast tests that run without external dependencies.

| Test File | Description |
|-----------|-------------|
| `test_risk_guardian.py` | Lot cap, daily loss limit, drawdown kill switch |
| `test_correlation_guardian.py` | Max 3 positions, currency exposure, correlation groups |
| `test_pine_guardian_payload.py` | Payload validation, position size calculation |
| `test_ml_guardian_stub.py` | ML prediction threshold using stub models |

**Run:** `make test-unit` or `pytest tests/unit -m unit`

### Integration Tests (`pytest -m integration`)

Tests requiring Redis (use docker-compose.test.yml).

| Test File | Description |
|-----------|-------------|
| `test_redis_roundtrip.py` | Enqueue/dequeue, payload integrity, FIFO order |
| `test_worker_processes_job_to_ledger.py` | Worker guard pipeline, ledger writes |

**Run:** `make test-int` or `pytest tests/integration -m integration`

### E2E Tests (`pytest -m e2e`)

End-to-end tests covering full signal flow.

| Test File | Description |
|-----------|-------------|
| `test_webhook_to_ledger.py` | POST webhook -> queue -> (worker consumption) |
| `test_burst_100_signals.py` | Burst load testing, stability, no data loss |

**Run:** `make test-e2e` or `pytest tests/e2e -m e2e`

## Requirements

### Environment Variables

```bash
# Required for tests
export TRINITY_ENV=test

# Redis (for integration/E2E tests)
export TEST_REDIS_URL=redis://localhost:6379
```

### Dependencies

```bash
pip install pytest pytest-asyncio httpx redis
```

### Test Infrastructure

Start Redis using Docker:

```bash
docker compose -f docker-compose.test.yml up -d
```

Verify connection:

```bash
make check-redis
# or
docker exec trading_test_redis redis-cli ping
```

## Test Commands

| Command | Description |
|---------|-------------|
| `make test-unit` | Run unit tests only (fast) |
| `make test-int` | Run integration tests (requires Redis) |
| `make test-e2e` | Run E2E tests (requires Redis) |
| `make test-all` | Run all tests |
| `make test-fast` | Unit + quick integration tests |
| `make test-coverage` | Run with coverage report |

## Critical Test Cases

These tests MUST pass before deployment:

1. **Risk Guardian - Lot Cap**
   - `test_risk_rejection_for_oversized_lot`: Size > 0.30 rejected

2. **Correlation Guardian - 4th Trade**
   - `test_rejects_4th_trade_with_3_active`: 4th trade blocked when 3 active

3. **ML Guardian - Threshold**
   - `test_rejects_when_below_threshold`: < 60% confidence rejected
   - `test_approves_at_exact_threshold`: >= 60% approved

4. **Webhook - Validation**
   - `test_valid_entry_returns_200`: Valid payload accepted
   - `test_missing_symbol_returns_422`: Invalid payload rejected

5. **Worker - Survival**
   - `test_survives_db_write_failure`: Worker continues after errors
   - `test_survives_ml_prediction_failure`: Fail-safe behavior

## Troubleshooting

### Redis Connection Refused

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solution:** Start Redis
```bash
make setup-test
# or
docker compose -f docker-compose.test.yml up -d
```

### Tests Skip "Redis not available"

**Solution:** Ensure Redis is running and accessible
```bash
make check-redis
```

### Import Errors

**Solution:** Install from project root with editable install
```bash
pip install -e .
```

### TRINITY_ENV Not Set

Reset scripts will fail if not in test mode:
```
SAFETY CHECK FAILED: TRINITY_ENV must be 'test'
```

**Solution:** Set environment variable
```bash
export TRINITY_ENV=test
```

## Test Configuration

### pytest.ini

```ini
[pytest]
markers =
    unit: Unit tests (no network)
    integration: Integration tests (requires Redis)
    e2e: End-to-end tests
    slow: Slow running tests
```

### Running Specific Tests

```bash
# Run specific test file
pytest tests/unit/test_risk_guardian.py -v

# Run specific test
pytest tests/unit/test_risk_guardian.py::TestDailyLossLimit::test_rejects_when_daily_loss_exceeds_4_percent -v

# Run tests matching pattern
pytest -k "risk" -v
```

## Adding New Tests

1. Place unit tests in `tests/unit/`
2. Place integration tests in `tests/integration/`
3. Place E2E tests in `tests/e2e/`
4. Mark tests with appropriate markers:
   ```python
   @pytest.mark.unit
   def test_something():
       pass
   ```
5. Use fixtures from `conftest.py`

## Safety Checks

The test suite includes safety checks for destructive scripts:

- `reset_system.py` - Requires TRINITY_ENV=test
- `hard_reset_server.py` - Requires TRINITY_ENV=test
- `purge_workspace.sh` - Requires TRINITY_ENV=test

These scripts will refuse to run in production environments.
