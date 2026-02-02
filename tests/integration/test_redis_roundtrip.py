"""
Integration Tests for Redis Queue Roundtrip

Tests the Redis queue operations:
1. Enqueue/dequeue cycle
2. Payload integrity
3. Queue ordering (FIFO)
4. Multiple signal handling

Requires Redis running (use docker-compose.test.yml).
"""

import json
import pytest
import time

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# ══════════════════════════════════════════════════════════
# BASIC ROUNDTRIP TESTS
# ══════════════════════════════════════════════════════════


class TestRedisRoundtrip:
    """Tests for basic Redis enqueue/dequeue operations."""

    def test_enqueue_dequeue_single_signal(self, redis_client, test_queue_name, base_signal):
        """Should enqueue and dequeue a single signal correctly."""
        # Enqueue
        payload_str = json.dumps(base_signal)
        redis_client.rpush(test_queue_name, payload_str)

        # Verify queue has item
        length = redis_client.llen(test_queue_name)
        assert length == 1

        # Dequeue
        result = redis_client.lpop(test_queue_name)
        assert result is not None

        # Parse and verify
        decoded = json.loads(result)
        assert decoded["symbol"] == base_signal["symbol"]
        assert decoded["side"] == base_signal["side"]

    def test_payload_integrity_preserved(self, redis_client, test_queue_name, base_signal):
        """Payload should be preserved exactly through queue."""
        # Enqueue
        payload_str = json.dumps(base_signal)
        redis_client.rpush(test_queue_name, payload_str)

        # Dequeue
        result = redis_client.lpop(test_queue_name)
        decoded = json.loads(result)

        # Verify all fields match
        assert decoded["symbol"] == base_signal["symbol"]
        assert decoded["side"] == base_signal["side"]
        assert decoded["entry"] == base_signal["entry"]
        assert decoded["sl"] == base_signal["sl"]
        assert decoded["tp"] == base_signal["tp"]
        assert decoded["size"] == base_signal["size"]
        assert decoded.get("zone_id") == base_signal.get("zone_id")

    def test_queue_is_fifo(self, redis_client, test_queue_name):
        """Queue should maintain FIFO order."""
        # Enqueue in order
        signals = [
            {"symbol": "EURUSD", "order": 1},
            {"symbol": "GBPUSD", "order": 2},
            {"symbol": "USDJPY", "order": 3},
        ]

        for signal in signals:
            redis_client.rpush(test_queue_name, json.dumps(signal))

        # Dequeue and verify order
        for expected in signals:
            result = redis_client.lpop(test_queue_name)
            decoded = json.loads(result)
            assert decoded["order"] == expected["order"]
            assert decoded["symbol"] == expected["symbol"]

    def test_empty_queue_returns_none(self, redis_client, test_queue_name):
        """Empty queue should return None on lpop."""
        # Ensure queue is empty
        redis_client.delete(test_queue_name)

        result = redis_client.lpop(test_queue_name)
        assert result is None


# ══════════════════════════════════════════════════════════
# BLOCKING POP TESTS
# ══════════════════════════════════════════════════════════


class TestBlockingPop:
    """Tests for blocking pop operations (like worker uses)."""

    def test_blpop_returns_immediately_when_data_present(self, redis_client, test_queue_name, base_signal):
        """blpop should return immediately when queue has data."""
        # Enqueue first
        redis_client.rpush(test_queue_name, json.dumps(base_signal))

        # blpop should return immediately
        start = time.time()
        result = redis_client.blpop(test_queue_name, timeout=5)
        elapsed = time.time() - start

        assert result is not None
        assert elapsed < 1.0  # Should be nearly instant

        _key, payload_str = result
        decoded = json.loads(payload_str)
        assert decoded["symbol"] == base_signal["symbol"]

    def test_blpop_times_out_on_empty_queue(self, redis_client, test_queue_name):
        """blpop should timeout on empty queue."""
        # Ensure queue is empty
        redis_client.delete(test_queue_name)

        start = time.time()
        result = redis_client.blpop(test_queue_name, timeout=1)
        elapsed = time.time() - start

        assert result is None
        assert elapsed >= 0.9  # Should wait close to timeout


# ══════════════════════════════════════════════════════════
# MULTIPLE SIGNALS TESTS
# ══════════════════════════════════════════════════════════


class TestMultipleSignals:
    """Tests for handling multiple signals in queue."""

    def test_enqueue_multiple_signals(self, redis_client, test_queue_name):
        """Should handle enqueueing multiple signals."""
        signals = [
            {"symbol": "EURUSD", "side": "buy", "size": 0.10},
            {"symbol": "GBPUSD", "side": "sell", "size": 0.15},
            {"symbol": "USDJPY", "side": "buy", "size": 0.08},
            {"symbol": "XAUUSD", "side": "sell", "size": 0.05},
        ]

        for signal in signals:
            redis_client.rpush(test_queue_name, json.dumps(signal))

        length = redis_client.llen(test_queue_name)
        assert length == len(signals)

    def test_dequeue_all_signals(self, redis_client, test_queue_name):
        """Should be able to dequeue all enqueued signals."""
        signals = [
            {"symbol": "EURUSD", "id": 1},
            {"symbol": "GBPUSD", "id": 2},
            {"symbol": "USDJPY", "id": 3},
        ]

        for signal in signals:
            redis_client.rpush(test_queue_name, json.dumps(signal))

        dequeued = []
        while True:
            result = redis_client.lpop(test_queue_name)
            if result is None:
                break
            dequeued.append(json.loads(result))

        assert len(dequeued) == len(signals)
        for i, decoded in enumerate(dequeued):
            assert decoded["id"] == i + 1


