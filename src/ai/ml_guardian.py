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

# Path to model artifacts: project root ml/ (src/ai -> src -> project root -> ml)
ML_DIR = Path(__file__).resolve().parent.parent.parent / "ml"

# [optimization/ai-overhaul] Default to v3 LightGBM (7,924 samples, 39 features, ROC-AUC 0.55)
# v1 RF (model.pkl): 41 samples, 5 features — effectively random for any unseen symbol.
# v3 LightGBM (model_v3_lgbm.txt): 7,924 synthetic samples, 39 rich features.
MODEL_PATH = ML_DIR / "model_v3_lgbm.txt"   # v3 LightGBM (was: model.pkl)
MODEL_PATH_LEGACY = ML_DIR / "model.pkl"     # v1 RF fallback (rarely useful)
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
        hard_reject_threshold: float = 0.10,
        warning_only_mode: bool = True,
    ):
        """
        Initialize ML Guardian.

        Args:
            model_path: Path to model file (default: ml/model_v3_lgbm.txt)
            encoders_path: Path to encoders.pkl (default: ml/encoders.pkl)
            min_confidence: Minimum win probability to APPROVE the trade (0-1)
            hard_reject_threshold: Only REJECT if win_probability < this (0-1).
                                   Trades between hard_reject_threshold and min_confidence
                                   get a WARNING decision (allowed, but logged).
                                   Only applies when warning_only_mode=True.
            warning_only_mode: When True, mid-confidence trades are WARNING (allowed),
                               not REJECT. Only probabilities < hard_reject_threshold
                               are hard-rejected. Defaults to True.
                               [optimization/ai-overhaul]
        """
        self.model_path = model_path or MODEL_PATH
        self.encoders_path = encoders_path or ENCODERS_PATH
        self.min_confidence = min_confidence
        self.hard_reject_threshold = hard_reject_threshold
        self.warning_only_mode = warning_only_mode

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

        # Ensure joblib/pickle for loading encoders (needed for both LightGBM and sklearn paths)
        try:
            import joblib
        except ImportError:
            try:
                import pickle as joblib
                logger.warning("joblib not found, falling back to pickle")
            except Exception:
                logger.error("Neither joblib nor pickle available")
                return False

        # [optimization/ai-overhaul] Support both LightGBM text format and legacy sklearn pickle
        is_lgbm_text = str(self.model_path).endswith(".txt")

        if is_lgbm_text:
            try:
                import lightgbm as lgb
                logger.info(f"Loading LightGBM model from {self.model_path}")
                self._model = lgb.Booster(model_file=str(self.model_path))
                self._model_type = "lightgbm"
                logger.info("LightGBM model loaded successfully")
            except ImportError:
                logger.error("LightGBM not installed. Run: pip install lightgbm")
                # Fallback to legacy RF model
                logger.warning(f"Falling back to legacy model at {MODEL_PATH_LEGACY}")
                self.model_path = MODEL_PATH_LEGACY
                is_lgbm_text = False
            except Exception as e:
                logger.error(f"Failed to load LightGBM model: {e}")
                return False

        if not is_lgbm_text:
            if not self.model_path.exists():
                logger.error(f"Model file not found: {self.model_path}")
                return False

            try:
                self._model = joblib.load(self.model_path)
                self._model_type = "sklearn"
                logger.info(f"Loaded sklearn model from {self.model_path}")
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

            # === FEATURE: Type (Long/Short) - Use entry_model for proper mapping ===
            # Mapping matches features.py: _SIDE_MODEL_TO_TYPE
            side = str(signal.get("side") or signal.get("type") or "unknown").lower()
            entry_model = str(signal.get("entry_model") or signal.get("entry") or "DIR_CLOSE").upper()

            # Map side + entry_model to type string (matches training data)
            type_mapping = {
                ("buy", "FLIP"): "flip",
                ("sell", "FLIP"): "flip",
                ("buy", "DIR_CLOSE"): "entry long",
                ("sell", "DIR_CLOSE"): "entry short",
                ("buy", "BREAK_CANDLE"): "boc",
                ("sell", "BREAK_CANDLE"): "boc",
            }
            trade_type = type_mapping.get((side, entry_model), "entry long" if side in ("buy", "long") else "entry short" if side in ("sell", "short") else "default")

            type_encoder = self._encoders.get("type")
            if type_encoder:
                features["type_encoded"] = self._safe_encode(type_encoder, trade_type, "type")
            else:
                features["type_encoded"] = 0

            # === FEATURE: Signal (LabelEncoded) ===
            signal_value = str(signal.get("signal") or signal.get("entry_model") or "unknown")
            # Clean up signal - take first part before pipe or comma (same as training)
            signal_clean = signal_value.split('|')[0].split(',')[0].strip()[:50]
            # Use default if empty after cleaning
            if not signal_clean:
                signal_clean = "default"
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

        # [optimization/ai-overhaul] Run prediction — support both LightGBM and sklearn
        try:
            model_type = getattr(self, "_model_type", "sklearn")
            if model_type == "lightgbm":
                # LightGBM Booster.predict returns raw probabilities for binary classification
                raw = self._model.predict(features)
                win_probability = float(raw[0])
            else:
                # sklearn RandomForest / compatible
                proba = self._model.predict_proba(features)
                # Class 1 = Win, Class 0 = Loss
                win_probability = float(proba[0][1])

            details["win_probability"] = win_probability
            details["loss_probability"] = 1.0 - win_probability

        except Exception as e:
            logger.error(f"Prediction error: {e} - allowing trade (fail-open)")
            details["decision"] = "SKIP_PREDICT_ERROR"
            details["reason"] = str(e)[:100]
            return True, 0.5, details

        # [optimization/ai-overhaul] Apply Warning-Only threshold semantics:
        # - APPROVE  : win_probability >= min_confidence (default 0.60)
        # - WARNING  : hard_reject_threshold <= win_probability < min_confidence
        #              Trade is ALLOWED but logged as a caution (warning_only_mode=True)
        # - REJECT   : win_probability < hard_reject_threshold (default 0.10)
        #              Only truly terrible predictions are blocked outright.
        if win_probability >= self.min_confidence:
            details["decision"] = "APPROVE"
            logger.info(
                f"ML Guardian APPROVED: {signal.get('symbol')} "
                f"(win_prob={win_probability:.1%} >= {self.min_confidence:.1%})"
            )
            return True, win_probability, details

        elif self.warning_only_mode and win_probability >= self.hard_reject_threshold:
            # Mid-confidence: allow trade but flag as WARNING
            details["decision"] = "WARNING"
            logger.warning(
                f"ML Guardian WARNING: {signal.get('symbol')} "
                f"(win_prob={win_probability:.1%}, below threshold {self.min_confidence:.1%} "
                f"but above hard-reject floor {self.hard_reject_threshold:.1%}) — trade ALLOWED"
            )
            return True, win_probability, details

        else:
            details["decision"] = "REJECT"
            extra = "" if not self.warning_only_mode else f" (hard-reject floor {self.hard_reject_threshold:.1%})"
            logger.info(
                f"ML Guardian REJECTED: {signal.get('symbol')} "
                f"(win_prob={win_probability:.1%} < threshold{extra})"
            )
            return False, win_probability, details


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_ml_guardian_from_settings() -> Optional["MLGuardian"]:
    """
    Factory function to create MLGuardian from config settings.

    Returns:
        MLGuardian instance if model files exist, None otherwise
    """
    from config import get_settings

    settings = get_settings()

    # [optimization/ai-overhaul] Prefer v3 LightGBM, fall back to legacy RF if not found
    model_path = MODEL_PATH
    if not model_path.exists():
        logger.warning(f"v3 LightGBM model not found at {model_path}, trying legacy fallback {MODEL_PATH_LEGACY}")
        model_path = MODEL_PATH_LEGACY
        if not model_path.exists():
            logger.warning(f"ML Guardian disabled: no model found at {model_path}")
            return None

    if not ENCODERS_PATH.exists():
        logger.warning(f"ML Guardian disabled: encoders not found at {ENCODERS_PATH}")
        return None

    # Get min confidence from settings (convert from 0-100 to 0-1)
    min_confidence = getattr(settings, 'ml_min_confidence', 0.60)
    # [optimization/ai-overhaul] New threshold semantics from settings
    warning_only_mode = getattr(settings, 'ml_warning_only_mode', True)
    hard_reject_threshold = 0.10  # Only trades with <10% win probability are hard-blocked

    return MLGuardian(
        model_path=model_path,
        encoders_path=ENCODERS_PATH,
        min_confidence=min_confidence,
        hard_reject_threshold=hard_reject_threshold,
        warning_only_mode=warning_only_mode,
    )
