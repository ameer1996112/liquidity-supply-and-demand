"""
Sprint 4.3: Reflection + Memory loop tests.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.services.reflection_service import (
    _compute_r_multiple,
    _build_reflection_content,
    create_reflection_on_close,
    create_reflection_on_close_safe,
)
from src.services.memory_retrieval import (
    retrieve_similar_reflections,
    format_reflections_for_prompt,
)


class ReflectionServiceTests(unittest.TestCase):
    """Tests for reflection creation on close."""

    def test_compute_r_multiple_buy_win(self):
        # Buy: entry 100, sl 98, tp 106. Risk=2. Exit at 106, gain=6 → 6/2 = 3R
        r = _compute_r_multiple(100, 98, 106, 106, "buy")
        self.assertAlmostEqual(r, 3.0, places=2)

    def test_compute_r_multiple_buy_loss(self):
        # Buy: exit at sl = -1R
        r = _compute_r_multiple(100, 98, 106, 98, "buy")
        self.assertAlmostEqual(r, -1.0, places=2)

    def test_compute_r_multiple_sell_win(self):
        # Sell: entry 100, sl 102, tp 94. Risk=2. Exit at 94, gain=6 → 6/2 = 3R
        r = _compute_r_multiple(100, 102, 94, 94, "sell")
        self.assertAlmostEqual(r, 3.0, places=2)

    def test_compute_r_multiple_missing_data(self):
        self.assertIsNone(_compute_r_multiple(0, 98, 106, 106, "buy"))
        self.assertIsNone(_compute_r_multiple(100, 0, 106, 106, "buy"))

    def test_build_reflection_content(self):
        signal = {
            "symbol": "XAUUSD",
            "side": "buy",
            "zone_type": "demand",
            "entry_model": "FLIP",
            "outcome": "win",
            "score": 72,
        }
        content = _build_reflection_content(signal, "Strong zone", "Tighten entry")
        self.assertIn("XAUUSD", content)
        self.assertIn("demand", content)
        self.assertIn("Strong zone", content)
        self.assertIn("Tighten entry", content)

    @patch("src.services.reflection_service.get_settings")
    def test_create_reflection_skipped_when_memory_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(memory_enabled=False)
        sb = MagicMock()
        result = create_reflection_on_close(sb, 1, {"outcome": "win", "entry": 2650, "sl": 2640, "tp": 2670, "exit_price": 2670, "side": "buy"})
        self.assertIsNone(result)
        sb.table.assert_not_called()

    @patch("src.services.reflection_service._get_embedding")
    @patch("src.services.reflection_service.get_settings")
    def test_create_reflection_on_close_creates_record(self, mock_settings, mock_embed):
        mock_settings.return_value = MagicMock(memory_enabled=True)
        mock_embed.return_value = [0.1] * 1536  # Mock embedding

        sb = MagicMock()
        # entry 2650, sl 2640, tp 2670, exit 2670: risk=10, gain=20 → 2R
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "trade_id": 42, "outcome": "win", "r_multiple": 2.0}]
        )

        signal = {
            "id": 42,
            "symbol": "XAUUSD",
            "side": "buy",
            "zone_type": "demand",
            "entry_model": "FLIP",
            "outcome": "win",
            "entry": 2650,
            "sl": 2640,
            "tp": 2670,
            "exit_price": 2670,
            "score": 72,
        }
        result = create_reflection_on_close(sb, 42, signal)
        self.assertIsNotNone(result)
        self.assertEqual(result["trade_id"], 42)
        sb.table.assert_called_with("trade_reflections")
        sb.table.return_value.upsert.assert_called_once()
        call_args = sb.table.return_value.upsert.call_args[0][0]
        self.assertEqual(call_args["trade_id"], 42)
        self.assertEqual(call_args["outcome"], "win")
        self.assertAlmostEqual(call_args["r_multiple"], 2.0, places=2)
        self.assertIn("embedding", call_args)

    def test_create_reflection_on_close_safe_never_raises(self):
        sb = None
        create_reflection_on_close_safe(sb, 1)  # Should not raise


class MemoryRetrievalTests(unittest.TestCase):
    """Tests for memory retrieval (mock embeddings allowed)."""

    def test_format_reflections_for_prompt_empty(self):
        self.assertEqual(format_reflections_for_prompt([]), "")

    def test_format_reflections_for_prompt(self):
        reflections = [
            {"outcome": "win", "reasons": "Strong zone", "what_to_improve": "None", "r_multiple": 2.0},
            {"outcome": "loss", "reasons": "Zone broke", "what_to_improve": "Wait for sweep", "r_multiple": -1.0},
        ]
        text = format_reflections_for_prompt(reflections)
        self.assertIn("Similar past situations", text)
        self.assertIn("win", text)
        self.assertIn("loss", text)
        self.assertIn("Strong zone", text)
        self.assertIn("Zone broke", text)

    @patch("src.services.memory_retrieval.get_settings")
    def test_retrieve_similar_reflections_skipped_when_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(memory_enabled=False)
        sb = MagicMock()
        result = retrieve_similar_reflections(sb, {"symbol": "XAUUSD", "side": "buy"})
        self.assertEqual(result, [])
        sb.rpc.assert_not_called()

    @patch("src.services.memory_retrieval._get_embedding")
    @patch("src.services.memory_retrieval.get_settings")
    def test_retrieve_similar_reflections_returns_expected_items(self, mock_settings, mock_embed):
        mock_settings.return_value = MagicMock(memory_enabled=True)
        mock_embed.return_value = [0.1] * 1536

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {"id": 1, "trade_id": 10, "outcome": "win", "reasons": "Strong demand", "what_to_improve": "", "r_multiple": 1.5},
                {"id": 2, "trade_id": 11, "outcome": "loss", "reasons": "Zone broke", "what_to_improve": "Wait sweep", "r_multiple": -1.0},
            ]
        )

        payload = {"symbol": "XAUUSD", "side": "buy", "zone_type": "demand", "entry_model": "FLIP"}
        result = retrieve_similar_reflections(sb, payload, k=3)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["outcome"], "win")
        self.assertEqual(result[1]["outcome"], "loss")
        sb.rpc.assert_called_once_with("match_trade_reflections", {"query_embedding": [0.1] * 1536, "match_count": 3})
