"""
Test Configuration and Fixtures for Trading System Tests

Provides fixtures for unit, integration, and E2E tests:
- base_signal(): Valid webhook payload
- stub_model_*(): ML model stubs with controlled predictions
- fake_ledger(): In-memory ledger for unit tests
- redis_client: Real Redis connection for integration tests
"""

import os
import json
import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
import numpy as np

# Set test environment before any imports (prevents production resets, disables webhook auth)
os.environ["TRINITY_ENV"] = "test"
os.environ["WEBHOOK_SECRET"] = ""  # Disable auth for e2e webhook tests
if "REDIS_URL" not in os.environ:
    os.environ["REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://localhost:6379")
if "SUPABASE_URL" not in os.environ:
    os.environ["SUPABASE_URL"] = os.getenv("TEST_SUPABASE_URL", "https://test.supabase.co")
if "SUPABASE_ANON_KEY" not in os.environ:
    os.environ["SUPABASE_ANON_KEY"] = os.getenv("TEST_SUPABASE_ANON_KEY", "test-anon-key")


# ══════════════════════════════════════════════════════════
# BASE SIGNAL FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def base_signal() -> Dict[str, Any]:
    """
    Valid webhook payload matching EntryWebhookPayload schema.

    This is the standard shape expected by the webhook handler.
    """
    return {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
        "zone_id": 12345,
        "zone_type": "demand",
        "entry_model": "FLIP",
        "score": 85.0,
        "freshness": 1,
        "liq_swept": True,
        "target_swept": False,
        "caused_sweep": True,
        "run_mode": "PAPER",
        "run_id": "test-run-001",
        "trade_key": "test-trade-001",
    }


@pytest.fixture
def base_signal_sell() -> Dict[str, Any]:
    """Valid sell signal."""
    return {
        "symbol": "GBPUSD",
        "side": "sell",
        "entry": 1.2650,
        "sl": 1.2700,
        "tp": 1.2550,
        "size": 0.15,
        "zone_id": 12346,
        "zone_type": "supply",
        "entry_model": "DIR_CLOSE",
        "run_mode": "PAPER",
    }


@pytest.fixture
def exit_signal() -> Dict[str, Any]:
    """Valid exit webhook payload."""
    return {
        "event_type": "exit",
        "zone_id": 12345,
        "outcome": "win",
        "bars_held": 15,
        "close_price": 1.0945,
        "exit_type": "tp",
        "mae_pips": 12.5,
        "pnl_r": 2.0,
        "pnl_usd": 100.0,
    }


@pytest.fixture
def invalid_signal_missing_symbol() -> Dict[str, Any]:
    """Invalid payload - missing symbol."""
    return {
        "side": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
    }


@pytest.fixture
def invalid_signal_bad_side() -> Dict[str, Any]:
    """Invalid payload - invalid side."""
    return {
        "symbol": "EURUSD",
        "side": "long",  # Should be "buy" or "sell"
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
    }


@pytest.fixture
def oversized_signal() -> Dict[str, Any]:
    """Signal with size exceeding MAX_LOT_SIZE (0.30)."""
    return {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.50,  # > 0.30 limit
        "zone_id": 99999,
        "run_mode": "PAPER",
    }


# ══════════════════════════════════════════════════════════
# ML MODEL STUB FIXTURES
# ══════════════════════════════════════════════════════════


class StubModel:
    """Stub ML model for testing with controlled predictions."""

    def __init__(self, win_probability: float = 0.5):
        self.win_probability = win_probability
        self.feature_names_in_ = [
            "asset_id", "hour", "day_of_week", "type_encoded", "signal_encoded"
        ]

    def predict_proba(self, X) -> np.ndarray:
        """Return controlled probability for class 1 (win)."""
        loss_prob = 1.0 - self.win_probability
        return np.array([[loss_prob, self.win_probability]])


class StubEncoders:
    """Stub encoders for ML model testing."""

    def __init__(self):
        self._encoders = {
            "symbol": self._create_symbol_encoder(),
            "type": self._create_type_encoder(),
            "signal": self._create_signal_encoder(),
        }

    def _create_symbol_encoder(self):
        encoder = MagicMock()
        encoder.classes_ = np.array(["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"])
        encoder.transform = lambda x: np.array([list(encoder.classes_).index(x[0]) if x[0] in encoder.classes_ else 0])
        return encoder

    def _create_type_encoder(self):
        encoder = MagicMock()
        encoder.classes_ = np.array(["entry long", "entry short"])
        encoder.transform = lambda x: np.array([0 if "long" in x[0] else 1])
        return encoder

    def _create_signal_encoder(self):
        encoder = MagicMock()
        encoder.classes_ = np.array(["FLIP", "DIR_CLOSE", "BREAK_CANDLE"])
        encoder.transform = lambda x: np.array([0])
        return encoder

    def get(self, key: str, default=None):
        return self._encoders.get(key, default)


@pytest.fixture
def stub_model_low_confidence():
    """Stub model that predicts low win probability (below 60% threshold)."""
    return StubModel(win_probability=0.45)


@pytest.fixture
def stub_model_high_confidence():
    """Stub model that predicts high win probability (above 60% threshold)."""
    return StubModel(win_probability=0.75)


@pytest.fixture
def stub_model_threshold():
    """Stub model that predicts exactly at threshold (60%)."""
    return StubModel(win_probability=0.60)


