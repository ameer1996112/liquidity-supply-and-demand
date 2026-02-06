"""
Test Configuration and Fixtures for Trading System Tests

Provides fixtures for unit, integration, and E2E tests:
- base_signal(): Valid webhook payload
- stub_model_*(): ML model stubs with controlled predictions
- fake_ledger(): In-memory ledger for unit tests
- redis_client: Real Redis connection for integration tests
"""

import os
import sys
from unittest.mock import MagicMock

# ══════════════════════════════════════════════════════════
# MOCK EXTERNAL DEPENDENCIES BEFORE ANY IMPORTS
# ══════════════════════════════════════════════════════════
# This must happen before any src imports to prevent ImportError
# when optional dependencies (openai, langchain, etc.) are not installed.

def _create_module_mock():
    """Create a MagicMock that acts as a proper module with submodules."""
    mock = MagicMock()
    # Set __path__ to make it act like a package
    mock.__path__ = []
    return mock


# Mock OpenAI
_openai_modules = [
    "openai",
]
for mod in _openai_modules:
    if mod not in sys.modules:
        sys.modules[mod] = _create_module_mock()

# Mock LangChain Core
_langchain_core_modules = [
    "langchain_core",
    "langchain_core.documents",
    "langchain_core.embeddings",
    "langchain_core.language_models",
    "langchain_core.messages",
    "langchain_core.vectorstores",
    "langchain_core.runnables",
]
for mod in _langchain_core_modules:
    if mod not in sys.modules:
        sys.modules[mod] = _create_module_mock()

# Mock LangChain Community
_langchain_community_modules = [
    "langchain_community",
    "langchain_community.vectorstores",
    "langchain_community.embeddings",
    "langchain_community.vectorstores.supabase",
]
for mod in _langchain_community_modules:
    if mod not in sys.modules:
        sys.modules[mod] = _create_module_mock()

# Mock LangChain OpenAI
_langchain_openai_modules = [
    "langchain_openai",
    "langchain_openai.embeddings",
]
for mod in _langchain_openai_modules:
    if mod not in sys.modules:
        sys.modules[mod] = _create_module_mock()

# Mock yfinance
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = _create_module_mock()

# Standard imports
import json
import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional
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

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for key checking."""
        return key in self._encoders

    def __getitem__(self, key: str):
        """Support bracket notation for accessing encoders."""
        return self._encoders[key]


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


# ══════════════════════════════════════════════════════════
# MOCK SETTINGS FIXTURES
# ══════════════════════════════════════════════════════════


class MockSettings:
    """Mock Settings class for isolated testing."""

    def __init__(self, **overrides):
        # Required base settings
        self.supabase_url = "https://test.supabase.co"
        self.supabase_anon_key = "test-anon-key"
        self.redis_url = "redis://localhost:6379"

        # Webhook & Execution
        self.webhook_secret = ""
        self.run_mode = "DRY_RUN"
        self.live_trading_enabled = False
        self.live_shadow = True
        self.trading_kill_switch = False
        self.execution_mode = "SHADOW"

        # Account & Risk
        self.account_balance = 10000.0
        self.risk_percent = 1.0
        self.min_rr_ratio = 1.0
        self.paper_trading_enabled = True
        self.paper_auto_execute = True
        self.paper_symbols = ""
        self.paper_max_positions = 3

        # AI & ML
        self.ai_filter_enabled = True
        self.ai_provider = "openai"
        self.ai_api_key = "test-key"
        self.ai_min_confidence = 75
        self.ai_model = "gpt-4o-mini"
        self.ml_min_confidence = 0.60
        self.enable_llm_filter = True

        # Trinity Engine
        self.trinity_enabled = True
        self.trinity_max_positions = 3
        self.trinity_max_daily_loss_pct = 4.0
        self.trinity_max_drawdown_pct = 8.0

        # MetaApi
        self.meta_api_token = "test-token"
        self.meta_api_account_id = "test-account-id"
        self.meta_api_region = "new-york"

        # Apply overrides
        for key, value in overrides.items():
            setattr(self, key, value)


@pytest.fixture
def mock_settings():
    """Default mock settings for testing."""
    return MockSettings()


@pytest.fixture
def mock_settings_live():
    """Mock settings with live trading enabled."""
    return MockSettings(
        run_mode="LIVE",
        live_trading_enabled=True,
        live_shadow=False,
        paper_trading_enabled=False,
        paper_auto_execute=False,
    )


@pytest.fixture
def mock_settings_paper():
    """Mock settings for paper trading."""
    return MockSettings(
        run_mode="PAPER",
        paper_trading_enabled=True,
        paper_auto_execute=True,
    )


@pytest.fixture
def mock_settings_ai_disabled():
    """Mock settings with AI filter disabled."""
    return MockSettings(
        ai_filter_enabled=False,
        enable_llm_filter=False,
    )


# ══════════════════════════════════════════════════════════
# MOCK SUPABASE CLIENT FIXTURES
# ══════════════════════════════════════════════════════════


class MockSupabaseResponse:
    """Mock Supabase response object."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error


