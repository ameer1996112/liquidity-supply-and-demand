"""
Test Suite: Brain (AI Decision Engine)
======================================

Tests the AI ensemble decision logic:
- RF model predictions
- RAG context retrieval
- LLM gatekeeper decisions
- Error handling and fallbacks

These tests mock external services (OpenAI, Supabase/RAG) to verify
logic without network calls or API costs.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import modules - external deps are mocked in conftest.py
import src.ai.brain as brain_module


# ══════════════════════════════════════════════════════════
# TEST: BULL MARKET CONDITIONS
# ══════════════════════════════════════════════════════════


class TestBrainBullMarket:
    """Test Brain behavior in bullish market conditions."""

    def test_brain_bull_market_go_decision(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: Valid bullish setup should receive GO decision.

        Conditions:
        - Price > SMA200 (uptrend)
        - RSI < 30 (oversold in uptrend = buy opportunity)
        - High RF confidence (>60%)
        - LLM approves

        Expected: decision == "GO"
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish above SMA200"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            assert result["decision"] == "GO"
            assert result["rf_prob"] >= 0.60
            assert "narrative" in result
            assert isinstance(result["rules"], list)

    def test_brain_bull_market_rf_pass_only(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_settings_ai_disabled,
    ):
        """
        Test: When LLM filter is disabled, RF pass alone triggers GO.

        Expected: decision == "GO" when RF > threshold and LLM disabled
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings_ai_disabled), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            assert result["decision"] == "GO"
            assert "LLM filter disabled" in result["reason"]


# ══════════════════════════════════════════════════════════
# TEST: BEAR MARKET REJECTION
# ══════════════════════════════════════════════════════════


class TestBrainBearMarketRejection:
    """Test Brain behavior when market conditions contradict the trade."""

    def test_brain_bear_market_rejection_by_llm(
        self,
        brain_payload_bearish_contradiction,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_no_go,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: LLM rejects trade when direction contradicts market trend.

        Conditions:
        - Price > SMA200 (bullish market)
        - Trade is SELL (contradiction)
        - LLM recognizes contradiction and rejects

        Expected: decision == "NO_GO"
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_no_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish above SMA200"):

            result = brain_module.ensemble_decision(brain_payload_bearish_contradiction)

            assert result["decision"] == "NO_GO"
            assert result["llm_raw"] is not None
            assert result["llm_raw"]["decision"] == "NO_GO"

    def test_brain_low_rf_confidence_rejection(
        self,
        brain_payload_bullish,
        stub_model_low_confidence,
        stub_encoders,
        mock_settings,
    ):
        """
        Test: RF model rejects trade when confidence below threshold.

        Conditions:
        - RF probability < 60% threshold

        Expected: decision == "NO_GO", reason mentions threshold
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_low_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD neutral"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            assert result["decision"] == "NO_GO"
            assert "threshold" in result["reason"].lower() or "below" in result["reason"].lower()
            assert result["rf_prob"] < 0.60


# ══════════════════════════════════════════════════════════
# TEST: RAG FAILURE SCENARIOS
# ══════════════════════════════════════════════════════════


class TestBrainRagFailure:
    """Test Brain behavior when RAG engine fails or returns empty."""

    def test_brain_rag_empty_context_still_decides(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine_empty,
        mock_settings,
    ):
        """
        Test: Brain still makes decision when RAG returns no documents.

        Expected: Decision made based on RF + LLM without RAG context.
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine_empty), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            # Should still make a decision
            assert result["decision"] in ("GO", "NO_GO")
            # Rules should be empty
            assert result["rules"] == []

    def test_brain_rag_failure_logs_and_continues(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine_failure,
        mock_settings,
        caplog,
    ):
        """
        Test: Brain handles RAG engine failure gracefully.

        Expected: Logs error, continues with decision, doesn't crash.
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine_failure), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            # Should still make a decision
            assert result["decision"] in ("GO", "NO_GO")
            # Rules should be empty due to failure
            assert result["rules"] == []

    def test_brain_rag_unavailable_fallback(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_settings,
    ):
        """
        Test: Brain continues when RAG engine is None (unavailable).

        Expected: Skips RAG, decision made on RF + LLM.
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=None), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            assert result["decision"] in ("GO", "NO_GO")
            assert result["rules"] == []


# ══════════════════════════════════════════════════════════
# TEST: JSON PARSING ERRORS
# ══════════════════════════════════════════════════════════


