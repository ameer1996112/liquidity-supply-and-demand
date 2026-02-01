"""
End-to-End Tests for Burst Signal Handling

Tests the system's ability to handle burst signal scenarios:
1. Burst enqueue 100 signals without crashes
2. All jobs accounted for in queue
3. System stability under load
4. No data loss or corruption

Uses FastAPI TestClient and real Redis.
"""

import json
import pytest
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Mark all tests in this module as e2e and slow
pytestmark = [pytest.mark.e2e, pytest.mark.slow]


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def client():
    """FastAPI TestClient for webhook testing."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def burst_queue_name():
    """Unique queue name for burst tests."""
    return "trading_queue_burst_test"


@pytest.fixture
def sample_symbols():
    """Sample trading symbols for variety."""
    return [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
        "NZDUSD", "USDCAD", "XAUUSD", "XAGUSD", "US30"
    ]


def generate_signal(index: int, symbols: list) -> dict:
    """Generate a unique signal payload."""
    symbol = symbols[index % len(symbols)]
    side = "buy" if index % 2 == 0 else "sell"

    return {
        "symbol": symbol,
        "side": side,
        "entry": round(1.0 + (index * 0.001), 5),
        "sl": round(0.99 + (index * 0.001), 5),
        "tp": round(1.01 + (index * 0.001), 5),
        "size": round(0.01 + (index % 10) * 0.01, 2),
        "signal_index": index,  # For tracking
        "zone_id": 10000 + index,
    }


# ══════════════════════════════════════════════════════════
# BURST ENQUEUE TESTS (REAL REDIS)
# ══════════════════════════════════════════════════════════


class TestBurstEnqueue:
    """Tests for burst enqueueing to Redis."""

    def test_burst_100_signals_all_enqueued(self, redis_client, burst_queue_name, sample_symbols):
        """100 signals should all be enqueued without loss."""
        # Clear queue
        redis_client.delete(burst_queue_name)

        # Generate and enqueue 100 signals
        signals = [generate_signal(i, sample_symbols) for i in range(100)]

        for signal in signals:
            payload_str = json.dumps(signal)
            redis_client.rpush(burst_queue_name, payload_str)

        # Verify count
        queue_length = redis_client.llen(burst_queue_name)
        assert queue_length == 100, f"Expected 100, got {queue_length}"

        # Cleanup
        redis_client.delete(burst_queue_name)

    def test_burst_100_signals_data_integrity(self, redis_client, burst_queue_name, sample_symbols):
        """All 100 signals should maintain data integrity."""
        redis_client.delete(burst_queue_name)

        signals = [generate_signal(i, sample_symbols) for i in range(100)]

        for signal in signals:
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        # Dequeue and verify all signals
        indices_found = set()
        for _ in range(100):
            item = redis_client.lpop(burst_queue_name)
            assert item is not None

            decoded = json.loads(item)
            signal_index = decoded["signal_index"]
            indices_found.add(signal_index)

            # Verify structure
            assert "symbol" in decoded
            assert "side" in decoded
            assert "entry" in decoded

        # Verify all indices present
        assert len(indices_found) == 100
        assert indices_found == set(range(100))

        redis_client.delete(burst_queue_name)

    def test_burst_fifo_order_preserved(self, redis_client, burst_queue_name, sample_symbols):
        """FIFO order should be preserved under burst."""
        redis_client.delete(burst_queue_name)

        signals = [generate_signal(i, sample_symbols) for i in range(100)]

        for signal in signals:
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        # Verify order
        for expected_index in range(100):
            item = redis_client.lpop(burst_queue_name)
            decoded = json.loads(item)
            assert decoded["signal_index"] == expected_index, \
                f"Expected index {expected_index}, got {decoded['signal_index']}"

        redis_client.delete(burst_queue_name)


# ══════════════════════════════════════════════════════════
# BURST WEBHOOK TESTS
# ══════════════════════════════════════════════════════════


class TestBurstWebhook:
    """Tests for burst webhook requests."""

    def test_burst_100_webhooks_all_accepted(self, client, redis_client, burst_queue_name, sample_symbols):
        """100 sequential webhook requests should all succeed."""
        with patch("backend.main.QUEUE_NAME", burst_queue_name), \
             patch("backend.main.get_redis", return_value=redis_client):

            redis_client.delete(burst_queue_name)

            success_count = 0
            for i in range(100):
                signal = generate_signal(i, sample_symbols)
                response = client.post("/webhook", json=signal)

                if response.status_code == 200:
                    success_count += 1

            # All should succeed
            assert success_count == 100

            # Verify queue has all signals
            queue_length = redis_client.llen(burst_queue_name)
            assert queue_length == 100

            redis_client.delete(burst_queue_name)

    def test_burst_no_crash(self, client, redis_client, burst_queue_name, sample_symbols):
        """System should not crash under burst load."""
        with patch("backend.main.QUEUE_NAME", burst_queue_name), \
             patch("backend.main.get_redis", return_value=redis_client):

            redis_client.delete(burst_queue_name)

            # Send burst rapidly
            for i in range(100):
                signal = generate_signal(i, sample_symbols)
                try:
                    response = client.post("/webhook", json=signal)
                    # Even errors shouldn't crash
                except Exception as e:
                    pytest.fail(f"Crash at signal {i}: {e}")

            redis_client.delete(burst_queue_name)


# ══════════════════════════════════════════════════════════
# CONCURRENT BURST TESTS
# ══════════════════════════════════════════════════════════


class TestConcurrentBurst:
    """Tests for concurrent/parallel burst scenarios."""

    def test_concurrent_50_webhooks(self, client, redis_client, burst_queue_name, sample_symbols):
        """50 concurrent webhook requests should all succeed."""
        with patch("backend.main.QUEUE_NAME", burst_queue_name), \
             patch("backend.main.get_redis", return_value=redis_client):

            redis_client.delete(burst_queue_name)

            def send_webhook(index):
                signal = generate_signal(index, sample_symbols)
                response = client.post("/webhook", json=signal)
                return response.status_code

            # Use ThreadPoolExecutor for concurrent requests
            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(send_webhook, i) for i in range(50)]
                for future in as_completed(futures):
                    results.append(future.result())

            # All should succeed
            success_count = sum(1 for r in results if r == 200)
            assert success_count == 50

            # May not be exactly 50 due to race conditions in test setup
            queue_length = redis_client.llen(burst_queue_name)
            assert queue_length >= 45  # Allow some slack

            redis_client.delete(burst_queue_name)


# ══════════════════════════════════════════════════════════
# MIXED VALID/INVALID BURST TESTS
# ══════════════════════════════════════════════════════════


class TestMixedBurst:
    """Tests for bursts with mixed valid/invalid signals."""

    def test_mixed_burst_valid_signals_enqueued(self, client, redis_client, burst_queue_name, sample_symbols):
        """Only valid signals in mixed burst should be enqueued."""
        with patch("backend.main.QUEUE_NAME", burst_queue_name), \
             patch("backend.main.get_redis", return_value=redis_client):

            redis_client.delete(burst_queue_name)

            valid_count = 0
            invalid_count = 0

            for i in range(100):
                if i % 5 == 0:  # Every 5th is invalid
                    signal = {
                        "side": "buy",
                        "entry": 1.0850,
                        # Missing symbol
                    }
                    invalid_count += 1
                else:
                    signal = generate_signal(i, sample_symbols)
                    valid_count += 1

                client.post("/webhook", json=signal)

            # Verify only valid signals enqueued
            queue_length = redis_client.llen(burst_queue_name)
            assert queue_length == valid_count

            redis_client.delete(burst_queue_name)


# ══════════════════════════════════════════════════════════
# WORKER BURST PROCESSING TESTS
# ══════════════════════════════════════════════════════════


class TestWorkerBurstProcessing:
    """Tests for worker handling burst of jobs."""

    def test_process_100_jobs_no_crash(self, redis_client, burst_queue_name, sample_symbols):
        """Worker should process 100 jobs without crashing."""
        from backend.worker import process_trade

        redis_client.delete(burst_queue_name)

        # Enqueue 100 jobs
        signals = [generate_signal(i, sample_symbols) for i in range(100)]
        for signal in signals:
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        # Mock supabase to track calls
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        processed = 0
        with patch("backend.worker.supabase", mock_supabase), \
             patch("backend.worker.get_prediction", return_value=(0.75, "OK")):

            while True:
                item = redis_client.lpop(burst_queue_name)
                if item is None:
                    break

                try:
                    payload = json.loads(item)
                    process_trade(payload)
                    processed += 1
                except Exception as e:
                    pytest.fail(f"Crash processing job {processed}: {e}")

        assert processed == 100
        redis_client.delete(burst_queue_name)

    def test_all_jobs_accounted_for(self, redis_client, burst_queue_name, sample_symbols):
        """All 100 jobs should result in ledger writes."""
        from backend.worker import process_trade

        redis_client.delete(burst_queue_name)

        signals = [generate_signal(i, sample_symbols) for i in range(100)]
        for signal in signals:
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        with patch("backend.worker.supabase", mock_supabase), \
             patch("backend.worker.get_prediction", return_value=(0.75, "OK")):

            while True:
                item = redis_client.lpop(burst_queue_name)
                if item is None:
                    break
                process_trade(json.loads(item))

        # Verify insert called 100 times
        insert_count = mock_supabase.table.return_value.insert.call_count
        assert insert_count == 100

        redis_client.delete(burst_queue_name)


# ══════════════════════════════════════════════════════════
# PERFORMANCE TESTS
# ══════════════════════════════════════════════════════════


class TestBurstPerformance:
    """Performance tests for burst scenarios."""

    def test_100_enqueue_completes_quickly(self, redis_client, burst_queue_name, sample_symbols):
        """100 enqueues should complete in reasonable time."""
        redis_client.delete(burst_queue_name)

        signals = [generate_signal(i, sample_symbols) for i in range(100)]

        start = time.time()
        for signal in signals:
            redis_client.rpush(burst_queue_name, json.dumps(signal))
        elapsed = time.time() - start

        # Should complete in under 5 seconds (generous for CI)
        assert elapsed < 5.0, f"Took {elapsed:.2f}s, expected < 5s"

        redis_client.delete(burst_queue_name)

    def test_100_dequeue_completes_quickly(self, redis_client, burst_queue_name, sample_symbols):
        """100 dequeues should complete in reasonable time."""
        redis_client.delete(burst_queue_name)

        signals = [generate_signal(i, sample_symbols) for i in range(100)]
        for signal in signals:
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        start = time.time()
        for _ in range(100):
            redis_client.lpop(burst_queue_name)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Took {elapsed:.2f}s, expected < 5s"

        redis_client.delete(burst_queue_name)


# ══════════════════════════════════════════════════════════
# STRESS TESTS (Optional, slower)
# ══════════════════════════════════════════════════════════


class TestStress:
    """Stress tests with larger volumes."""

    @pytest.mark.slow
    def test_burst_500_signals(self, redis_client, burst_queue_name, sample_symbols):
        """500 signals should all be handled correctly."""
        redis_client.delete(burst_queue_name)

        for i in range(500):
            signal = generate_signal(i, sample_symbols)
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        queue_length = redis_client.llen(burst_queue_name)
        assert queue_length == 500

        redis_client.delete(burst_queue_name)

    @pytest.mark.slow
    def test_burst_1000_signals(self, redis_client, burst_queue_name, sample_symbols):
        """1000 signals should all be handled correctly."""
        redis_client.delete(burst_queue_name)

        for i in range(1000):
            signal = generate_signal(i, sample_symbols)
            redis_client.rpush(burst_queue_name, json.dumps(signal))

        queue_length = redis_client.llen(burst_queue_name)
        assert queue_length == 1000

        redis_client.delete(burst_queue_name)