class MockSupabaseTable:
    """Mock Supabase table with chainable methods."""

    def __init__(self, name: str, records: List[Dict[str, Any]] = None):
        self.name = name
        self._records = records if records is not None else []
        self._filters: Dict[str, Any] = {}
        self._select_cols = "*"
        self._update_data = {}
        self._insert_data = {}

    def select(self, cols: str = "*"):
        self._select_cols = cols
        return self

    def insert(self, data: Dict[str, Any]):
        self._insert_data = data
        return self

    def update(self, data: Dict[str, Any]):
        self._update_data = data
        return self

    def eq(self, column: str, value: Any):
        self._filters[column] = value
        return self

    def execute(self) -> MockSupabaseResponse:
        # Handle insert
        if self._insert_data:
            new_id = len(self._records) + 1
            record = {**self._insert_data, "id": new_id}
            self._records.append(record)
            return MockSupabaseResponse(data=[record])

        # Handle update
        if self._update_data:
            updated = []
            for record in self._records:
                if all(record.get(k) == v for k, v in self._filters.items()):
                    record.update(self._update_data)
                    updated.append(record)
            return MockSupabaseResponse(data=updated)

        # Handle select
        filtered = self._records
        for col, val in self._filters.items():
            filtered = [r for r in filtered if r.get(col) == val]
        return MockSupabaseResponse(data=filtered)


class MockSupabaseClient:
    """
    Mock Supabase client for testing without network calls.

    Usage:
        client = MockSupabaseClient()
        client.add_record("trading_signals", {"id": 1, "symbol": "EURUSD"})
        result = client.table("trading_signals").select("*").eq("id", 1).execute()
    """

    def __init__(self):
        self._tables: Dict[str, List[Dict[str, Any]]] = {
            "trading_signals": [],
            "strategy_rules": [],
        }

    def add_record(self, table_name: str, record: Dict[str, Any]) -> None:
        """Add a record to a mock table."""
        if table_name not in self._tables:
            self._tables[table_name] = []
        if "id" not in record:
            record["id"] = len(self._tables[table_name]) + 1
        self._tables[table_name].append(record)

    def get_records(self, table_name: str) -> List[Dict[str, Any]]:
        """Get all records from a mock table."""
        return self._tables.get(table_name, [])

    def clear_table(self, table_name: str) -> None:
        """Clear all records from a mock table."""
        self._tables[table_name] = []

    def table(self, name: str) -> MockSupabaseTable:
        if name not in self._tables:
            self._tables[name] = []
        return MockSupabaseTable(name, self._tables[name])


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    return MockSupabaseClient()


@pytest.fixture
def mock_supabase_with_trades(mock_supabase_client):
    """Mock Supabase with pre-populated executed trades."""
    mock_supabase_client.add_record("trading_signals", {
        "id": 1,
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
        "status": "executed",
        "run_mode": "LIVE",
        "broker_order_id": "123456",
        "trade_key": "test-trade-001",
    })
    mock_supabase_client.add_record("trading_signals", {
        "id": 2,
        "symbol": "GBPUSD",
        "side": "sell",
        "entry": 1.2650,
        "sl": 1.2700,
        "tp": 1.2550,
        "size": 0.15,
        "status": "executed",
        "run_mode": "LIVE",
        "broker_order_id": "789012",
        "trade_key": "test-trade-002",
    })
    return mock_supabase_client


