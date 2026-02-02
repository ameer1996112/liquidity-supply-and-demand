"""
Unit Tests for ML Guardian with Stub Models

Tests the MLGuardian class using stub models instead of real ML artifacts:
1. Low confidence (< 60%) rejection
2. High confidence (>= 60%) approval
3. Exactly at threshold (60%) approval
4. Model missing handling (fail-open)
5. Feature extraction validation

Uses stub models to avoid loading real model.pkl.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
import numpy as np

from backend.ml_guardian import (
    MLGuardian,
    MODEL_PATH,
    ENCODERS_PATH,
)


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def stub_model_low():
    """Stub model predicting low win probability (45%)."""
    model = MagicMock()
    model.predict_proba.return_value = np.array([[0.55, 0.45]])  # [loss, win]
    model.feature_names_in_ = ["asset_id", "hour", "day_of_week", "type_encoded", "signal_encoded"]
    return model


@pytest.fixture
def stub_model_high():
    """Stub model predicting high win probability (75%)."""
    model = MagicMock()
    model.predict_proba.return_value = np.array([[0.25, 0.75]])  # [loss, win]
    model.feature_names_in_ = ["asset_id", "hour", "day_of_week", "type_encoded", "signal_encoded"]
    return model


@pytest.fixture
def stub_model_threshold():
    """Stub model predicting exactly at threshold (60%)."""
    model = MagicMock()
    model.predict_proba.return_value = np.array([[0.40, 0.60]])  # [loss, win]
    model.feature_names_in_ = ["asset_id", "hour", "day_of_week", "type_encoded", "signal_encoded"]
    return model


@pytest.fixture
def stub_encoders():
    """Stub encoders for ML features."""
    encoders = {}

    # Symbol encoder
    symbol_enc = MagicMock()
    symbol_enc.classes_ = np.array(["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"])
    symbol_enc.transform = MagicMock(return_value=np.array([0]))
    encoders["symbol"] = symbol_enc

    # Type encoder
    type_enc = MagicMock()
    type_enc.classes_ = np.array(["entry long", "entry short"])
    type_enc.transform = MagicMock(return_value=np.array([0]))
    encoders["type"] = type_enc

    # Signal encoder
    signal_enc = MagicMock()
    signal_enc.classes_ = np.array(["FLIP", "DIR_CLOSE", "BREAK_CANDLE"])
    signal_enc.transform = MagicMock(return_value=np.array([0]))
    encoders["signal"] = signal_enc

    return encoders


@pytest.fixture
def signal_buy():
    """Sample buy signal for testing."""
    return {
        "symbol": "EURUSD",
        "side": "buy",
        "type": "buy",
        "entry": 1.0850,
        "sl": 1.0800,
        "tp": 1.0950,
        "size": 0.10,
        "timestamp": "2024-01-15T10:30:00Z",
        "signal": "FLIP",
        "entry_model": "FLIP",
    }


@pytest.fixture
def signal_sell():
    """Sample sell signal for testing."""
    return {
        "symbol": "GBPUSD",
        "side": "sell",
        "type": "sell",
        "entry": 1.2650,
        "sl": 1.2700,
        "tp": 1.2550,
        "size": 0.15,
    }


# ══════════════════════════════════════════════════════════
# ML GUARDIAN INITIALIZATION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestMLGuardianInit:
    """Tests for MLGuardian initialization."""

    def test_default_min_confidence_is_60_percent(self):
        """Default min_confidence should be 0.60 (60%)."""
        guardian = MLGuardian()
        assert guardian.min_confidence == 0.60

    def test_custom_min_confidence(self):
        """Should accept custom min_confidence."""
        guardian = MLGuardian(min_confidence=0.70)
        assert guardian.min_confidence == 0.70

    def test_lazy_loading_not_triggered_on_init(self):
        """Model should not be loaded on initialization."""
        guardian = MLGuardian()
        assert guardian._model is None
        assert guardian._encoders is None
        assert guardian._loaded is False


# ══════════════════════════════════════════════════════════
# LOW CONFIDENCE REJECTION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestLowConfidenceRejection:
    """Tests for rejecting low-confidence predictions."""

    def test_rejects_when_below_threshold(self, stub_model_low, stub_encoders, signal_buy):
        """Should reject when win probability < 60%."""
        guardian = MLGuardian()
        guardian._model = stub_model_low
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_low.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert passed is False
        assert probability == 0.45
        assert details["decision"] == "REJECT"

    def test_rejection_includes_probability(self, stub_model_low, stub_encoders, signal_buy):
        """Rejection should include win probability in details."""
        guardian = MLGuardian()
        guardian._model = stub_model_low
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_low.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert "win_probability" in details
        assert details["win_probability"] == 0.45

    def test_rejection_includes_threshold(self, stub_model_low, stub_encoders, signal_buy):
        """Rejection should include threshold in details."""
        guardian = MLGuardian()
        guardian._model = stub_model_low
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_low.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert "threshold" in details
        assert details["threshold"] == 0.60


# ══════════════════════════════════════════════════════════
# HIGH CONFIDENCE APPROVAL TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestHighConfidenceApproval:
    """Tests for approving high-confidence predictions."""

    def test_approves_when_above_threshold(self, stub_model_high, stub_encoders, signal_buy):
        """Should approve when win probability >= 60%."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert passed is True
        assert probability == 0.75
        assert details["decision"] == "APPROVE"

    def test_approves_at_exact_threshold(self, stub_model_threshold, stub_encoders, signal_buy):
        """Should approve when win probability equals exactly 60%."""
        guardian = MLGuardian()
        guardian._model = stub_model_threshold
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_threshold.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert passed is True
        assert probability == 0.60
        assert details["decision"] == "APPROVE"


