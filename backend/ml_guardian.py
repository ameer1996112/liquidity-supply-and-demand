"""
ML Guardian - Machine Learning Trade Validation Layer

This module implements an ML-powered validation layer that predicts the probability
of a trade winning based on the trained RandomForest model from backtest data.

Features Used:
- asset_id: LabelEncoded symbol
- hour: Hour of trade (0-23)
- day_of_week: Day of week (0=Monday, 6=Sunday)
- type_encoded: Trade type (entry long/short)
- signal_encoded: Signal type

The model outputs a win probability (0-1). Trades below AI_MIN_CONFIDENCE are rejected.

Author: ML Guardian System
Version: 1.0.0
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Path to model artifacts (relative to this file)
ML_DIR = Path(__file__).resolve().parent.parent / "ml"
MODEL_PATH = ML_DIR / "model.pkl"
ENCODERS_PATH = ML_DIR / "encoders.pkl"


class MLGuardianError(Exception):
    """Custom exception for ML Guardian errors."""
    pass


class MLGuardian:
    """
    ML-powered trade validation using trained RandomForest model.

    Loads the trained model and encoders from ml/ directory and provides
    win probability predictions for incoming trade signals.

    Architecture:
    - Lazy-load model/encoders on first use
    - Graceful handling of unknown symbols/signals
    - Fail-open on errors (allows trade through)

    Usage:
        guardian = MLGuardian()
        passed, confidence, details = guardian.analyze(signal_dict)
        if not passed:
            # Log rejection
        else:
            # Execute trade
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        encoders_path: Optional[Path] = None,
        min_confidence: float = 0.60,
    ):
        """
        Initialize ML Guardian.

        Args:
            model_path: Path to model.pkl (default: ml/model.pkl)
            encoders_path: Path to encoders.pkl (default: ml/encoders.pkl)
            min_confidence: Minimum win probability to approve trade (0-1)
        """
        self.model_path = model_path or MODEL_PATH
        self.encoders_path = encoders_path or ENCODERS_PATH
        self.min_confidence = min_confidence

        # Lazy-loaded artifacts
        self._model = None
        self._encoders = None
        self._feature_names = None
        self._loaded = False

    def _load_artifacts(self) -> bool:
        """
        Load model and encoders from disk.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._loaded:
            return self._model is not None

        self._loaded = True

        try:
            import joblib
        except ImportError:
            try:
                import pickle as joblib
                logger.warning("joblib not found, falling back to pickle")
            except Exception:
                logger.error("Neither joblib nor pickle available")
                return False

        # Load model
        if not self.model_path.exists():
            logger.error(f"Model file not found: {self.model_path}")
            return False

        try:
            self._model = joblib.load(self.model_path)
            logger.info(f"Loaded model from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

        # Load encoders
        if not self.encoders_path.exists():
            logger.error(f"Encoders file not found: {self.encoders_path}")
            return False

        try:
            self._encoders = joblib.load(self.encoders_path)
            logger.info(f"Loaded encoders from {self.encoders_path}")
        except Exception as e:
            logger.error(f"Failed to load encoders: {e}")
            return False

        # Get feature names from model
        if hasattr(self._model, 'feature_names_'):
            self._feature_names = self._model.feature_names_
        else:
            # Default feature order from training script
            self._feature_names = [
                'asset_id', 'hour', 'day_of_week', 'type_encoded', 'signal_encoded'
            ]

        logger.info(f"ML Guardian ready with features: {self._feature_names}")
        return True

    def _safe_encode(self, encoder, value: str, encoder_name: str) -> int:
        """
        Safely encode a value, handling unknowns gracefully.

        If the value is not in the encoder's classes, returns -1 (UNKNOWN token).
        The model was trained with LabelEncoder so we map unknown to a default.

        Args:
            encoder: sklearn LabelEncoder instance
            value: Value to encode
            encoder_name: Name for logging

        Returns:
            Encoded integer value, or 0 (first class) if unknown
        """
        try:
            if value in encoder.classes_:
                return int(encoder.transform([value])[0])
            else:
                # Unknown value - use first class (most common fallback)
                logger.warning(
                    f"Unknown {encoder_name} value '{value}' - using default (0)"
                )
                return 0
        except Exception as e:
            logger.warning(f"Encoding error for {encoder_name}: {e} - using default (0)")
            return 0

    def _extract_features(self, signal: Dict[str, Any]) -> Optional[np.ndarray]:
        """
        Extract features from signal dictionary.

        Replicates the exact feature engineering from train_ai_guardian.py:
        - asset_id: LabelEncoded symbol
        - hour: Hour from timestamp (0-23), default 12
        - day_of_week: Day from timestamp (0-6), default 2 (Wednesday)
        - type_encoded: LabelEncoded type
        - signal_encoded: LabelEncoded signal (first part before | or ,)

        Args:
            signal: Trade signal dictionary

        Returns:
            Feature array ready for model.predict_proba(), or None on error
        """
        try:
            features = {}

            # === FEATURE: Asset ID (LabelEncoded symbol) ===
            symbol = str(signal.get("symbol", "UNKNOWN")).upper()
            symbol_encoder = self._encoders.get("symbol")
            if symbol_encoder:
                features["asset_id"] = self._safe_encode(symbol_encoder, symbol, "symbol")
            else:
                features["asset_id"] = 0

            # === FEATURE: Hour and DayOfWeek ===
            timestamp = signal.get("timestamp") or signal.get("time") or signal.get("close_time")
            if timestamp:
                try:
                    if isinstance(timestamp, str):
                        # Try parsing ISO format
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    elif isinstance(timestamp, (int, float)):
                        # Unix timestamp
                        dt = datetime.fromtimestamp(timestamp)
                    else:
                        dt = datetime.now()
                    features["hour"] = dt.hour
                    features["day_of_week"] = dt.weekday()
                except Exception:
                    features["hour"] = 12  # Default noon
                    features["day_of_week"] = 2  # Default Wednesday
            else:
                # Use current time if no timestamp provided
                now = datetime.now()
                features["hour"] = now.hour
                features["day_of_week"] = now.weekday()

            # === FEATURE: Type (Long/Short) ===
            trade_type = str(signal.get("type") or signal.get("side") or "unknown").lower()
            # Normalize: buy/long -> entry long, sell/short -> entry short
            if trade_type in ("buy", "long"):
                trade_type = "entry long"
            elif trade_type in ("sell", "short"):
                trade_type = "entry short"
            type_encoder = self._encoders.get("type")
            if type_encoder:
                features["type_encoded"] = self._safe_encode(type_encoder, trade_type, "type")
            else:
                features["type_encoded"] = 0

            # === FEATURE: Signal (LabelEncoded) ===
            signal_value = str(signal.get("signal") or signal.get("entry_model") or "unknown")
            # Clean up signal - take first part before pipe or comma (same as training)
            signal_clean = signal_value.split('|')[0].split(',')[0].strip()[:50]
            signal_encoder = self._encoders.get("signal")
            if signal_encoder:
                features["signal_encoded"] = self._safe_encode(signal_encoder, signal_clean, "signal")
            else:
                features["signal_encoded"] = 0

            # === OPTIONAL FEATURES (if model was trained with them) ===
            if "source_encoded" in self._feature_names:
                source = str(signal.get("_source") or "live")
                source_encoder = self._encoders.get("source")
                if source_encoder:
                    features["source_encoded"] = self._safe_encode(source_encoder, source, "source")
                else:
                    features["source_encoded"] = 0

            if "session_encoded" in self._feature_names:
                session = str(signal.get("session") or "unknown")
                session_encoder = self._encoders.get("session")
                if session_encoder:
                    features["session_encoded"] = self._safe_encode(session_encoder, session, "session")
                else:
                    features["session_encoded"] = 0

            if "liq_distance" in self._feature_names:
                features["liq_distance"] = float(signal.get("liquidity_distance") or 50.0)

            if "runup_pct" in self._feature_names:
                features["runup_pct"] = float(signal.get("runup_pct") or 0.0)

            if "drawdown_pct" in self._feature_names:
                features["drawdown_pct"] = float(signal.get("drawdown_pct") or 0.0)

            # Build feature array in correct order
            feature_array = []
            for fname in self._feature_names:
                if fname in features:
                    feature_array.append(features[fname])
                else:
                    # Missing feature - use 0 as default
                    logger.warning(f"Missing feature '{fname}' - using default 0")
                    feature_array.append(0)

            return np.array([feature_array])

        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def analyze(self, signal: Dict[str, Any]) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Analyze a trade signal and predict win probability.

        This is the main entry point for trade validation.

        Args:
            signal: Trade signal dictionary with keys like symbol, type, timestamp, etc.

        Returns:
            Tuple of (should_execute, win_probability, details_dict)
            - should_execute: True if win_probability >= min_confidence
            - win_probability: Predicted probability of winning (0-1)
            - details_dict: Additional info for logging
        """
        details = {
            "guardian": "MLGuardian",
            "model_loaded": False,
            "win_probability": 0.0,
            "threshold": self.min_confidence,
            "decision": "SKIP",
        }

        # Load model if not already loaded
        if not self._load_artifacts():
            logger.warning("ML Guardian not available - allowing trade (fail-open)")
            details["decision"] = "SKIP_NO_MODEL"
            details["reason"] = "Model not loaded"
            return True, 0.5, details

        details["model_loaded"] = True

        # Extract features
        features = self._extract_features(signal)
        if features is None:
            logger.warning("Feature extraction failed - allowing trade (fail-open)")
            details["decision"] = "SKIP_FEATURE_ERROR"
            details["reason"] = "Feature extraction failed"
            return True, 0.5, details

        details["features"] = features.tolist()[0]
        details["feature_names"] = self._feature_names

        # Run prediction
        try:
            proba = self._model.predict_proba(features)
            # Class 1 = Win, Class 0 = Loss
            win_probability = float(proba[0][1])
            details["win_probability"] = win_probability
            details["loss_probability"] = float(proba[0][0])

        except Exception as e:
            logger.error(f"Prediction error: {e} - allowing trade (fail-open)")
            details["decision"] = "SKIP_PREDICT_ERROR"
            details["reason"] = str(e)[:100]
            return True, 0.5, details

        # Apply threshold
        if win_probability >= self.min_confidence:
            details["decision"] = "APPROVE"
            logger.info(
                f"ML Guardian APPROVED: {signal.get('symbol')} "
                f"(win_prob={win_probability:.1%} >= {self.min_confidence:.1%})"
            )
            return True, win_probability, details
        else:
            details["decision"] = "REJECT"
            logger.info(
                f"ML Guardian REJECTED: {signal.get('symbol')} "
                f"(win_prob={win_probability:.1%} < {self.min_confidence:.1%})"
            )
            return False, win_probability, details


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_ml_guardian_from_settings() -> Optional[MLGuardian]:
    """
    Factory function to create MLGuardian from config settings.

    Returns:
        MLGuardian instance if model files exist, None otherwise
    """
    from backend.config import get_settings

    settings = get_settings()

    # Check if model files exist
    if not MODEL_PATH.exists():
        logger.warning(f"ML Guardian disabled: model not found at {MODEL_PATH}")
        return None

    if not ENCODERS_PATH.exists():
        logger.warning(f"ML Guardian disabled: encoders not found at {ENCODERS_PATH}")
        return None

    # Get min confidence from settings (convert from 0-100 to 0-1)
    min_confidence = getattr(settings, 'ml_min_confidence', 0.60)

    return MLGuardian(
        model_path=MODEL_PATH,
        encoders_path=ENCODERS_PATH,
        min_confidence=min_confidence,
    )
