"""Ensemble Brain v9.1: RF + RAG + LLM."""

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openai import OpenAI

from config import get_settings
from src.adapters.market_data import get_market_narrative
from src.ai.features import build_feature_frame, encode_asset_id
from src.ai.rag_engine import RagEngine

logger = logging.getLogger(__name__)

import numpy as np


def _engineer_features_for_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for prediction (same as training script).
    Creates 20 engineered features from base features.
    """
    # ═══════════════════════════════════════════════════════
    # ORIGINAL FEATURES (8)
    # ═══════════════════════════════════════════════════════

    # Core interactions
    if 'score' in df and 'fresh' in df:
        df['score_x_fresh'] = df['score'] * df['fresh']
    if 'trend' in df and 'htf_trend' in df:
        df['trend_alignment'] = (df['trend'] == df['htf_trend']).astype(np.int8)

    # Liquidity metrics
    if 'liquidity_distance' in df and 'liquidity_spread' in df:
        df['liquidity_quality'] = df['liquidity_distance'] / (df['liquidity_spread'] + 0.001)

    # Strength composite
    if 'base_quality' in df and 'departure_strength' in df and 'return_strength' in df:
        df['strength_composite'] = (
            df['base_quality'] + df['departure_strength'] + df['return_strength']
        ) / 3.0

    # Momentum indicators
    if 'rsi' in df:
        df['rsi_neutral'] = ((df['rsi'] >= 40) & (df['rsi'] <= 60)).astype(np.int8)
    if 'adx' in df:
        df['strong_adx'] = (df['adx'] > 25).astype(np.int8)

    # Zone quality
    if 'score' in df and 'base_quality' in df:
        df['zone_quality'] = df['score'] * df['base_quality'] / 100.0

    # Risk indicators
    if 'touch_count' in df and 'atr_ratio' in df:
        df['high_risk'] = ((df['touch_count'] > 3) | (df['atr_ratio'] > 1.5)).astype(np.int8)

    # ═══════════════════════════════════════════════════════
    # ADVANCED FEATURES (12 NEW)
    # ═══════════════════════════════════════════════════════

    if 'score' in df:
        df['score_tier'] = np.select(
            [df['score'] >= 90, df['score'] >= 80, df['score'] >= 70],
            [3, 2, 1],
            default=0
        )

    if 'score' in df and 'fresh' in df:
        df['fresh_premium'] = ((df['score'] >= 85) & (df['fresh'] <= 2)).astype(np.int8)

    if 'trend' in df and 'htf_trend' in df:
        df['momentum_confluence'] = (
            (df['trend'] == df['htf_trend']).astype(int) +
            ((df.get('rsi', 50) > 50).astype(int) if 'rsi' in df else 0) +
            ((df.get('adx', 0) > 25).astype(int) if 'adx' in df else 0)
        )

    if 'touch_count' in df:
        df['zone_age_risk'] = np.minimum(df['touch_count'] / 5.0, 1.0)

    if 'atr_ratio' in df:
        df['atr_quality'] = ((df['atr_ratio'] >= 0.8) & (df['atr_ratio'] <= 1.5)).astype(np.int8)

    if 'departure_strength' in df and 'return_strength' in df:
        df['strength_imbalance'] = np.abs(df['departure_strength'] - df['return_strength'])

    if 'session' in df:
        df['prime_session'] = ((df['session'] == 1) | (df['session'] == 2)).astype(np.int8)

    if 'rsi' in df:
        df['rsi_extreme'] = ((df['rsi'] < 30) | (df['rsi'] > 70)).astype(np.int8)

    if 'liquidity_distance' in df and 'liquidity_spread' in df:
        df['liquidity_sweet_spot'] = (
            (df['liquidity_distance'] >= 5) & (df['liquidity_distance'] <= 20) &
            (df['liquidity_spread'] >= 10) & (df['liquidity_spread'] <= 50)
        ).astype(np.int8)

    if 'score' in df and 'fresh' in df and 'trend' in df and 'htf_trend' in df and 'atr_ratio' in df and 'touch_count' in df:
        df['perfect_setup'] = (
            (df['score'] >= 85) &
            (df['fresh'] <= 2) &
            (df['trend'] == df['htf_trend']) &
            (df['atr_ratio'] >= 0.8) & (df['atr_ratio'] <= 1.5) &
            (df['touch_count'] <= 2)
        ).astype(np.int8)

    if 'rvol' in df and 'adx' in df:
        df['volume_strength'] = df['rvol'] * (df['adx'] / 50.0)

    if 'score' in df and 'base_quality' in df and 'departure_strength' in df and 'return_strength' in df:
        zone_age_risk = df.get('zone_age_risk', 0)
        atr_quality = df.get('atr_quality', 0)
        df['composite_quality'] = (
            df['score'] * 0.3 +
            df['base_quality'] * 0.2 +
            df['departure_strength'] * 0.15 +
            df['return_strength'] * 0.15 +
            (100 - zone_age_risk * 100) * 0.1 +
            (atr_quality * 100) * 0.1
        ) / 100.0

    return df

# Model paths relative to project root
_ROOT = Path(__file__).resolve().parent.parent.parent

# v3 LightGBM models (preferred - 10x less memory)
MODEL_V3_LGBM_PATH = _ROOT / "ml" / "model_v3_lgbm.txt"
MODEL_V3_PKL_PATH = _ROOT / "ml" / "model_v3.pkl"
ENCODERS_V3_PATH = _ROOT / "ml" / "encoders_v3.pkl"

# v2 RandomForest models (legacy fallback)
MODEL_V2_PATH = _ROOT / "ml" / "model_v2.pkl"
ENCODERS_V2_PATH = _ROOT / "ml" / "encoders_v2.pkl"
SCALER_V2_PATH = _ROOT / "ml" / "scaler_v2.pkl"

# v1 legacy paths
MODEL_PATH = _ROOT / "ml" / "model.pkl"
ENCODERS_PATH = _ROOT / "ml" / "encoders.pkl"
SCALER_PATH = _ROOT / "ml" / "scaler.pkl"

AI_MODEL = None
AI_ENCODERS = None
AI_SCALER = None  # ✅ v5.1: StandardScaler for feature normalization (not used with LightGBM v3)
AI_MODEL_TYPE = None  # "lightgbm" or "sklearn"
AI_MODEL_METADATA: Dict[str, Any] = {}
_RAG_ENGINE: Optional[RagEngine] = None
_LLM_CLIENT: Optional[OpenAI] = None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_probability(value: Any) -> float:
    """Normalize probabilities to [0, 1], accepting either 0-1 or 0-100 inputs."""
    v = _safe_float(value, 0.0)
    if v > 1.0:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def _resolve_positive_class_index(model: Any) -> tuple[int, Dict[str, Any]]:
    """Resolve the probability column representing a positive/winning outcome."""
    classes = list(getattr(model, "classes_", []) or [])
    class_mapping = {
        "classes": classes,
        "positive_class": None,
        "positive_index": 1,
        "resolution": "default_index_1",
    }

    if not classes:
        return 1, class_mapping

    # Most sklearn binary models are [0, 1] where 1=positive class.
    if 1 in classes:
        idx = classes.index(1)
        class_mapping.update({
            "positive_class": 1,
            "positive_index": idx,
            "resolution": "numeric_class_1",
        })
        return idx, class_mapping

    lower_map = {str(c).strip().lower(): i for i, c in enumerate(classes)}
    for candidate in ("win", "good", "go", "approved", "true"):
        if candidate in lower_map:
            idx = lower_map[candidate]
            class_mapping.update({
                "positive_class": classes[idx],
                "positive_index": idx,
                "resolution": f"label_{candidate}",
            })
            return idx, class_mapping

    idx = min(1, len(classes) - 1)
    class_mapping.update({
        "positive_class": classes[idx],
        "positive_index": idx,
        "resolution": "fallback_second_class",
    })
    return idx, class_mapping


def _compute_dynamic_rf_threshold(payload: Dict[str, Any], settings) -> tuple[float, Dict[str, Any]]:
    """Compute effective RF threshold with adaptive baseline + entry-model offsets."""
    base_threshold = _normalize_probability(getattr(settings, "ml_min_confidence", 0.60))

    # Adaptive baseline: respect configured threshold cap but avoid unrealistic thresholds
    # for low-base-rate models.
    model_win_rate = _safe_float(AI_MODEL_METADATA.get("win_rate"), -1.0)
    adaptive_floor = _normalize_probability(getattr(settings, "ml_adaptive_threshold_floor", 0.30))
    adaptive_margin = _normalize_probability(getattr(settings, "ml_adaptive_threshold_margin", 0.08))
    use_adaptive = bool(getattr(settings, "ml_use_adaptive_threshold", True))

    adaptive_threshold = base_threshold
    if use_adaptive and 0.0 <= model_win_rate <= 1.0:
        adaptive_threshold = min(base_threshold, max(adaptive_floor, model_win_rate + adaptive_margin))

    zone_score = _safe_float(payload.get("score"), 0.0)
    zone_grade = str(payload.get("zone_grade", "")).strip().upper()
    entry_model = str(payload.get("entry_model", "")).strip().upper()

    grade_adjustments = {
        "A+": -0.05, "A": -0.04,
        "B+": -0.03, "B": -0.02,
        "C+": -0.01, "C": 0.00,
        "D": 0.00, "F": 0.00,
    }
    grade_adj = grade_adjustments.get(zone_grade, 0.00)

    if zone_score >= 80:
        score_adj = -0.03
    elif zone_score >= 70:
        score_adj = -0.02
    elif zone_score >= 60:
        score_adj = -0.01
    else:
        score_adj = 0.00

    entry_model_offsets = {
        "FLIP": _safe_float(getattr(settings, "ml_flip_threshold_offset", -0.03), -0.03),
        "BREAK_CANDLE": _safe_float(getattr(settings, "ml_break_candle_threshold_offset", 0.0), 0.0),
        "DIR_CLOSE": _safe_float(getattr(settings, "ml_dir_close_threshold_offset", -0.01), -0.01),
    }
    entry_model_adj = entry_model_offsets.get(entry_model, 0.0)

    threshold = adaptive_threshold + grade_adj + score_adj + entry_model_adj
    threshold = max(adaptive_floor, min(0.95, threshold))

    meta = {
        "base_threshold": base_threshold,
        "adaptive_threshold": adaptive_threshold,
        "model_win_rate": model_win_rate if 0.0 <= model_win_rate <= 1.0 else None,
        "use_adaptive_threshold": use_adaptive,
        "grade_adj": grade_adj,
        "score_adj": score_adj,
        "entry_model": entry_model,
        "entry_model_adj": entry_model_adj,
        "final_threshold": threshold,
    }
    return threshold, meta


def _load_feature_names_from_metadata(path: Path, key: str) -> List[str]:
    """Best-effort metadata feature loader."""
    try:
        if not path.exists():
            return []
        with open(path, "r") as f:
            data = json.load(f)
        names = data.get(key, [])
        return [str(c) for c in names] if isinstance(names, list) else []
    except Exception as e:
        logger.warning("Failed reading metadata feature names from %s: %s", path.name, e)
        return []


def _get_expected_feature_spec() -> Tuple[List[str], Optional[int], str]:
    """
    Return (expected_feature_names, expected_feature_count, source).

    Priority:
    1) Model-native names (feature_names_in_ / Booster.feature_name())
    2) Metadata files
    3) Encoder keys (last resort)
    """
    # LightGBM native booster
    if AI_MODEL_TYPE == "lightgbm_native":
        if AI_MODEL is not None and hasattr(AI_MODEL, "feature_name"):
            try:
                names = [str(c) for c in AI_MODEL.feature_name()]
                if names:
                    return names, len(names), "lightgbm_native.feature_name()"
            except Exception as e:
                logger.warning("Could not read Booster.feature_name(): %s", e)

        names = _load_feature_names_from_metadata(_ROOT / "ml" / "model_metadata_v3.json", "features")
        if names:
            return names, len(names), "model_metadata_v3.json"

        if AI_MODEL is not None and hasattr(AI_MODEL, "num_feature"):
            try:
                return [], int(AI_MODEL.num_feature()), "lightgbm_native.num_feature()"
            except Exception:
                pass

    # sklearn-compatible models (RandomForest, LightGBM sklearn wrapper, etc.)
    if AI_MODEL is not None and hasattr(AI_MODEL, "feature_names_in_"):
        try:
            names = [str(c) for c in list(AI_MODEL.feature_names_in_)]
            if names:
                n = int(getattr(AI_MODEL, "n_features_in_", len(names)))
                return names, n, "model.feature_names_in_"
        except Exception as e:
            logger.warning("Could not read model.feature_names_in_: %s", e)

    # Metadata fallback for legacy models
    for path, key in (
        (_ROOT / "ml" / "model_metadata_v2.json", "feature_names"),
        (_ROOT / "ml" / "model_metadata.json", "feature_names"),
    ):
        names = _load_feature_names_from_metadata(path, key)
        if names:
            return names, len(names), path.name

    # Encoder fallback (weakest)
    if AI_ENCODERS:
        names = [str(c) for c in AI_ENCODERS.keys()]
        if names:
            return names, len(names), "encoder_keys_fallback"

    # Count-only fallback
    if AI_MODEL is not None and hasattr(AI_MODEL, "n_features_in_"):
        try:
            return [], int(AI_MODEL.n_features_in_), "model.n_features_in_"
        except Exception:
            pass

    return [], None, "unknown"


def _align_features_for_inference(
    df: pd.DataFrame,
    expected_cols: List[str],
    expected_count: Optional[int],
    symbol: str,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Align live feature frame to model input shape.

    - If feature names are known: strict reindex by name (drop extras, add missing as 0.0).
    - If only count is known: trim/pad by position.
    """
    live_cols = list(df.columns)

    # Best path: align by exact feature names
    if expected_cols:
        dropped_cols = [c for c in live_cols if c not in expected_cols]
        missing_cols = [c for c in expected_cols if c not in live_cols]

        if dropped_cols:
            logger.warning(
                "ML inference alignment for %s: dropping %d unexpected columns (live=%d expected=%d): %s",
                symbol,
                len(dropped_cols),
                len(live_cols),
                len(expected_cols),
                dropped_cols,
            )
        if missing_cols:
            logger.warning(
                "ML inference alignment for %s: adding %d missing columns as 0.0: %s",
                symbol,
                len(missing_cols),
                missing_cols,
            )

        aligned = df.reindex(columns=expected_cols, fill_value=0.0)
        return aligned, dropped_cols, missing_cols

    # Fallback path: align by count only
    dropped_cols: List[str] = []
    missing_cols: List[str] = []
    if expected_count is not None:
        live_count = len(live_cols)
        if live_count > expected_count:
            dropped_cols = live_cols[expected_count:]
            logger.warning(
                "ML inference alignment for %s: dropping %d overflow columns by position "
                "(live=%d expected=%d): %s",
                symbol,
                live_count - expected_count,
                live_count,
                expected_count,
                dropped_cols,
            )
            df = df.iloc[:, :expected_count]
        elif live_count < expected_count:
            pad = expected_count - live_count
            missing_cols = [f"__pad_{i}" for i in range(pad)]
            logger.warning(
                "ML inference alignment for %s: padding %d missing columns as 0.0 "
                "(live=%d expected=%d)",
                symbol,
                pad,
                live_count,
                expected_count,
            )
            for c in missing_cols:
                df[c] = 0.0

    return df, dropped_cols, missing_cols