class TestBrainJsonParsingError:
    """Test Brain handling of malformed LLM responses."""

    def test_brain_llm_broken_json_defaults_to_no_go(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: LLM returns broken JSON, Brain defaults to NO_GO.

        Expected: decision == "NO_GO", reason mentions error.
        """
        # Create a mock that returns invalid JSON
        mock_broken_client = MagicMock()
        mock_broken_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="This is not valid JSON {broken"))]
        )

        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_broken_client), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            assert result["decision"] == "NO_GO"
            assert "error" in result["reason"].lower() or "LLM" in result["reason"]

    def test_brain_llm_missing_decision_field(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: LLM returns valid JSON but missing 'decision' field.

        Expected: Defaults to NO_GO.
        """
        mock_incomplete_client = MagicMock()
        mock_incomplete_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"reason": "No decision field"}'))]
        )

        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_incomplete_client), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            # Missing decision field defaults to NO_GO
            assert result["decision"] == "NO_GO"

    def test_brain_llm_api_error_conservative_fallback(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_error,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: LLM API throws exception, Brain handles gracefully.

        Expected: decision == "NO_GO" (conservative fallback).
        """
        mock_error_client = MagicMock()
        mock_error_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")

        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_error_client), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            # On error, should be conservative
            assert result["decision"] == "NO_GO"
            assert "error" in result["reason"].lower()


# ══════════════════════════════════════════════════════════
# TEST: MODEL UNAVAILABLE SCENARIOS
# ══════════════════════════════════════════════════════════


class TestBrainModelUnavailable:
    """Test Brain behavior when ML model is unavailable."""

    def test_brain_no_model_returns_neutral(
        self,
        brain_payload_bullish,
        mock_settings,
    ):
        """
        Test: When AI_MODEL is None, prediction returns 0.5 (neutral).

        Expected: RF probability = 0.5, note mentions disabled/missing.
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", None), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD"):

            prob, note, features = brain_module.get_prediction(brain_payload_bullish)

            assert prob == 0.5
            assert "disabled" in note.lower() or "missing" in note.lower()
            assert features == {}

    def test_brain_model_error_returns_neutral(
        self,
        brain_payload_bullish,
        mock_settings,
    ):
        """
        Test: When model prediction throws error, returns 0.5.

        Expected: RF probability = 0.5, note mentions error.
        """
        mock_broken_model = MagicMock()
        mock_broken_model.feature_names_in_ = ["asset_id", "hour", "day_of_week"]
        mock_broken_model.predict_proba.side_effect = Exception("Model prediction failed")

        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", mock_broken_model), \
             patch.object(brain_module, "AI_ENCODERS", {}):

            prob, note, features = brain_module.get_prediction(brain_payload_bullish)

            assert prob == 0.5
            assert "error" in note.lower()


# ══════════════════════════════════════════════════════════
# TEST: LLM CLIENT UNAVAILABLE
# ══════════════════════════════════════════════════════════


class TestBrainLlmUnavailable:
    """Test Brain behavior when LLM client is unavailable."""

    def test_brain_llm_unavailable_trusts_rf(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: When LLM client is None, Brain trusts RF decision.

        Expected: If RF > threshold, decision = GO (trusts RF).
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=None), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD bullish"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            assert result["decision"] == "GO"
            assert "unavailable" in result["reason"].lower() or "RF pass" in result["reason"]


# ══════════════════════════════════════════════════════════
# TEST: MARKET NARRATIVE FAILURE
# ══════════════════════════════════════════════════════════


class TestBrainMarketNarrativeFailure:
    """Test Brain behavior when market narrative fails."""

    def test_brain_narrative_failure_continues(
        self,
        brain_payload_bullish,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: Market narrative failure doesn't crash Brain.

        Expected: Narrative set to fallback message, decision still made.
        """
        def failing_narrative(symbol):
            raise Exception("yfinance API error")

        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", side_effect=failing_narrative):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            # Should still return a decision
            assert result["decision"] in ("GO", "NO_GO")
            # Narrative should mention unavailable
            assert "unavailable" in result["narrative"].lower()


# ══════════════════════════════════════════════════════════
# TEST: EDGE CASES
# ══════════════════════════════════════════════════════════


class TestBrainEdgeCases:
    """Test Brain with edge case inputs."""

    def test_brain_exactly_at_threshold(
        self,
        brain_payload_bullish,
        stub_model_threshold,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: RF probability exactly at threshold (0.60).

        Expected: Should pass RF filter (>= threshold).
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_threshold), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="EURUSD neutral"):

            result = brain_module.ensemble_decision(brain_payload_bullish)

            # At threshold, RF passes, LLM decides
            assert result["rf_prob"] == 0.60
            # Final decision depends on LLM (GO in this case)
            assert result["decision"] == "GO"

    def test_brain_unknown_symbol(
        self,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine,
        mock_settings,
    ):
        """
        Test: Unknown symbol doesn't crash Brain.

        Expected: Brain handles gracefully, makes decision.
        """
        payload = {
            "symbol": "UNKNOWN_SYMBOL_XYZ",
            "side": "buy",
            "entry": 100.0,
            "sl": 99.0,
            "tp": 102.0,
            "size": 0.01,
        }

        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "_get_llm_client", return_value=mock_openai_go), \
             patch.object(brain_module, "_get_rag_engine", return_value=mock_rag_engine), \
             patch.object(brain_module, "get_market_narrative", return_value="Unknown symbol"):

            result = brain_module.ensemble_decision(payload)

            # Should not crash, should make a decision
            assert result["decision"] in ("GO", "NO_GO")

    def test_brain_empty_payload(
        self,
        stub_model_high_confidence,
        stub_encoders,
        mock_settings,
    ):
        """
        Test: Empty/minimal payload handling.

        Expected: Brain handles gracefully without crashing.
        """
        with patch.object(brain_module, "get_settings", return_value=mock_settings), \
             patch.object(brain_module, "AI_MODEL", stub_model_high_confidence), \
             patch.object(brain_module, "AI_ENCODERS", stub_encoders), \
             patch.object(brain_module, "get_market_narrative", return_value="Unknown"):

            prob, note, features = brain_module.get_prediction({})

            # Should not crash
            assert isinstance(prob, float)
            assert isinstance(note, str)
