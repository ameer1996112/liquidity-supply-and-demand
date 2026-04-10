# Testing Guide

This document describes how to write, run, and maintain tests for the trading system.

---

## Test Stack

- **Framework:** `pytest` (all tests in `tests/`)
- **Mocking:** `unittest.mock` (`MagicMock`, `patch`, `monkeypatch`)
- **Fixtures:** Defined in `tests/conftest.py` and `tests/conftest_incidents.py`
- **Style:** `unittest.TestCase` classes or plain `pytest` functions — both are acceptable

---

## Running Tests

```bash
# Run the full suite from the project root
pytest tests/

# Run a single file
pytest tests/test_worker_observers.py

# Run a specific test class or method
pytest tests/test_worker_observers.py::WorkerSubjectEventTests::test_success_emits_received_then_submitted

# Verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -x
```

---

## Environment Setup for Tests

`tests/conftest.py` sets dummy environment variables before any `src.*` imports so that `config.Settings` can be instantiated without real credentials.

**Key defaults set by conftest:**

| Variable | Value |
|---|---|
| `SUPABASE_URL` | `http://dummy.supabase.test` |
| `SUPABASE_KEY` | *(empty — skips Supabase init)* |
| `REDIS_URL` | `redis://localhost:6379` |
| `SIGNAL_TRANSPORT` | `memory` |
| `META_API_TOKEN` | *(empty)* |
| `AI_API_KEY` | `dummy-ai-key` |

**Global autouse fixture** (`_mock_redis_client`): replaces the lazy Redis singleton with a `MagicMock` for every test, preventing real TCP connections to Redis.

Tests that need specific Redis or Supabase behaviour must patch at a finer scope themselves.

---

## What to Test

### Required for every bug fix

1. A test that **reproduces the bug** (fails before the fix, passes after).
2. Placed in the most relevant existing test file, or a new file if the area is not yet covered.

### Required for risk and execution changes

Any change to `risk_engine.py`, worker guard logic, or `logic.py` must include:
- A unit test for the changed path.
- An integration test if the change affects the signal → order lifecycle.
- A note in `docs/decisions.md`.

### Required for new API endpoints

- At least one test covering the happy path.
- At least one test covering a validation error or missing data.

---

## Test Organisation

Tests are grouped by area. File naming follows the pattern `test_<area>.py`:

| File | Area |
|---|---|
| `test_worker_observers.py` | Observer pipeline, TradeEvent, WorkerSubject |
| `test_sprint55_reliability.py` | Chaos/reliability: Redis, idempotency, retries |
| `test_dynamic_sizing.py` | Position sizing across instrument types |
| `test_nzdjpy_fix.py` | JPY pair dynamic pip value calculation |
| `test_pipeline.py` | End-to-end webhook → trade lifecycle (integration) |
| `test_ai_brain.py` | ML brain predictions |
| `test_prop_firm_phase1.py` | Prop firm guard rail logic |
| `test_consumer_validation.py` | Dequeued message schema validation |
| `test_signal_transport.py` | InMemoryTransport and RedisTransport |
| `test_account_routing.py` | Account routing and multi-account isolation |

---

## Writing Tests

### Unit tests (preferred for domain logic)

```python
import unittest
from unittest.mock import MagicMock, patch

class MyTests(unittest.TestCase):
    def test_something(self):
        result = my_function(input)
        self.assertEqual(result, expected)
```

### Patching external dependencies

Always patch at the point of use, not at the definition:

```python
# Patch where it is imported, not where it is defined
with patch("src.services.some_service.requests.get") as mock_get:
    mock_get.return_value.json.return_value = {"status": "ok"}
    result = my_function()
```

### Testing the Observer pipeline

Use `_CapturingObserver` (defined locally or copied from `test_worker_observers.py`) to record events:

```python
class CapturingObserver(Observer):
    def __init__(self):
        self.events = []
    def on_event(self, event):
        self.events.append(event)

cap = CapturingObserver()
subject = WorkerSubject(process_fn=lambda p: None)
subject.attach(cap)
subject.process_signal(payload)

assert cap.events[0].event_type == SIGNAL_RECEIVED
assert cap.events[1].event_type == ORDER_SUBMITTED
```

### Testing API endpoints

Use FastAPI's `TestClient`:

```python
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_webhook_returns_200():
    response = client.post("/webhook", json={...}, headers={"X-TV-Secret": "test"})
    assert response.status_code == 200
```

---

## Test Doubles Hierarchy

Prefer the simplest double that proves the invariant:

1. **Real object** — use when the real implementation is fast and has no side effects (e.g. `InMemoryTransport`).
2. **Stub** — returns a fixed value; use when you need the dependency to exist but don't care about its behaviour.
3. **Mock** (`MagicMock`) — records calls; use when you need to assert the dependency was called correctly.
4. **Fake** — a lightweight real implementation; use when the real one is too heavy (e.g. in-memory Redis via `InMemoryTransport`).
5. **Patch** — replaces a module-level attribute at test time; use sparingly, prefer constructor injection.

---

## What Not to Test

- Do not write tests that hit real Redis, Supabase, or MetaAPI — mock them.
- Do not test implementation details (private methods, internal state); test observable behaviour.
- Do not test third-party library behaviour (e.g. Pydantic validation internals).
- Do not write tests that depend on wall-clock time or network latency; freeze time or use fixed timestamps.

---

## CI Behaviour

The test suite is designed to run without any external services:

- Redis is mocked globally via `conftest.py`.
- Supabase keys are left empty so the init guard skips DB setup.
- Signal transport defaults to `InMemoryTransport`.
- All network-bound adapters (MetaAPI, Telegram, Discord) require explicit patching in tests that exercise them.

If a test fails in CI but passes locally, the most common cause is an unpatched environment variable or a missing `conftest.py` fixture. Check `conftest.py` first.

---

## Regression Protection

When closing a bug:
1. Add the failing scenario as a named test case.
2. The test name must describe the bug, not the fix (e.g. `test_jpy_pip_value_not_hardcoded`, not `test_fix_for_issue_123`).
3. Add the test file or test name to `docs/bugs.md` in the bug's entry.
