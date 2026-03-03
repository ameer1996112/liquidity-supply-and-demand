"""Tests for the SignalTransport abstraction (P0-2).

Verifies:
  - InMemoryTransport round-trip without Redis
  - RedisTransport delegates to redis_queue helpers
  - Factory respects SIGNAL_TRANSPORT setting
  - set_transport() / reset_transport() injection for tests
"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.transport import (
    InMemoryTransport,
    RedisTransport,
    SignalTransport,
    get_transport,
    reset_transport,
    set_transport,
)


# ═══════════════════════════════════════════════════════════════
# InMemoryTransport
# ═══════════════════════════════════════════════════════════════


class InMemoryTransportTests(unittest.TestCase):
    def setUp(self):
        self.transport = InMemoryTransport()

    def test_enqueue_dequeue_roundtrip(self):
        payload = json.dumps({"symbol": "XAUUSD", "side": "buy"})
        self.transport.enqueue(payload)
        result = self.transport.dequeue(timeout=1)

        self.assertIsNotNone(result)
        key, data = result
        self.assertEqual(key, "memory_queue")
        self.assertEqual(data, payload)

    def test_dequeue_empty_returns_none(self):
        result = self.transport.dequeue(timeout=0)
        self.assertIsNone(result)

    def test_fifo_ordering(self):
        self.transport.enqueue('{"n":1}')
        self.transport.enqueue('{"n":2}')
        self.transport.enqueue('{"n":3}')

        results = []
        for _ in range(3):
            item = self.transport.dequeue()
            self.assertIsNotNone(item)
            results.append(json.loads(item[1])["n"])

        self.assertEqual(results, [1, 2, 3])

    def test_queue_size(self):
        self.assertEqual(self.transport.queue_size, 0)
        self.transport.enqueue('{"a":1}')
        self.transport.enqueue('{"b":2}')
        self.assertEqual(self.transport.queue_size, 2)
        self.transport.dequeue()
        self.assertEqual(self.transport.queue_size, 1)

    def test_dead_letter(self):
        payload = json.dumps({"symbol": "EURUSD"})
        self.transport.dead_letter(payload, "test error", attempt=2)

        dls = self.transport.dead_letters
        self.assertEqual(len(dls), 1)
        self.assertEqual(dls[0]["error"], "test error")
        self.assertEqual(dls[0]["attempt"], 2)
        self.assertEqual(dls[0]["payload"]["symbol"], "EURUSD")
        self.assertTrue(dls[0]["id"].startswith("dl-"))
        self.assertIn("failed_at", dls[0])

    def test_ping_always_true(self):
        self.assertTrue(self.transport.ping())

    def test_reset_is_noop(self):
        self.transport.enqueue('{"x":1}')
        self.transport.reset()
        result = self.transport.dequeue()
        self.assertIsNotNone(result)

    def test_implements_abc(self):
        self.assertIsInstance(self.transport, SignalTransport)


# ═══════════════════════════════════════════════════════════════
# RedisTransport (mocked — no real Redis needed)
# ═══════════════════════════════════════════════════════════════


class RedisTransportTests(unittest.TestCase):
    def setUp(self):
        self.transport = RedisTransport()

    @patch("src.adapters.redis_queue.push_payload")
    def test_enqueue_delegates(self, mock_push):
        self.transport.enqueue('{"symbol":"XAUUSD"}')
        mock_push.assert_called_once_with('{"symbol":"XAUUSD"}')

    @patch("src.adapters.redis_queue.blpop_queue", return_value=("trading_queue", '{"side":"buy"}'))
    def test_dequeue_delegates(self, mock_blpop):
        result = self.transport.dequeue(timeout=3)
        mock_blpop.assert_called_once_with(timeout=3)
        self.assertEqual(result, ("trading_queue", '{"side":"buy"}'))

    @patch("src.adapters.redis_queue.blpop_queue", return_value=None)
    def test_dequeue_none_on_timeout(self, mock_blpop):
        result = self.transport.dequeue(timeout=1)
        self.assertIsNone(result)

    @patch("src.adapters.redis_queue.push_dead_letter")
    def test_dead_letter_delegates(self, mock_dl):
        self.transport.dead_letter('{"x":1}', "boom", attempt=3)
        mock_dl.assert_called_once_with('{"x":1}', "boom", 3)

    @patch("src.adapters.redis_queue.ping_redis", return_value=True)
    def test_ping_delegates(self, mock_ping):
        self.assertTrue(self.transport.ping())
        mock_ping.assert_called_once()

    @patch("src.adapters.redis_queue.reset_redis_client")
    def test_reset_delegates(self, mock_reset):
        self.transport.reset()
        mock_reset.assert_called_once()

    def test_implements_abc(self):
        self.assertIsInstance(self.transport, SignalTransport)


# ═══════════════════════════════════════════════════════════════
# Factory: get_transport / set_transport / reset_transport
# ═══════════════════════════════════════════════════════════════


class TransportFactoryTests(unittest.TestCase):
    def setUp(self):
        reset_transport()

    def tearDown(self):
        reset_transport()

    @patch("config.get_settings")
    def test_factory_defaults_to_redis(self, mock_settings):
        mock_settings.return_value = SimpleNamespace(signal_transport="redis")
        t = get_transport()
        self.assertIsInstance(t, RedisTransport)

    @patch("config.get_settings")
    def test_factory_creates_memory_transport(self, mock_settings):
        mock_settings.return_value = SimpleNamespace(signal_transport="memory")
        t = get_transport()
        self.assertIsInstance(t, InMemoryTransport)

    @patch("config.get_settings")
    def test_factory_is_singleton(self, mock_settings):
        mock_settings.return_value = SimpleNamespace(signal_transport="memory")
        t1 = get_transport()
        t2 = get_transport()
        self.assertIs(t1, t2)
        mock_settings.assert_called_once()

    def test_set_transport_overrides(self):
        custom = InMemoryTransport()
        set_transport(custom)
        self.assertIs(get_transport(), custom)

    def test_reset_transport_clears_singleton(self):
        set_transport(InMemoryTransport())
        reset_transport()
        with patch("config.get_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(signal_transport="memory")
            t = get_transport()
            self.assertIsInstance(t, InMemoryTransport)
            mock_settings.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Integration: full enqueue → dequeue → dead-letter cycle
# ═══════════════════════════════════════════════════════════════


class InMemoryIntegrationTests(unittest.TestCase):
    """Simulates a simplified worker loop using InMemoryTransport."""

    def test_end_to_end_signal_flow(self):
        transport = InMemoryTransport()

        payloads = [
            {"symbol": "XAUUSD", "side": "buy", "size": 0.5},
            {"symbol": "EURUSD", "side": "sell", "size": 0.1},
        ]
        for p in payloads:
            transport.enqueue(json.dumps(p))

        self.assertEqual(transport.queue_size, 2)

        processed = []
        while True:
            task = transport.dequeue(timeout=0)
            if task is None:
                break
            _key, payload_str = task
            processed.append(json.loads(payload_str))

        self.assertEqual(len(processed), 2)
        self.assertEqual(processed[0]["symbol"], "XAUUSD")
        self.assertEqual(processed[1]["symbol"], "EURUSD")
        self.assertEqual(transport.queue_size, 0)

    def test_dead_letter_on_bad_payload(self):
        transport = InMemoryTransport()
        bad_json = '{"symbol": "XAUUSD", "size": "not_a_number"}'
        transport.enqueue(bad_json)

        task = transport.dequeue()
        self.assertIsNotNone(task)
        _key, payload_str = task

        try:
            payload = json.loads(payload_str)
            size = float(payload["size"])
            raise AssertionError("Should have failed")
        except (ValueError, AssertionError):
            transport.dead_letter(payload_str, "Invalid size field")

        self.assertEqual(len(transport.dead_letters), 1)
        self.assertEqual(transport.dead_letters[0]["error"], "Invalid size field")
        self.assertEqual(transport.queue_size, 0)


if __name__ == "__main__":
    unittest.main()