# ══════════════════════════════════════════════════════════
# MOCK OPENAI CLIENT FIXTURES
# ══════════════════════════════════════════════════════════


class MockOpenAIMessage:
    """Mock OpenAI message object."""

    def __init__(self, content: str):
        self.content = content


class MockOpenAIChoice:
    """Mock OpenAI choice object."""

    def __init__(self, content: str):
        self.message = MockOpenAIMessage(content)


class MockOpenAIResponse:
    """Mock OpenAI chat completion response."""

    def __init__(self, content: str):
        self.choices = [MockOpenAIChoice(content)]


class MockOpenAIClient:
    """
    Mock OpenAI client for testing without API calls.

    Configurable responses for different test scenarios.
    """

    def __init__(self, response_json: Optional[Dict[str, Any]] = None, raise_error: bool = False):
        self._response_json = response_json or {"decision": "GO", "reason": "Test approved"}
        self._raise_error = raise_error
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **kwargs) -> MockOpenAIResponse:
        if self._raise_error:
            raise Exception("Mock OpenAI API Error")
        return MockOpenAIResponse(json.dumps(self._response_json))


@pytest.fixture
def mock_openai_go():
    """Mock OpenAI client that returns GO decision."""
    return MockOpenAIClient({"decision": "GO", "reason": "Trade approved by LLM"})


@pytest.fixture
def mock_openai_no_go():
    """Mock OpenAI client that returns NO_GO decision."""
    return MockOpenAIClient({"decision": "NO_GO", "reason": "Trade rejected by LLM"})


@pytest.fixture
def mock_openai_broken_json():
    """Mock OpenAI client that returns invalid JSON."""
    client = MockOpenAIClient()
    client._response_json = None

    def broken_create(**kwargs):
        return MockOpenAIResponse("This is not valid JSON {broken")

    client.completions.create = broken_create
    return client


@pytest.fixture
def mock_openai_error():
    """Mock OpenAI client that raises an error."""
    return MockOpenAIClient(raise_error=True)


# ══════════════════════════════════════════════════════════
# MOCK METAAPI FIXTURES
# ══════════════════════════════════════════════════════════