# ══════════════════════════════════════════════════════════
# PAYLOAD TYPES TESTS
# ══════════════════════════════════════════════════════════


class TestPayloadTypes:
    """Tests for different payload types and edge cases."""

    def test_handles_nested_objects(self, redis_client, test_queue_name):
        """Should handle payloads with nested objects."""
        signal = {
            "symbol": "EURUSD",
            "side": "buy",
            "metadata": {
                "zone": {"top": 1.0900, "bottom": 1.0850},
                "indicators": {"rsi": 45, "atr": 0.0012},
            },
        }

        redis_client.rpush(test_queue_name, json.dumps(signal))
        result = redis_client.lpop(test_queue_name)
        decoded = json.loads(result)

        assert decoded["metadata"]["zone"]["top"] == 1.0900
        assert decoded["metadata"]["indicators"]["rsi"] == 45

    def test_handles_float_precision(self, redis_client, test_queue_name):
        """Should preserve float precision."""
        signal = {
            "symbol": "EURUSD",
            "entry": 1.08567,
            "sl": 1.08234,
            "size": 0.123,
        }

        redis_client.rpush(test_queue_name, json.dumps(signal))
        result = redis_client.lpop(test_queue_name)
        decoded = json.loads(result)

        assert decoded["entry"] == 1.08567
        assert decoded["sl"] == 1.08234
        assert decoded["size"] == 0.123

    def test_handles_special_characters(self, redis_client, test_queue_name):
        """Should handle special characters in string fields."""
        signal = {
            "symbol": "EURUSD",
            "notes": "Test with special chars: < > & \" ' \\ /",
            "signal": "FLIP|DIR_CLOSE",
        }

        redis_client.rpush(test_queue_name, json.dumps(signal))
        result = redis_client.lpop(test_queue_name)
        decoded = json.loads(result)

        assert decoded["notes"] == signal["notes"]
        assert decoded["signal"] == "FLIP|DIR_CLOSE"

    def test_handles_boolean_fields(self, redis_client, test_queue_name):
        """Should handle boolean fields."""
        signal = {
            "symbol": "EURUSD",
            "liq_swept": True,
            "target_swept": False,
            "is_accuracy": True,
        }

        redis_client.rpush(test_queue_name, json.dumps(signal))
        result = redis_client.lpop(test_queue_name)
        decoded = json.loads(result)

        assert decoded["liq_swept"] is True
        assert decoded["target_swept"] is False
        assert decoded["is_accuracy"] is True


# ══════════════════════════════════════════════════════════
# QUEUE CLEANUP TESTS
# ══════════════════════════════════════════════════════════


class TestQueueCleanup:
    """Tests for queue cleanup operations."""

    def test_delete_clears_queue(self, redis_client, test_queue_name, base_signal):
        """DELETE should clear all items from queue."""
        # Add items
        for _ in range(5):
            redis_client.rpush(test_queue_name, json.dumps(base_signal))

        assert redis_client.llen(test_queue_name) == 5

        # Delete queue
        redis_client.delete(test_queue_name)

        assert redis_client.llen(test_queue_name) == 0

    def test_ltrim_can_limit_queue_size(self, redis_client, test_queue_name):
        """LTRIM can be used to limit queue size."""
        # Add 10 items
        for i in range(10):
            redis_client.rpush(test_queue_name, json.dumps({"id": i}))

        # Keep only first 5
        redis_client.ltrim(test_queue_name, 0, 4)

        assert redis_client.llen(test_queue_name) == 5

        # Verify first items are kept
        first = json.loads(redis_client.lindex(test_queue_name, 0))
        assert first["id"] == 0


# ══════════════════════════════════════════════════════════
# QUEUE NAME TESTS
# ══════════════════════════════════════════════════════════


class TestQueueName:
    """Tests for queue name handling."""

    def test_production_queue_name_is_trading_queue(self):
        """Production queue name should be 'trading_queue'."""
        from src.worker import QUEUE_NAME

        assert QUEUE_NAME == "trading_queue"

    def test_main_queue_name_matches_worker(self):
        """Main and worker should use same queue name."""
        from src.api import QUEUE_NAME as MAIN_QUEUE
        from src.worker import QUEUE_NAME as WORKER_QUEUE

        assert MAIN_QUEUE == WORKER_QUEUE


# ══════════════════════════════════════════════════════════
# CONNECTION TESTS
# ══════════════════════════════════════════════════════════


class TestRedisConnection:
    """Tests for Redis connection handling."""

    def test_ping_works(self, redis_client):
        """Should be able to ping Redis."""
        assert redis_client.ping() is True

    def test_connection_from_url(self, redis_url):
        """Should be able to connect using URL."""
        import redis

        client = redis.from_url(redis_url, decode_responses=True)
        assert client.ping() is True