def _load_model_metadata_for_current_model() -> Dict[str, Any]:
    """Best-effort metadata load for the currently selected model version."""
    candidates: list[Path] = []
    if AI_MODEL_TYPE in {"lightgbm_native", "lightgbm"}:
        candidates.append(_ROOT / "ml" / "model_metadata_v3.json")
    if AI_MODEL_TYPE == "sklearn":
        candidates.extend([
            _ROOT / "ml" / "model_metadata_v2.json",
            _ROOT / "ml" / "model_metadata.json",
        ])
    # Fallback order
    candidates.extend([
        _ROOT / "ml" / "model_metadata_v3.json",
        _ROOT / "ml" / "model_metadata_v2.json",
        _ROOT / "ml" / "model_metadata.json",
    ])

    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        try:
            with open(path, "r") as f:
                meta = json.load(f)
            logger.info("Loaded model metadata: %s", path.name)
            return meta if isinstance(meta, dict) else {}
        except Exception as e:
            logger.warning("Failed loading metadata %s: %s", path.name, e)
    return {}


def load_brain() -> None:
    """
    Load ML model, encoders, and scaler once at startup.

    Priority order:
    1. v3 LightGBM (fastest, most memory-efficient)
    2. v2 RandomForest (legacy, high memory)
    3. v1 legacy models
    """
    global AI_MODEL, AI_ENCODERS, AI_SCALER, AI_MODEL_TYPE, AI_MODEL_METADATA

    try:
        # Try v3 LightGBM first (preferred)
        if MODEL_V3_LGBM_PATH.exists() or MODEL_V3_PKL_PATH.exists():
            try:
                import lightgbm as lgb

                # Load native LightGBM format (faster)
                if MODEL_V3_LGBM_PATH.exists():
                    AI_MODEL = lgb.Booster(model_file=str(MODEL_V3_LGBM_PATH))
                    AI_MODEL_TYPE = "lightgbm_native"
                    logger.info("✅ Loaded LightGBM v3 (native format): %s", MODEL_V3_LGBM_PATH)

                # Fallback to pickle format
                elif MODEL_V3_PKL_PATH.exists():
                    with open(MODEL_V3_PKL_PATH, "rb") as f:
                        AI_MODEL = pickle.load(f)
                    AI_MODEL_TYPE = "lightgbm"
                    logger.info("✅ Loaded LightGBM v3 (pickle): %s", MODEL_V3_PKL_PATH)

                # Load v3 encoders
                if ENCODERS_V3_PATH.exists():
                    with open(ENCODERS_V3_PATH, "rb") as f:
                        AI_ENCODERS = pickle.load(f)
                    logger.info("✅ Loaded v3 encoders: %d categorical features", len(AI_ENCODERS))

                # v3 doesn't use StandardScaler (LightGBM handles raw features)
                AI_SCALER = None
                AI_MODEL_METADATA = _load_model_metadata_for_current_model()
                logger.info("🚀 Brain v3 online (LightGBM, 10x faster, 90%% less RAM)")
                return

            except ImportError:
                logger.warning(
                    "⚠️  LightGBM model found but library not installed. "
                    "Install with: pip install lightgbm"
                )
                # Fall through to v2/v1 models
            except Exception as e:
                logger.error("Failed to load v3 LightGBM model: %s", e)
                # Fall through to v2/v1 models

        # Try v2 RandomForest
        if MODEL_V2_PATH.exists():
            logger.info("Loading RandomForest v2 model (legacy)...")
            with open(MODEL_V2_PATH, "rb") as f:
                AI_MODEL = pickle.load(f)
            AI_MODEL_TYPE = "sklearn"

            if ENCODERS_V2_PATH.exists():
                with open(ENCODERS_V2_PATH, "rb") as f:
                    AI_ENCODERS = pickle.load(f)

            if SCALER_V2_PATH.exists():
                with open(SCALER_V2_PATH, "rb") as f:
                    AI_SCALER = pickle.load(f)

            AI_MODEL_METADATA = _load_model_metadata_for_current_model()

            logger.info(
                "✅ Brain v2 online (RandomForest). "
                "💡 Upgrade to v3 for 10x faster: python ml/train_ai_guardian_v3_lightgbm.py"
            )
            return

        # Try v1 legacy models
        if MODEL_PATH.exists():
            logger.info("Loading legacy v1 model...")
            with open(MODEL_PATH, "rb") as f:
                AI_MODEL = pickle.load(f)
            AI_MODEL_TYPE = "sklearn"

            if ENCODERS_PATH.exists():
                with open(ENCODERS_PATH, "rb") as f:
                    AI_ENCODERS = pickle.load(f)

            if SCALER_PATH.exists():
                with open(SCALER_PATH, "rb") as f:
                    scaler_data = pickle.load(f)
                    AI_SCALER = scaler_data.get('scaler') if isinstance(scaler_data, dict) else scaler_data

            AI_MODEL_METADATA = _load_model_metadata_for_current_model()

            logger.info(
                "✅ Brain v1 online (legacy). "
                "💡 Upgrade to v3: python ml/train_ai_guardian_v3_lightgbm.py"
            )
            return

        # No model found
        logger.warning(
            "⚠️  No AI model found. Train with: python ml/train_ai_guardian_v3_lightgbm.py"
        )

    except Exception as e:
        logger.error("Brain load error: %s", e)