class MockMetaApiResponse:
    """Mock requests response for MetaApi calls."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        text: str = "",
        raise_timeout: bool = False,
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text or json.dumps(json_data or {})
        self._raise_timeout = raise_timeout

    def json(self) -> Dict[str, Any]:
        if self._json_data is None:
            raise ValueError("No JSON data")
        return self._json_data


@pytest.fixture
def mock_metaapi_success():
    """Mock MetaApi successful order response."""
    return MockMetaApiResponse(
        status_code=200,
        json_data={"orderId": "12345678", "status": "filled"},
    )


@pytest.fixture
def mock_metaapi_rejection():
    """Mock MetaApi order rejection (invalid stops)."""
    return MockMetaApiResponse(
        status_code=400,
        text="Invalid SL/TP levels for current price",
    )


@pytest.fixture
def mock_metaapi_price():
    """Mock MetaApi price response."""
    return MockMetaApiResponse(
        status_code=200,
        json_data={"bid": 1.0848, "ask": 1.0852, "symbol": "EURUSD"},
    )


@pytest.fixture
def mock_metaapi_positions():
    """Mock MetaApi open positions response."""
    return [
        {
            "id": "123456",
            "positionId": "123456",
            "symbol": "EURUSD",
            "type": "POSITION_TYPE_BUY",
            "volume": 0.10,
            "openPrice": 1.0850,
            "profit": 25.50,
        },
    ]


@pytest.fixture
def mock_metaapi_positions_empty():
    """Mock MetaApi empty positions response."""
    return []


@pytest.fixture
def mock_metaapi_history_deals():
    """Mock MetaApi history deals for watchdog testing."""
    return {
        "deals": [
            # Entry deal
            {
                "id": "deal-001",
                "orderId": "123456",
                "positionId": "pos-001",
                "symbol": "EURUSD",
                "type": "DEAL_TYPE_BUY",
                "entryType": "DEAL_ENTRY_IN",
                "volume": 0.10,
                "price": 1.0850,
                "profit": 0.0,
                "swap": 0.0,
                "commission": -0.50,
                "time": "2024-01-15T10:00:00.000Z",
            },
            # Exit deal (TP hit)
            {
                "id": "deal-002",
                "orderId": "123457",
                "positionId": "pos-001",
                "symbol": "EURUSD",
                "type": "DEAL_TYPE_SELL",
                "entryType": "DEAL_ENTRY_OUT",
                "volume": 0.10,
                "price": 1.0950,
                "profit": 100.0,
                "swap": -0.25,
                "commission": -0.50,
                "time": "2024-01-15T14:30:00.000Z",
            },
        ],
    }


@pytest.fixture
def mock_metaapi_history_loss():
    """Mock MetaApi history deals with losing trade."""
    return {
        "deals": [
            # Entry deal
            {
                "id": "deal-001",
                "orderId": "789012",
                "positionId": "pos-002",
                "symbol": "GBPUSD",
                "type": "DEAL_TYPE_SELL",
                "entryType": "DEAL_ENTRY_IN",
                "volume": 0.15,
                "price": 1.2650,
                "profit": 0.0,
                "swap": 0.0,
                "commission": -0.75,
                "time": "2024-01-15T11:00:00.000Z",
            },
            # Exit deal (SL hit)
            {
                "id": "deal-002",
                "orderId": "789013",
                "positionId": "pos-002",
                "symbol": "GBPUSD",
                "type": "DEAL_TYPE_BUY",
                "entryType": "DEAL_ENTRY_OUT",
                "volume": 0.15,
                "price": 1.2700,
                "profit": -75.0,
                "swap": -0.10,
                "commission": -0.75,
                "time": "2024-01-15T13:00:00.000Z",
            },
        ],
    }


@pytest.fixture
def mock_metaapi_history_no_exit():
    """Mock MetaApi history with entry but no exit deal yet."""
    return {
        "deals": [
            {
                "id": "deal-001",
                "orderId": "123456",
                "positionId": "pos-001",
                "symbol": "EURUSD",
                "type": "DEAL_TYPE_BUY",
                "entryType": "DEAL_ENTRY_IN",
                "volume": 0.10,
                "price": 1.0850,
                "profit": 0.0,
                "time": "2024-01-15T10:00:00.000Z",
            },
        ],
    }


@pytest.fixture
def mock_metaapi_history_id_mismatch():
    """Mock MetaApi history where orderId != positionId."""
    return {
        "deals": [
            # Entry deal: orderId=123456, positionId=pos-999 (mismatch)
            {
                "id": "deal-001",
                "orderId": "123456",
                "positionId": "pos-999",  # Different from orderId
                "symbol": "EURUSD",
                "type": "DEAL_TYPE_BUY",
                "entryType": "DEAL_ENTRY_IN",
                "volume": 0.10,
                "price": 1.0850,
                "profit": 0.0,
                "time": "2024-01-15T10:00:00.000Z",
            },
            # Exit deal linked by positionId
            {
                "id": "deal-002",
                "orderId": "999888",  # Different orderId
                "positionId": "pos-999",  # Same positionId as entry
                "symbol": "EURUSD",
                "type": "DEAL_TYPE_SELL",
                "entryType": "DEAL_ENTRY_OUT",
                "volume": 0.10,
                "price": 1.0920,
                "profit": 70.0,
                "swap": -0.15,
                "commission": -0.50,
                "time": "2024-01-15T15:00:00.000Z",
            },
        ],
    }


# ══════════════════════════════════════════════════════════
# MOCK RAG ENGINE FIXTURES
# ══════════════════════════════════════════════════════════


class MockRagDocument:
    """Mock RAG document."""

    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.page_content = content
        self.metadata = metadata or {}


class MockRagEngine:
    """Mock RAG engine for testing."""

    def __init__(self, documents: Optional[List[MockRagDocument]] = None, fail: bool = False):
        self._documents = documents or []
        self._fail = fail

    def query_rules(self, query: str, k: int = 4, filter: Optional[Dict[str, Any]] = None) -> List[MockRagDocument]:
        if self._fail:
            raise Exception("RAG engine failure")
        return self._documents[:k]


@pytest.fixture
def mock_rag_engine():
    """Mock RAG engine with sample rules."""
    return MockRagEngine(documents=[
        MockRagDocument("Only enter on liquidity sweeps with fresh demand zones"),
        MockRagDocument("Avoid trading during high-impact news events"),
        MockRagDocument("Minimum R:R ratio should be 2:1 for A+ setups"),
        MockRagDocument("Wait for price to sweep liquidity before entering"),
    ])


@pytest.fixture
def mock_rag_engine_empty():
    """Mock RAG engine returning no documents."""
    return MockRagEngine(documents=[])


@pytest.fixture
def mock_rag_engine_failure():
    """Mock RAG engine that fails."""
    return MockRagEngine(fail=True)


# ══════════════════════════════════════════════════════════
# BRAIN TEST PAYLOADS
# ══════════════════════════════════════════════════════════


@pytest.fixture
def brain_payload_bullish():
    """
    Payload representing bullish market conditions.
    Price > SMA200, RSI < 30 (oversold in uptrend = buying opportunity).
    """
    return {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
        "zone_type": "demand",
        "entry_model": "FLIP",
        "score": 90.0,
        "freshness": 1,
        "liq_swept": True,
        # Market context indicators (for narrative)
        "price": 1.0850,
        "sma200": 1.0700,  # price > sma200 = bullish
        "rsi": 28,  # RSI < 30 = oversold
    }


@pytest.fixture
def brain_payload_bearish_contradiction():
    """
    Payload with contradictory signals.
    Price > SMA200 (bullish) but trying to sell = contradiction.
    """
    return {
        "symbol": "EURUSD",
        "side": "sell",  # Selling in bullish market
        "entry": 1.0850,
        "sl": 1.0900,
        "tp": 1.0750,
        "size": 0.10,
        "zone_type": "supply",
        "entry_model": "DIR_CLOSE",
        "score": 60.0,  # Lower score
        "freshness": 3,  # Stale zone
        "liq_swept": False,
        "price": 1.0850,
        "sma200": 1.0700,  # price > sma200 = bullish (contradicts sell)
        "rsi": 65,
    }


# ══════════════════════════════════════════════════════════
# EXECUTION TEST FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def order_request_buy():
    """Sample buy order request."""
    from src.adapters.execution.interfaces import OrderRequest

    return OrderRequest(
        client_order_id="test-order-001",
        signal_id=1,
        symbol="EURUSD",
        side="buy",
        size=0.10,
        entry=1.0850,
        sl=1.0800,
        tp=1.0950,
        alert_id=1,
        rr_ratio=2.0,
    )


@pytest.fixture
def order_request_sell():
    """Sample sell order request."""
    from src.adapters.execution.interfaces import OrderRequest

    return OrderRequest(
        client_order_id="test-order-002",
        signal_id=2,
        symbol="GBPUSD",
        side="sell",
        size=0.15,
        entry=1.2650,
        sl=1.2700,
        tp=1.2550,
        alert_id=2,
        rr_ratio=2.0,
    )


@pytest.fixture
def close_request():
    """Sample close order request."""
    from src.adapters.execution.interfaces import CloseRequest

    return CloseRequest(
        client_order_id="test-close-001",
        signal_id=1,
        symbol="EURUSD",
        close_price=1.0920,
        outcome="win",
        alert_id=1,
        broker_order_id="123456",
        notes="exit_webhook",
        side="buy",
        size=0.10,
    )
