"""
End-to-End Tests for Webhook to Ledger Flow

Tests the complete signal flow:
1. POST webhook with valid signal -> 200 response -> job enqueued
2. POST webhook with invalid signal -> 400 response -> no job enqueued
3. Webhook secret validation
4. Full flow: webhook -> Redis queue -> (worker would consume)

Uses FastAPI TestClient and real Redis.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Mark all tests in this module as e2e tests
pytestmark = pytest.mark.e2e


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def client():
    """FastAPI TestClient for webhook testing."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = MagicMock()
    mock.rpush = MagicMock(return_value=1)
    mock.llen = MagicMock(return_value=0)
    return mock


@pytest.fixture
def valid_entry_payload():
    """Valid entry payload for webhook."""
    return {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
    }


@pytest.fixture
def valid_exit_payload():
    """Valid exit payload for webhook."""
    return {
        "event_type": "exit",
        "zone_id": 12345,
        "outcome": "win",
        "bars_held": 15,
        "close_price": 1.0945,
        "exit_type": "tp",
        "mae_pips": 12.5,
    }


# ══════════════════════════════════════════════════════════
# VALID WEBHOOK TESTS
# ══════════════════════════════════════════════════════════


class TestValidWebhook:
    """Tests for valid webhook payloads."""

    def test_valid_entry_returns_200(self, client, valid_entry_payload, mock_redis):
        """Valid entry payload should return 200."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post("/webhook", json=valid_entry_payload)

        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_valid_entry_enqueues_job(self, client, valid_entry_payload, mock_redis):
        """Valid entry should enqueue exactly 1 job."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            client.post("/webhook", json=valid_entry_payload)

        # Verify rpush was called once
        mock_redis.rpush.assert_called_once()

        # Verify queue name is correct
        call_args = mock_redis.rpush.call_args
        queue_name = call_args[0][0]
        assert queue_name == "trading_queue"

    def test_valid_entry_payload_preserved(self, client, valid_entry_payload, mock_redis):
        """Entry payload should be preserved in queue."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            client.post("/webhook", json=valid_entry_payload)

        # Get the payload that was enqueued
        call_args = mock_redis.rpush.call_args
        enqueued_str = call_args[0][1]
        enqueued = json.loads(enqueued_str)

        assert enqueued["symbol"] == valid_entry_payload["symbol"]
        assert enqueued["side"] == valid_entry_payload["side"]
        assert enqueued["entry"] == valid_entry_payload["entry"]

    def test_valid_exit_returns_200(self, client, valid_exit_payload, mock_redis):
        """Valid exit payload should return 200."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post("/webhook", json=valid_exit_payload)

        assert response.status_code == 200

    def test_exit_event_enqueued(self, client, valid_exit_payload, mock_redis):
        """Exit event should also be enqueued."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            client.post("/webhook", json=valid_exit_payload)

        mock_redis.rpush.assert_called_once()


# ══════════════════════════════════════════════════════════
# INVALID WEBHOOK TESTS
# ══════════════════════════════════════════════════════════


class TestInvalidWebhook:
    """Tests for invalid webhook payloads."""

    def test_missing_symbol_returns_422(self, client, mock_redis):
        """Missing required field should return 422."""
        payload = {
            "side": "buy",
            "entry": 1.0850,
            "sl": 1.0800,
            "tp": 1.0950,
            "size": 0.10,
        }

        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post("/webhook", json=payload)

        assert response.status_code == 422

    def test_missing_symbol_no_enqueue(self, client, mock_redis):
        """Invalid payload should not enqueue job."""
        payload = {
            "side": "buy",
            "entry": 1.0850,
            "sl": 1.0800,
            "tp": 1.0950,
            "size": 0.10,
        }

        with patch("backend.main.get_redis", return_value=mock_redis):
            client.post("/webhook", json=payload)

        mock_redis.rpush.assert_not_called()

    def test_invalid_side_returns_422(self, client, mock_redis):
        """Invalid side value should return 422."""
        payload = {
            "symbol": "EURUSD",
            "side": "long",  # Should be "buy" or "sell"
            "entry": 1.0850,
            "sl": 1.0800,
            "tp": 1.0950,
            "size": 0.10,
        }

        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post("/webhook", json=payload)

        assert response.status_code == 422

    def test_empty_body_returns_422(self, client, mock_redis):
        """Empty body should return 422."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post("/webhook", json={})

        assert response.status_code == 422

    def test_invalid_json_returns_400(self, client, mock_redis):
        """Invalid JSON should return 400."""
        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post(
                "/webhook",
                content="not json",
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 400


# ══════════════════════════════════════════════════════════
# WEBHOOK SECRET TESTS
# ══════════════════════════════════════════════════════════


class TestWebhookSecret:
    """Tests for webhook secret validation."""

    def test_accepts_valid_secret_in_header(self, client, valid_entry_payload, mock_redis):
        """Should accept valid secret in X-Webhook-Secret header."""
        with patch("backend.main.get_redis", return_value=mock_redis), \
             patch("backend.main.get_settings") as mock_settings:

            mock_settings.return_value.webhook_secret = "test-secret"
            mock_settings.return_value.redis_url = "redis://localhost:6379"

            response = client.post(
                "/webhook",
                json=valid_entry_payload,
                headers={"X-Webhook-Secret": "test-secret"}
            )

        assert response.status_code == 200

    def test_accepts_valid_secret_in_query(self, client, valid_entry_payload, mock_redis):
        """Should accept valid secret in query parameter."""
        with patch("backend.main.get_redis", return_value=mock_redis), \
             patch("backend.main.get_settings") as mock_settings:

            mock_settings.return_value.webhook_secret = "test-secret"
            mock_settings.return_value.redis_url = "redis://localhost:6379"

            response = client.post(
                "/webhook?secret=test-secret",
                json=valid_entry_payload,
            )

        assert response.status_code == 200

    def test_rejects_invalid_secret(self, client, valid_entry_payload, mock_redis):
        """Should reject invalid secret with 401."""
        with patch("backend.main.get_redis", return_value=mock_redis), \
             patch("backend.main.get_settings") as mock_settings:

            mock_settings.return_value.webhook_secret = "correct-secret"
            mock_settings.return_value.redis_url = "redis://localhost:6379"

            response = client.post(
                "/webhook",
                json=valid_entry_payload,
                headers={"X-Webhook-Secret": "wrong-secret"}
            )

        assert response.status_code == 401

    def test_no_secret_when_not_configured(self, client, valid_entry_payload, mock_redis):
        """Should work without secret when not configured."""
        with patch("backend.main.get_redis", return_value=mock_redis), \
             patch("backend.main.get_settings") as mock_settings:

            mock_settings.return_value.webhook_secret = ""  # Not configured
            mock_settings.return_value.redis_url = "redis://localhost:6379"

            response = client.post("/webhook", json=valid_entry_payload)

        assert response.status_code == 200


# ══════════════════════════════════════════════════════════
# HEALTH CHECK TESTS
# ══════════════════════════════════════════════════════════


class TestHealthCheck:
    """Tests for health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_ok(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"


# ══════════════════════════════════════════════════════════
# PAYLOAD HANDLING TESTS
# ══════════════════════════════════════════════════════════


class TestPayloadHandling:
    """Tests for various payload handling scenarios."""

    def test_extra_fields_preserved(self, client, mock_redis):
        """Extra fields in payload should be preserved."""
        payload = {
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.0850,
            "sl": 1.0800,
            "tp": 1.0950,
            "size": 0.10,
            "custom_field": "custom_value",
            "zone_id": 12345,
        }

        with patch("backend.main.get_redis", return_value=mock_redis):
            client.post("/webhook", json=payload)

        call_args = mock_redis.rpush.call_args
        enqueued = json.loads(call_args[0][1])

        assert enqueued.get("custom_field") == "custom_value"
        assert enqueued.get("zone_id") == 12345

    def test_float_values_preserved(self, client, mock_redis):
        """Float values should be preserved exactly."""
        payload = {
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.08567,
            "sl": 1.08234,
            "tp": 1.09123,
            "size": 0.123,
        }

        with patch("backend.main.get_redis", return_value=mock_redis):
            client.post("/webhook", json=payload)

        call_args = mock_redis.rpush.call_args
        enqueued = json.loads(call_args[0][1])

        assert enqueued["entry"] == 1.08567
        assert enqueued["sl"] == 1.08234
        assert enqueued["size"] == 0.123

    def test_handles_tradingview_placeholder(self, client, mock_redis):
        """Should handle TradingView placeholders in body."""
        # TradingView may send {{placeholder}} that didn't resolve
        raw_body = b'{"symbol": "EURUSD", "side": "buy", "entry": {{close}}, "sl": 1.0800, "tp": 1.0950, "size": 0.10}'

        with patch("backend.main.get_redis", return_value=mock_redis):
            response = client.post(
                "/webhook",
                content=raw_body,
                headers={"Content-Type": "application/json"}
            )

        # Should handle gracefully (either replace with null or error)
        # Current implementation replaces {{...}} with null
        assert response.status_code in [200, 400, 422]


# ══════════════════════════════════════════════════════════
# REAL REDIS TESTS (Skip if Redis not available)
# ══════════════════════════════════════════════════════════


class TestRealRedisFlow:
    """Tests using real Redis connection."""

    def test_webhook_to_redis_roundtrip(self, client, redis_client, valid_entry_payload):
        """Full roundtrip: webhook -> redis -> verify in queue."""
        # Use test queue
        test_queue = "trading_queue_e2e_test"

        # Patch to use test queue
        with patch("backend.main.QUEUE_NAME", test_queue), \
             patch("backend.main.get_redis", return_value=redis_client):

            # Clear queue
            redis_client.delete(test_queue)

            # Send webhook
            response = client.post("/webhook", json=valid_entry_payload)
            assert response.status_code == 200

            # Verify in queue
            length = redis_client.llen(test_queue)
            assert length == 1

            # Dequeue and verify
            item = redis_client.lpop(test_queue)
            assert item is not None

            decoded = json.loads(item)
            assert decoded["symbol"] == valid_entry_payload["symbol"]

            # Cleanup
            redis_client.delete(test_queue)

    def test_multiple_webhooks_fifo_order(self, client, redis_client):
        """Multiple webhooks should be queued in FIFO order."""
        test_queue = "trading_queue_e2e_test"

        with patch("backend.main.QUEUE_NAME", test_queue), \
             patch("backend.main.get_redis", return_value=redis_client):

            redis_client.delete(test_queue)

            # Send multiple webhooks
            payloads = [
                {"symbol": "EURUSD", "side": "buy", "entry": 1.0850, "sl": 1.0800, "tp": 1.0950, "size": 0.10, "order": 1},
                {"symbol": "GBPUSD", "side": "sell", "entry": 1.2650, "sl": 1.2700, "tp": 1.2550, "size": 0.15, "order": 2},
                {"symbol": "USDJPY", "side": "buy", "entry": 150.50, "sl": 149.50, "tp": 152.00, "size": 0.08, "order": 3},
            ]

            for payload in payloads:
                response = client.post("/webhook", json=payload)
                assert response.status_code == 200

            # Verify count
            assert redis_client.llen(test_queue) == 3

            # Verify order
            for expected in payloads:
                item = redis_client.lpop(test_queue)
                decoded = json.loads(item)
                assert decoded["order"] == expected["order"]

            redis_client.delete(test_queue)
