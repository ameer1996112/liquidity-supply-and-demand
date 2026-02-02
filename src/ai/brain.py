"""ML brain: load model and predict win probability."""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.ai.features import build_feature_frame, encode_asset_id

logger = logging.getLogger(__name__)

# Model paths relative to project root
_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = _ROOT / "ml" / "model.pkl"
ENCODERS_PATH = _ROOT / "ml" / "encoders.pkl"

AI_MODEL = None
AI_ENCODERS = None


def load_brain() -> None:
    """Load ML model and encoders once at startup."""
    global AI_MODEL, AI_ENCODERS
    try:
        if not MODEL_PATH.exists():
            logger.warning("Brain missing: %s", MODEL_PATH)
            return
        with open(MODEL_PATH, "rb") as f:
            AI_MODEL = pickle.load(f)
        with open(ENCODERS_PATH, "rb") as f:
            AI_ENCODERS = pickle.load(f)
        logger.info("Brain online. Features: %s", len(AI_MODEL.feature_names_in_))
    except Exception as e:
        logger.error("Brain load error: %s", e)


def get_prediction(payload: Dict[str, Any]) -> Tuple[float, str, Dict[str, Any]]:
    """
    Predict win probability. Returns (probability, note, features_used).
    Returns (0.5, "AI Disabled", {}) if model unavailable or on error.
    """
    if AI_MODEL is None:
        return 0.5, "AI Disabled (Missing Model)", {}
    try:
        features = build_feature_frame(payload, list(AI_MODEL.feature_names_in_))
        symbol = payload.get("symbol", "UNKNOWN")
        asset_id = encode_asset_id(symbol, AI_ENCODERS or {})
        if asset_id is not None and "asset_id" in features:
            features["asset_id"] = asset_id
        df = pd.DataFrame([features])
        prob = float(AI_MODEL.predict_proba(df)[0][1])
        return prob, f"AI Confidence: {prob:.1%}", features
    except Exception as e:
        logger.error("Prediction error: %s", e)
        return 0.5, f"AI Error: {str(e)[:50]}", {}