def get_prediction(payload: Dict[str, Any]) -> Tuple[float, str, Dict[str, Any]]:
    """
    Predict win probability (supports both LightGBM v3 and RandomForest v2).
    Returns (probability, note, features_used).
    Returns (0.5, "AI Disabled", {}) if model unavailable or on error.

    This remains a pure ML call for backward compatibility. The full
    ensemble decision is implemented in `ensemble_decision`.
    """
    if AI_MODEL is None:
        return 0.5, "AI Disabled (Missing Model)", {}

    try:
        symbol = payload.get("symbol", "UNKNOWN")

        feature_names, expected_feature_count, spec_source = _get_expected_feature_spec()
        logger.debug(
            "ML expected feature spec for %s: source=%s names=%d expected_count=%s",
            symbol,
            spec_source,
            len(feature_names),
            expected_feature_count,
        )

        features = build_feature_frame(payload, feature_names, AI_ENCODERS or {})
        asset_id = encode_asset_id(symbol, AI_ENCODERS or {})
        if asset_id is not None and "asset_id" in features:
            features["asset_id"] = float(asset_id)

        df = pd.DataFrame([features])

        # Engineer features (same as training script)
        df = _engineer_features_for_prediction(df)

        # Hard alignment gate before predict()/predict_proba().
        # Prevents crashes when live payload evolves and introduces extra columns.
        original_feature_count = len(df.columns)
        df, dropped_cols, missing_cols = _align_features_for_inference(
            df,
            expected_cols=feature_names,
            expected_count=expected_feature_count,
            symbol=symbol,
        )
        if dropped_cols or missing_cols:
            logger.info(
                "ML feature alignment summary for %s: live=%d aligned=%d dropped=%d missing_filled=%d",
                symbol,
                original_feature_count,
                len(df.columns),
                len(dropped_cols),
                len(missing_cols),
            )

        # Fail loudly on invalid values instead of silently producing bad probabilities.
        invalid_cols: list[str] = []
        for col in df.columns:
            val = df.iloc[0][col]
            if not isinstance(val, (int, float, np.floating, np.integer)):
                invalid_cols.append(str(col))
                continue
            if not np.isfinite(float(val)):
                invalid_cols.append(str(col))
        if invalid_cols:
            raise ValueError(f"Invalid feature values (NaN/Inf/non-numeric): {invalid_cols[:10]}")

        class_mapping: Dict[str, Any] = {
            "classes": None,
            "positive_class": 1,
            "positive_index": 1,
            "resolution": "default_index_1",
        }

        # Different prediction logic based on model type
        if AI_MODEL_TYPE == "lightgbm_native":
            # LightGBM native Booster.predict() returns raw scores
            # No scaling needed - LightGBM handles raw features
            prob = float(AI_MODEL.predict(df.values)[0])
            prob = _normalize_probability(prob)
            class_mapping = {
                "classes": [0, 1],
                "positive_class": 1,
                "positive_index": 1,
                "resolution": "lightgbm_native_default",
            }
            logger.debug(f"Prediction for {symbol}: {prob:.2%} (LightGBM native)")

        elif AI_MODEL_TYPE == "lightgbm":
            # LightGBM sklearn wrapper
            # No scaling needed - LightGBM handles raw features
            positive_idx, class_mapping = _resolve_positive_class_index(AI_MODEL)
            prob = float(AI_MODEL.predict_proba(df)[0][positive_idx])
            prob = _normalize_probability(prob)
            logger.debug(f"Prediction for {symbol}: {prob:.2%} (LightGBM sklearn)")

        elif AI_MODEL_TYPE == "sklearn":
            positive_idx, class_mapping = _resolve_positive_class_index(AI_MODEL)
            # RandomForest v2 - use scaling if available
            if AI_SCALER is not None:
                # Identify categorical vs numerical columns
                categorical_cols = [col for col in df.columns if '_encoded' in col or col == 'asset_id']
                numerical_cols = [col for col in df.columns if col not in categorical_cols]

                # Scale numerical features only
                df_scaled = df.copy()
                if numerical_cols:
                    df_scaled[numerical_cols] = AI_SCALER.transform(df[numerical_cols])

                prob = float(AI_MODEL.predict_proba(df_scaled)[0][positive_idx])
                prob = _normalize_probability(prob)
                logger.debug(f"Prediction for {symbol}: {prob:.2%} (RandomForest WITH scaling)")
            else:
                # No scaling (legacy behavior)
                prob = float(AI_MODEL.predict_proba(df)[0][positive_idx])
                prob = _normalize_probability(prob)
                logger.debug(f"Prediction for {symbol}: {prob:.2%} (RandomForest NO scaling)")
        else:
            # Unknown model type - try sklearn API
            positive_idx, class_mapping = _resolve_positive_class_index(AI_MODEL)
            prob = float(AI_MODEL.predict_proba(df)[0][positive_idx])
            prob = _normalize_probability(prob)
            logger.warning(f"Unknown model type: {AI_MODEL_TYPE}, using sklearn API")

        # Attach decision-trace metadata to features payload for downstream persistence.
        features["_trace_class_mapping"] = class_mapping
        features["_trace_feature_spec_source"] = spec_source
        features["_trace_model_type"] = AI_MODEL_TYPE
        return prob, f"AI Confidence: {prob:.1%}", features

    except Exception as e:
        logger.error("Prediction error: %s", e, exc_info=True)
        return 0.5, f"AI Error: {str(e)[:50]}", {}