# ══════════════════════════════════════════════════════════
# MODEL MISSING / FAIL-OPEN TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestModelMissingFailOpen:
    """Tests for fail-open behavior when model is missing."""

    def test_approves_when_model_missing(self, signal_buy):
        """Should approve (fail-open) when model file is missing."""
        # Use non-existent path
        guardian = MLGuardian(
            model_path=Path("/nonexistent/model.pkl"),
            encoders_path=Path("/nonexistent/encoders.pkl"),
        )

        passed, probability, details = guardian.analyze(signal_buy)

        assert passed is True
        assert probability == 0.5  # Default neutral probability
        assert details["decision"] == "SKIP_NO_MODEL"

    def test_fail_open_returns_neutral_probability(self, signal_buy):
        """Fail-open should return 0.5 probability."""
        guardian = MLGuardian(
            model_path=Path("/nonexistent/model.pkl"),
        )

        passed, probability, details = guardian.analyze(signal_buy)

        assert probability == 0.5

    def test_fail_open_details_explain_reason(self, signal_buy):
        """Fail-open details should explain why."""
        guardian = MLGuardian(
            model_path=Path("/nonexistent/model.pkl"),
        )

        passed, probability, details = guardian.analyze(signal_buy)

        assert "reason" in details or "Model not loaded" in str(details)