@pytest.fixture
def stub_encoders():
    """Stub encoders for ML model."""
    return StubEncoders()


# ══════════════════════════════════════════════════════════
# FAKE LEDGER FIXTURES
# ══════════════════════════════════════════════════════════


class FakeLedger:
    """
    In-memory ledger for unit tests.

    Provides same interface as supabase_db functions without network calls.
    """

    def __init__(self):
        self.records: List[Dict[str, Any]] = []
        self._next_id = 1

    def save_alert(self, data: Dict[str, Any], mode: str = "manual", filter_reasons: List[str] = None) -> int:
        """Save alert to in-memory storage."""
        record = {
            "id": self._next_id,
            "symbol": data.get("symbol", "UNKNOWN"),
            "side": data.get("side", "buy"),
            "entry": float(data.get("entry", 0)),
            "sl": float(data.get("sl", 0)),
            "tp": float(data.get("tp", 0)),
            "size": float(data.get("size", 0)),
            "status": data.get("status", "active"),
            "notes": data.get("notes"),
            "ml_win_probability": data.get("ml_win_probability"),
            "run_mode": data.get("run_mode", "PAPER"),
            "run_id": data.get("run_id"),
            "trade_key": data.get("trade_key"),
            "zone_id": data.get("zone_id"),
            "filter_reason_json": json.dumps(filter_reasons) if filter_reasons else None,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._next_id += 1
        self.records.append(record)
        return record["id"]

    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions."""
        return [r for r in self.records if r.get("status") == "active"]

    def get_by_id(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Get record by ID."""
        for r in self.records:
            if r["id"] == alert_id:
                return r
        return None

    def get_by_zone_id(self, zone_id: int) -> Optional[Dict[str, Any]]:
        """Get record by zone_id."""
        for r in self.records:
            if r.get("zone_id") == zone_id:
                return r
        return None

    def update_status(self, alert_id: int, status: str, notes: str = None) -> bool:
        """Update record status."""
        for r in self.records:
            if r["id"] == alert_id:
                r["status"] = status
                if notes:
                    r["notes"] = notes
                return True
        return False

    def count_by_status(self, status: str) -> int:
        """Count records by status."""
        return len([r for r in self.records if r.get("status") == status])

    def clear(self):
        """Clear all records."""
        self.records.clear()
        self._next_id = 1


@pytest.fixture
def fake_ledger():
    """In-memory ledger for unit tests."""
    return FakeLedger()


# ══════════════════════════════════════════════════════════
# REDIS FIXTURES (Integration Tests)
# ══════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def redis_url():
    """Get Redis URL for tests (default: localhost:6379)."""
    return os.getenv("TEST_REDIS_URL", "redis://localhost:6379")


@pytest.fixture
def redis_client(redis_url):
    """
    Real Redis client for integration tests.

    Requires Redis running (use docker-compose.test.yml).
    Clears test queue before and after each test.
    """
    import redis

    client = redis.from_url(redis_url, decode_responses=True)

    # Verify connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available - run: docker compose -f docker-compose.test.yml up -d")

    # Clear test queue before test
    test_queue = "trading_queue_test"
    client.delete(test_queue)

    yield client

    # Cleanup after test
    client.delete(test_queue)


@pytest.fixture
def test_queue_name():
    """Queue name for integration tests."""
    return "trading_queue_test"


# ══════════════════════════════════════════════════════════
# ACTIVE POSITIONS FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def active_positions_full():
    """List of 3 active positions (at max limit)."""
    from src.core.guard_rails.correlation import ActivePosition
    from datetime import datetime

    return [
        ActivePosition(
            symbol="EURUSD",
            side="buy",
            size=0.10,
            entry_price=1.0850,
            entry_time=datetime.utcnow(),
            zone_id="zone1",
        ),
        ActivePosition(
            symbol="GBPUSD",
            side="sell",
            size=0.15,
            entry_price=1.2650,
            entry_time=datetime.utcnow(),
            zone_id="zone2",
        ),
        ActivePosition(
            symbol="USDJPY",
            side="buy",
            size=0.12,
            entry_price=150.50,
            entry_time=datetime.utcnow(),
            zone_id="zone3",
        ),
    ]


@pytest.fixture
def active_positions_two():
    """List of 2 active positions (below max limit)."""
    from src.core.guard_rails.correlation import ActivePosition
    from datetime import datetime

    return [
        ActivePosition(
            symbol="EURUSD",
            side="buy",
            size=0.10,
            entry_price=1.0850,
            entry_time=datetime.utcnow(),
        ),
        ActivePosition(
            symbol="USDJPY",
            side="sell",
            size=0.08,
            entry_price=149.50,
            entry_time=datetime.utcnow(),
        ),
    ]


@pytest.fixture
def active_positions_empty():
    """Empty list of active positions."""
    return []


# ══════════════════════════════════════════════════════════
# TEST API CLIENT (E2E)
# ══════════════════════════════════════════════════════════


@pytest.fixture
def test_app():
    """FastAPI TestClient for E2E tests."""
    from fastapi.testclient import TestClient
    from src.api import app

    return TestClient(app)


@pytest.fixture
def webhook_secret():
    """Test webhook secret (if configured)."""
    return os.getenv("WEBHOOK_SECRET", "test-secret-123")