def _get_rag_engine() -> Optional[RagEngine]:
    global _RAG_ENGINE
    if _RAG_ENGINE is not None:
        return _RAG_ENGINE
    try:
        _RAG_ENGINE = RagEngine.from_settings()
    except Exception as e:
        logger.error("RagEngine init failed: %s", e)
        _RAG_ENGINE = None
    return _RAG_ENGINE


def _get_llm_client() -> Optional[OpenAI]:
    global _LLM_CLIENT
    if _LLM_CLIENT is not None:
        return _LLM_CLIENT
    try:
        settings = get_settings()
        api_key = settings.ai_api_key.get_secret_value() if settings.ai_api_key else None
        base_url = settings.ai_base_url or None
        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        _LLM_CLIENT = OpenAI(**kwargs)
        logger.info("LLM client initialized (base_url=%s)", base_url or "default")
    except Exception as e:
        logger.error("LLM client init failed: %s", e)
        _LLM_CLIENT = None
    return _LLM_CLIENT


def ensemble_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full v9.1 ensemble flow:

    1. RF Model Filter (fast).
       - If probability < 0.60 -> NO_GO.
    2. If LLM filter disabled in settings -> GO (RF-only).
    3. Build market narrative from recent price data.
    4. Query RAG engine for matching strategy rules.
    5. Call LLM with context + rules + RF score to decide GO / NO_GO.

    Returns:
        {
          "decision": "GO" | "NO_GO",
          "reason": str,
          "rf_prob": float,
          "rf_note": str,
          "narrative": str,
          "rules": List[str],
          "llm_raw": dict | None,
        }
    """
    settings = get_settings()

    # Step 1: RF model – always run, but don't return early so we can still
    # observe RAG and market narrative even when RF is skeptical.
    rf_prob, rf_note, features = get_prediction(payload)
    rf_prob = _normalize_probability(rf_prob)
    threshold, threshold_meta = _compute_dynamic_rf_threshold(payload, settings)

    class_mapping = {}
    if isinstance(features, dict):
        class_mapping = features.get("_trace_class_mapping", {}) or {}

    feature_snapshot: Dict[str, Any] = {}
    if isinstance(features, dict):
        numeric_items = [
            (k, float(v))
            for k, v in features.items()
            if not str(k).startswith("_trace_") and isinstance(v, (int, float, np.floating, np.integer))
        ]
        numeric_items.sort(key=lambda kv: abs(kv[1]), reverse=True)
        feature_snapshot = {k: round(v, 6) for k, v in numeric_items[:10]}

    decision_trace: Dict[str, Any] = {
        "rf_probability_raw": rf_prob,
        "rf_probability_pct": round(rf_prob * 100.0, 2),
        "threshold_raw": threshold,
        "threshold_pct": round(threshold * 100.0, 2),
        "predicted_class": class_mapping.get("positive_class", 1),
        "class_mapping": class_mapping,
        "feature_spec_source": (features or {}).get("_trace_feature_spec_source") if isinstance(features, dict) else None,
        "model_type": (features or {}).get("_trace_model_type") if isinstance(features, dict) else AI_MODEL_TYPE,
        "model_win_rate": AI_MODEL_METADATA.get("win_rate") if isinstance(AI_MODEL_METADATA, dict) else None,
        "threshold_meta": threshold_meta,
        "features_snapshot": feature_snapshot,
        "rules": [],
        "rejected_rule": None,
    }
    result: Dict[str, Any] = {
        "decision": "NO_GO",
        "reason": "",
        "rf_prob": rf_prob,
        "rf_note": rf_note,
        "narrative": "",
        "rules": [],
        "llm_raw": None,
        "features": features,
        "decision_trace": decision_trace,
        "rf_threshold": threshold,
    }

    symbol = payload.get("symbol", "UNKNOWN")

    # Step 2: Market narrative – always attempt, even if RF is low
    try:
        narrative = get_market_narrative(symbol)
    except Exception as e:
        logger.error("Market narrative failed for %s: %s", symbol, e)
        narrative = f"{symbol} market narrative unavailable."
    result["narrative"] = narrative

    # Step 3: RAG retrieval – always attempt so we can inspect rules in logs
    rag = _get_rag_engine()
    rules_texts: list[str] = []
    if rag is not None:
        try:
            # Build a signal-aware query instead of generic keyword stuffing.
            # This matches rule-document vocabulary much better.
            side = payload.get("side", "")
            zone_type = payload.get("zone_type", "")
            entry_model = payload.get("entry_model", "")
            liq_swept = "liquidity swept" if payload.get("liq_swept") else ""
            rag_query = (
                f"{zone_type} zone {side} entry using {entry_model} model. "
                f"{liq_swept} {narrative}"
            ).strip()

            # No metadata filter – documents from all ingestion paths are valid.
            # Previously filtered by {"timeframe": "5m"} which hid most docs.
            docs = rag.query_rules(rag_query, k=4)
            rules_texts = [d.page_content for d in docs]
            try:
                from src.services.trade_events import log_event
                log_event(
                    None,
                    "rag_query",
                    "brain",
                    {"query_preview": rag_query[:200], "k": 4, "num_docs": len(docs), "symbol": symbol},
                )
            except Exception:
                pass
        except Exception as e:
            logger.error("RAG query failed: %s", e)
    else:
        logger.warning("RagEngine unavailable; skipping RAG retrieval.")
    result["rules"] = rules_texts

    # Step 4: Late RF rejection - after we have narrative & RAG context
    # Log feature values for debugging (helps verify Pine Script data)
    if features:
        _nonzero = {
            k: round(float(v), 3)
            for k, v in features.items()
            if isinstance(v, (int, float, np.floating, np.integer)) and float(v) != 0.0
        }
        _zero_keys = [
            k
            for k, v in features.items()
            if isinstance(v, (int, float, np.floating, np.integer)) and float(v) == 0.0
        ]
        logger.info(
            "RF features for %s: non-zero=%s | zero_keys=%s",
            symbol, _nonzero, _zero_keys,
        )

    logger.debug(
        "RF threshold for %s: base=%.0f%% adaptive=%.0f%% grade_adj=%+.0f%% score_adj=%+.0f%% entry_adj=%+.0f%% final=%.0f%%",
        symbol,
        threshold_meta.get("base_threshold", 0.0) * 100,
        threshold_meta.get("adaptive_threshold", 0.0) * 100,
        threshold_meta.get("grade_adj", 0.0) * 100,
        threshold_meta.get("score_adj", 0.0) * 100,
        threshold_meta.get("entry_model_adj", 0.0) * 100,
        threshold * 100,
    )

    # Rule: model health
    model_error = ("Disabled" in rf_note) or ("AI Error" in rf_note)
    decision_trace["rules"].append({
        "rule_id": "model_health",
        "passed": not model_error,
        "message": rf_note if model_error else "Model inference healthy",
    })
    if model_error:
        result["decision"] = "MODEL_ERROR"
        result["reason"] = rf_note
        decision_trace["rejected_rule"] = {"rule_id": "model_health", "message": rf_note}
        _log_brain_decision(symbol, result)
        return result

    # Rule: RF threshold gate
    rf_pass = rf_prob >= threshold
    rf_rule_message = (
        f"RF probability {rf_prob:.1%} {'>=' if rf_pass else '<'} {threshold:.0%} threshold"
    )
    decision_trace["rules"].append({
        "rule_id": "rf_threshold",
        "passed": rf_pass,
        "value_raw": rf_prob,
        "value_pct": round(rf_prob * 100.0, 2),
        "threshold_raw": threshold,
        "threshold_pct": round(threshold * 100.0, 2),
        "message": rf_rule_message,
    })

    # Rule: entry model visibility (required for explainability)
    entry_model = str(payload.get("entry_model", "")).strip().upper()
    entry_model_present = bool(entry_model)
    decision_trace["rules"].append({
        "rule_id": "entry_model_present",
        "passed": entry_model_present,
        "value": entry_model or None,
        "message": "Entry model provided" if entry_model_present else "Entry model missing",
    })

    if not rf_pass:
        result["reason"] = rf_rule_message + "."
        decision_trace["rejected_rule"] = {"rule_id": "rf_threshold", "message": rf_rule_message}
        _log_brain_decision(symbol, result)
        return result

    # If LLM filter disabled, accept RF decision (but still include RAG/narrative)
    if not getattr(settings, "enable_llm_filter", True):
        result["decision"] = "GO"
        result["reason"] = "RF pass and LLM filter disabled."
        decision_trace["rules"].append({
            "rule_id": "llm_filter",
            "passed": True,
            "message": "LLM filter disabled",
        })
        _log_brain_decision(symbol, result)
        return result

    # Step 5: LLM wisdom
    client = _get_llm_client()
    if client is None:
        result["decision"] = "GO"
        result["reason"] = "RF pass; LLM unavailable, defaulting to GO."
        decision_trace["rules"].append({
            "rule_id": "llm_availability",
            "passed": True,
            "message": "LLM unavailable; fail-open after RF pass",
        })
        _log_brain_decision(symbol, result)
        return result

    rules_block = "\n\n".join(f"- {r}" for r in rules_texts) if rules_texts else "No explicit rules found."

    prompt = (
        "You are a strict trading risk gatekeeper.\n\n"
        f"Context (Market Narrative):\n{narrative}\n\n"
        f"Strategy Rules (from knowledge base):\n{rules_block}\n\n"
        f"RF Model Score: {rf_prob:.4f}\n\n"
        "Task: Decide if this trade is valid and should be executed.\n"
        "Constraints:\n"
        "- Only approve trades that clearly align with the rules and context.\n"
        "- Be conservative if context or rules are ambiguous.\n\n"
        "Response: Return ONLY a valid JSON object of the form:\n"
        "{\n"
        "  \"decision\": \"GO\" | \"NO_GO\",\n"
        "  \"reason\": \"... concise explanation ...\"\n"
        "}\n"
    )

    try:
        chat = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a strict trading risk co-pilot."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=256,
        )
        content = chat.choices[0].message.content or "{}"
        llm_json = json.loads(content)
        result["llm_raw"] = llm_json

        decision = str(llm_json.get("decision", "NO_GO")).upper()
        reason = str(llm_json.get("reason", "")).strip()

        if decision == "GO":
            result["decision"] = "GO"
            result["reason"] = reason or "LLM approved trade."
            decision_trace["rules"].append({
                "rule_id": "llm_decision",
                "passed": True,
                "message": result["reason"],
            })
        else:
            result["decision"] = "NO_GO"
            result["reason"] = reason or "LLM rejected trade."
            decision_trace["rules"].append({
                "rule_id": "llm_decision",
                "passed": False,
                "message": result["reason"],
            })
            decision_trace["rejected_rule"] = {"rule_id": "llm_decision", "message": result["reason"]}
    except Exception as e:
        logger.error("LLM ensemble decision failed: %s", e)
        # Fail-open: RF already passed, so if LLM is down we allow the trade
        result["decision"] = "GO"
        result["reason"] = f"RF pass; LLM error (fail-open): {str(e)[:60]}"
        decision_trace["rules"].append({
            "rule_id": "llm_error",
            "passed": True,
            "message": result["reason"],
        })

    _log_brain_decision(symbol, result)
    return result


def _log_brain_decision(symbol: str, result: Dict[str, Any]) -> None:
    """Log brain prediction to trade_events for audit and tuning (Package C)."""
    try:
        from src.services.trade_events import log_event
        meta = {
            "decision": result.get("decision", ""),
            "rf_prob": result.get("rf_prob"),
            "rf_threshold": result.get("rf_threshold"),
            "reason": (result.get("reason") or "")[:300],
            "symbol": symbol,
            "num_rules": len(result.get("rules") or []),
            "decision_trace": result.get("decision_trace"),
        }
        log_event(None, "brain_prediction", "brain", meta)
    except Exception:
        pass


__all__ = ["load_brain", "get_prediction", "ensemble_decision"]

