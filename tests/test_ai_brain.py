import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.ai import brain


class DummyModel:
    def __init__(self, classes):
        self.classes_ = classes


class BrainDecisionTests(unittest.TestCase):
    def test_normalize_probability_handles_pct_and_raw(self):
        self.assertAlmostEqual(brain._normalize_probability(0.336), 0.336)
        self.assertAlmostEqual(brain._normalize_probability(33.6), 0.336)
        self.assertAlmostEqual(brain._normalize_probability(120), 1.0)

    def test_positive_class_index_prefers_class_one(self):
        idx, mapping = brain._resolve_positive_class_index(DummyModel([0, 1]))
        self.assertEqual(idx, 1)
        self.assertEqual(mapping["positive_class"], 1)

    def test_dynamic_threshold_respects_entry_model_offset(self):
        settings = SimpleNamespace(
            ml_min_confidence=0.60,
            ml_use_adaptive_threshold=False,
            ml_adaptive_threshold_floor=0.30,
            ml_adaptive_threshold_margin=0.08,
            ml_flip_threshold_offset=-0.03,
            ml_break_candle_threshold_offset=0.0,
            ml_dir_close_threshold_offset=-0.01,
        )
        threshold, meta = brain._compute_dynamic_rf_threshold(
            {"entry_model": "FLIP", "zone_grade": "B", "score": 70}, settings
        )
        self.assertLess(threshold, 0.60)
        self.assertEqual(meta["entry_model"], "FLIP")

    def test_known_good_signal_can_yield_go_when_above_threshold(self):
        settings = SimpleNamespace(
            enable_llm_filter=False,
            ml_min_confidence=0.60,
            ml_use_adaptive_threshold=False,
            ml_adaptive_threshold_floor=0.30,
            ml_adaptive_threshold_margin=0.08,
            ml_flip_threshold_offset=-0.03,
            ml_break_candle_threshold_offset=0.0,
            ml_dir_close_threshold_offset=-0.01,
        )

        with patch("src.ai.brain.get_settings", return_value=settings), patch(
            "src.ai.brain.get_prediction",
            return_value=(
                0.72,
                "AI Confidence: 72.0%",
                {
                    "score": 85.0,
                    "entry_model": "FLIP",
                    "_trace_class_mapping": {"positive_class": 1, "positive_index": 1},
                    "_trace_model_type": "sklearn",
                    "_trace_feature_spec_source": "test",
                },
            ),
        ), patch("src.ai.brain.get_market_narrative", return_value="test narrative"), patch(
            "src.ai.brain._get_rag_engine", return_value=None
        ):
            result = brain.ensemble_decision(
                {"symbol": "XAUUSD", "entry_model": "FLIP", "zone_grade": "A", "score": 85}
            )

        self.assertEqual(result["decision"], "GO")
        self.assertGreaterEqual(result["rf_prob"], result["rf_threshold"])

    def test_low_probability_is_rejected_with_rf_rule(self):
        settings = SimpleNamespace(
            enable_llm_filter=False,
            ml_min_confidence=0.60,
            ml_use_adaptive_threshold=False,
            ml_adaptive_threshold_floor=0.30,
            ml_adaptive_threshold_margin=0.08,
            ml_flip_threshold_offset=-0.03,
            ml_break_candle_threshold_offset=0.0,
            ml_dir_close_threshold_offset=-0.01,
        )

        with patch("src.ai.brain.get_settings", return_value=settings), patch(
            "src.ai.brain.get_prediction",
            return_value=(0.33, "AI Confidence: 33.0%", {}),
        ), patch("src.ai.brain.get_market_narrative", return_value="test narrative"), patch(
            "src.ai.brain._get_rag_engine", return_value=None
        ):
            result = brain.ensemble_decision(
                {"symbol": "XAUUSD", "entry_model": "BREAK_CANDLE", "zone_grade": "C", "score": 50}
            )

        self.assertEqual(result["decision"], "NO_GO")
        self.assertEqual(result["decision_trace"]["rejected_rule"]["rule_id"], "rf_threshold")

    def test_llm_primary_404_retries_fallback_and_succeeds(self):
        settings = SimpleNamespace(
            enable_llm_filter=True,
            llm_model_primary="bad-model",
            llm_model_fallback="good-model",
            ml_min_confidence=0.60,
            ml_use_adaptive_threshold=False,
            ml_adaptive_threshold_floor=0.30,
            ml_adaptive_threshold_margin=0.08,
            ml_flip_threshold_offset=-0.03,
            ml_break_candle_threshold_offset=0.0,
            ml_dir_close_threshold_offset=-0.01,
        )

        class _Resp:
            def __init__(self, text: str):
                self.choices = [
                    SimpleNamespace(message=SimpleNamespace(content=text))
                ]

        class _Client:
            def __init__(self):
                self.calls = []
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=self._create)
                )

            def _create(self, model, **kwargs):
                self.calls.append(model)
                if model == "bad-model":
                    err = Exception("Error code: 404 - model not found")
                    err.status_code = 404
                    raise err
                return _Resp('{"decision":"GO","reason":"fallback ok"}')

        client = _Client()

        with patch("src.ai.brain.get_settings", return_value=settings), patch(
            "src.ai.brain.get_prediction",
            return_value=(0.72, "AI Confidence: 72.0%", {}),
        ), patch("src.ai.brain.get_market_narrative", return_value="test narrative"), patch(
            "src.ai.brain._get_rag_engine", return_value=None
        ), patch("src.ai.brain._get_llm_client", return_value=client):
            result = brain.ensemble_decision(
                {"symbol": "XAUUSD", "entry_model": "FLIP", "zone_grade": "A", "score": 85}
            )

        self.assertEqual(result["decision"], "GO")
        self.assertEqual(result["llm_status"], "ok")
        self.assertEqual(result["llm_model_used"], "good-model")
        self.assertEqual(client.calls, ["bad-model", "good-model"])

    def test_llm_both_models_fail_marks_non_blocking_error(self):
        settings = SimpleNamespace(
            enable_llm_filter=True,
            llm_model_primary="bad-model",
            llm_model_fallback="also-bad-model",
            ml_min_confidence=0.60,
            ml_use_adaptive_threshold=False,
            ml_adaptive_threshold_floor=0.30,
            ml_adaptive_threshold_margin=0.08,
            ml_flip_threshold_offset=-0.03,
            ml_break_candle_threshold_offset=0.0,
            ml_dir_close_threshold_offset=-0.01,
        )

        class _Client:
            def __init__(self):
                self.calls = []
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=self._create)
                )

            def _create(self, model, **kwargs):
                self.calls.append(model)
                err = Exception("Error code: 404 - model not found")
                err.status_code = 404
                raise err

        client = _Client()

        with patch("src.ai.brain.get_settings", return_value=settings), patch(
            "src.ai.brain.get_prediction",
            return_value=(0.72, "AI Confidence: 72.0%", {}),
        ), patch("src.ai.brain.get_market_narrative", return_value="test narrative"), patch(
            "src.ai.brain._get_rag_engine", return_value=None
        ), patch("src.ai.brain._get_llm_client", return_value=client):
            result = brain.ensemble_decision(
                {"symbol": "XAUUSD", "entry_model": "FLIP", "zone_grade": "A", "score": 85}
            )

        self.assertEqual(result["decision"], "GO")
        self.assertEqual(result["llm_status"], "error")
        self.assertIn("treated as neutral", result["reason"].lower())
        self.assertEqual(client.calls, ["bad-model", "also-bad-model"])


if __name__ == "__main__":
    unittest.main()
