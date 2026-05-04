from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.services.ai_decision_cache import (
    build_cache_key,
    cache_get,
    cache_set,
    candle_context_hash,
    signal_hash,
)


class AiDecisionCacheTests(unittest.TestCase):
    def test_signal_hash_deterministic(self):
        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2650,
            "sl": 2640,
            "tp": 2670,
        }

        self.assertEqual(signal_hash(payload), signal_hash(payload))

    def test_signal_hash_different_payloads(self):
        first_hash = signal_hash({"symbol": "XAUUSD", "side": "buy"})
        second_hash = signal_hash({"symbol": "EURUSD", "side": "sell"})

        self.assertNotEqual(first_hash, second_hash)

    def test_build_cache_key(self):
        cache_key = build_cache_key("abc", "def", "gpt-4")

        self.assertIsInstance(cache_key, str)
        self.assertEqual(len(cache_key), 32)

    def test_candle_context_hash_empty(self):
        self.assertEqual(len(candle_context_hash([])), 32)

    def test_cache_set_get(self):
        mock_supabase = MagicMock()

        cache_set(mock_supabase, "key123", {"decision": "GO", "rf_prob": 0.7})

        mock_supabase.table.assert_called_with("ai_decision_cache")
        mock_supabase.table.return_value.upsert.assert_called_once()

    def test_cache_get_miss(self):
        mock_supabase = MagicMock()
        (
            mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value
        ) = MagicMock(data=[])

        self.assertIsNone(cache_get(mock_supabase, "nonexistent"))

    def test_cache_get_hit(self):
        mock_supabase = MagicMock()
        (
            mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value
        ) = MagicMock(data=[{"decision_json": {"decision": "GO", "rf_prob": 0.8}}])

        result = cache_get(mock_supabase, "hit_key")

        self.assertIsNotNone(result)
        self.assertEqual(result["decision"], "GO")