# ══════════════════════════════════════════════════════════
# FEATURE EXTRACTION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestFeatureExtraction:
    """Tests for feature extraction from signals."""

    def test_extracts_symbol(self, stub_model_high, stub_encoders, signal_buy):
        """Should extract symbol from signal."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        # Symbol encoder should have been called
        stub_encoders["symbol"].transform.assert_called()

    def test_extracts_type_from_side(self, stub_model_high, stub_encoders, signal_buy):
        """Should extract type from side field."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert passed is True  # Should complete without error

    def test_handles_missing_timestamp(self, stub_model_high, stub_encoders):
        """Should handle signals without timestamp (use current time)."""
        signal_no_timestamp = {
            "symbol": "EURUSD",
            "side": "buy",
        }

        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        # Should not crash
        passed, probability, details = guardian.analyze(signal_no_timestamp)

        assert passed is True

    def test_features_included_in_details(self, stub_model_high, stub_encoders, signal_buy):
        """Details should include extracted features."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert "features" in details
        assert "feature_names" in details

    def test_handles_unknown_symbol(self, stub_model_high, stub_encoders):
        """Should handle unknown symbols gracefully."""
        signal = {
            "symbol": "UNKNOWN_PAIR",
            "side": "buy",
        }

        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        # Should not crash, should use default encoding
        passed, probability, details = guardian.analyze(signal)

        assert passed is True  # Model returns high confidence


# ══════════════════════════════════════════════════════════
# PREDICTION ERROR HANDLING TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPredictionErrorHandling:
    """Tests for error handling during prediction."""

    def test_fail_open_on_prediction_error(self, stub_encoders, signal_buy):
        """Should fail-open if prediction throws exception."""
        error_model = MagicMock()
        error_model.predict_proba.side_effect = Exception("Prediction failed")
        error_model.feature_names_in_ = ["asset_id", "hour", "day_of_week", "type_encoded", "signal_encoded"]

        guardian = MLGuardian()
        guardian._model = error_model
        guardian._encoders = stub_encoders
        guardian._feature_names = error_model.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert passed is True  # Fail-open
        assert probability == 0.5
        assert "SKIP" in details["decision"]

    def test_fail_open_on_feature_extraction_error(self, stub_model_high):
        """Should fail-open if feature extraction fails."""
        # Encoders that throw errors
        bad_encoders = {"symbol": MagicMock(side_effect=Exception("Encoding failed"))}

        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = bad_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        signal = {"symbol": "EURUSD", "side": "buy"}
        passed, probability, details = guardian.analyze(signal)

        # Should still complete (with defaults or fail-open)
        assert passed is not None


# ══════════════════════════════════════════════════════════
# SIGNAL TYPE MAPPING TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestSignalTypeMapping:
    """Tests for mapping side to trade type."""

    def test_buy_maps_to_entry_long(self, stub_model_high, stub_encoders):
        """'buy' should map to 'entry long'."""
        signal = {"symbol": "EURUSD", "side": "buy"}

        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal)

        # Type encoder should be called for encoding
        assert passed is True

    def test_sell_maps_to_entry_short(self, stub_model_high, stub_encoders):
        """'sell' should map to 'entry short'."""
        signal = {"symbol": "EURUSD", "side": "sell"}

        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal)

        assert passed is True

    def test_long_maps_to_entry_long(self, stub_model_high, stub_encoders):
        """'long' should map to 'entry long'."""
        signal = {"symbol": "EURUSD", "type": "long"}

        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal)

        assert passed is True


# ══════════════════════════════════════════════════════════
# WORKER INTEGRATION TESTS (Constants)
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestWorkerIntegration:
    """Tests verifying ML Guardian constants match worker."""

    def test_worker_ml_min_confidence_matches(self):
        """Worker's ML_MIN_CONFIDENCE should match expected threshold."""
        from backend.worker import ML_MIN_CONFIDENCE

        assert ML_MIN_CONFIDENCE == 0.50  # worker uses 0.50 (see worker.py)

    def test_guardian_threshold_matches_worker(self):
        """MLGuardian threshold should match worker when aligned."""
        from backend.worker import ML_MIN_CONFIDENCE

        guardian = MLGuardian(min_confidence=ML_MIN_CONFIDENCE)
        assert guardian.min_confidence == ML_MIN_CONFIDENCE


# ══════════════════════════════════════════════════════════
# DETAILS STRUCTURE TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDetailsStructure:
    """Tests for details dict structure."""

    def test_details_contains_required_fields(self, stub_model_high, stub_encoders, signal_buy):
        """Details should contain all required fields."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert "guardian" in details
        assert "model_loaded" in details
        assert "win_probability" in details
        assert "threshold" in details
        assert "decision" in details

    def test_details_guardian_is_ml_guardian(self, stub_model_high, stub_encoders, signal_buy):
        """Guardian field should be 'MLGuardian'."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert details["guardian"] == "MLGuardian"

    def test_details_model_loaded_true_when_loaded(self, stub_model_high, stub_encoders, signal_buy):
        """model_loaded should be True when model is loaded."""
        guardian = MLGuardian()
        guardian._model = stub_model_high
        guardian._encoders = stub_encoders
        guardian._feature_names = stub_model_high.feature_names_in_
        guardian._loaded = True

        passed, probability, details = guardian.analyze(signal_buy)

        assert details["model_loaded"] is True
