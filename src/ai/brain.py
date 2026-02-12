"""Ensemble Brain v9.1: RF + RAG + LLM."""

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from openai import OpenAI

from config import get_settings
from src.adapters.market_data import get_market_narrative
from src.ai.features import build_feature_frame, encode_asset_id
from src.ai.rag_engine import RagEngine

logger = logging.getLogger(__name__)

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
_RAG_ENGINE: Optional[RagEngine] = None
_LLM_CLIENT: Optional[OpenAI] = None


def load_brain() -> None:
    """
    Load ML model, encoders, and scaler once at startup.

    Priority order:
    1. v3 LightGBM (fastest, most memory-efficient)
    2. v2 RandomForest (legacy, high memory)
    3. v1 legacy models
    """
    global AI_MODEL, AI_ENCODERS, AI_SCALER, AI_MODEL_TYPE

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

        # Get feature names based on model type
        if AI_MODEL_TYPE == "lightgbm_native":
            # LightGBM native format doesn't have feature_names_in_
            # We'll use the features from encoders or expected features
            feature_names = list(AI_ENCODERS.keys()) if AI_ENCODERS else []
        elif hasattr(AI_MODEL, 'feature_names_in_'):
            feature_names = list(AI_MODEL.feature_names_in_)
        else:
            logger.warning("Model has no feature_names_in_, using encoders")
            feature_names = list(AI_ENCODERS.keys()) if AI_ENCODERS else []

        features = build_feature_frame(payload, feature_names, AI_ENCODERS or {})
        asset_id = encode_asset_id(symbol, AI_ENCODERS or {})
        if asset_id is not None and "asset_id" in features:
            features["asset_id"] = float(asset_id)

        df = pd.DataFrame([features])

        # Different prediction logic based on model type
        if AI_MODEL_TYPE == "lightgbm_native":
            # LightGBM native Booster.predict() returns raw scores
            # No scaling needed - LightGBM handles raw features
            prob = float(AI_MODEL.predict(df.values)[0])
            logger.debug(f"Prediction for {symbol}: {prob:.2%} (LightGBM native)")

        elif AI_MODEL_TYPE == "lightgbm":
            # LightGBM sklearn wrapper
            # No scaling needed - LightGBM handles raw features
            prob = float(AI_MODEL.predict_proba(df)[0][1])
            logger.debug(f"Prediction for {symbol}: {prob:.2%} (LightGBM sklearn)")

        elif AI_MODEL_TYPE == "sklearn":
            # RandomForest v2 - use scaling if available
            if AI_SCALER is not None:
                # Identify categorical vs numerical columns
                categorical_cols = [col for col in df.columns if '_encoded' in col or col == 'asset_id']
                numerical_cols = [col for col in df.columns if col not in categorical_cols]

                # Scale numerical features only
                df_scaled = df.copy()
                if numerical_cols:
                    df_scaled[numerical_cols] = AI_SCALER.transform(df[numerical_cols])

                prob = float(AI_MODEL.predict_proba(df_scaled)[0][1])
                logger.debug(f"Prediction for {symbol}: {prob:.2%} (RandomForest WITH scaling)")
            else:
                # No scaling (legacy behavior)
                prob = float(AI_MODEL.predict_proba(df)[0][1])
                logger.debug(f"Prediction for {symbol}: {prob:.2%} (RandomForest NO scaling)")
        else:
            # Unknown model type - try sklearn API
            prob = float(AI_MODEL.predict_proba(df)[0][1])
            logger.warning(f"Unknown model type: {AI_MODEL_TYPE}, using sklearn API")

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
    result: Dict[str, Any] = {
        "decision": "NO_GO",
        "reason": "",
        "rf_prob": rf_prob,
        "rf_note": rf_note,
        "narrative": "",
        "rules": [],
        "llm_raw": None,
        "features": features,
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
        _nonzero = {k: round(v, 3) for k, v in features.items() if v != 0.0}
        _zero_keys = [k for k, v in features.items() if v == 0.0]
        logger.info(
            "RF features for %s: non-zero=%s | zero_keys=%s",
            symbol, _nonzero, _zero_keys,
        )

    # ✅ Dynamic threshold: Lower threshold for high-quality zones
    # This allows strong setups to pass even if RF is slightly skeptical
    base_threshold = getattr(settings, "ml_min_confidence", 0.60)
    zone_score = float(payload.get("score", 0))
    zone_grade = payload.get("zone_grade", "")

    # Grade multipliers: A+ = -0.05, A = -0.04, B+ = -0.03, B = -0.02, C+ = -0.01, C/lower = 0
    grade_adjustments = {
        "A+": -0.05, "A": -0.04,
        "B+": -0.03, "B": -0.02,
        "C+": -0.01, "C": 0.00,
        "D": 0.00, "F": 0.00
    }
    grade_adj = grade_adjustments.get(zone_grade, 0.00)

    # Score bonus: 80+ = -0.03, 70-80 = -0.02, 60-70 = -0.01
    if zone_score >= 80:
        score_adj = -0.03
    elif zone_score >= 70:
        score_adj = -0.02
    elif zone_score >= 60:
        score_adj = -0.01
    else:
        score_adj = 0.00

    # Combine adjustments (max -0.08 reduction for perfect zones)
    rf_threshold = max(0.50, base_threshold + grade_adj + score_adj)

    logger.debug(
        f"RF threshold for {symbol}: base={base_threshold:.0%}, "
        f"grade_adj={grade_adj:+.0%} ({zone_grade}), score_adj={score_adj:+.0%} ({zone_score:.0f}), "
        f"final={rf_threshold:.0%}"
    )
    if rf_prob < rf_threshold:
        # When RF returns 0.5, it's usually model missing or prediction error – show real cause
        if rf_prob == 0.5 and ("Disabled" in rf_note or "Error" in rf_note):
            result["reason"] = rf_note
        else:
            result["reason"] = (
                f"RF probability {rf_prob:.1%} below {rf_threshold:.0%} threshold."
            )
        _log_brain_decision(symbol, result)
        return result

    # If LLM filter disabled, accept RF decision (but still include RAG/narrative)
    if not getattr(settings, "enable_llm_filter", True):
        result["decision"] = "GO"
        result["reason"] = "RF pass and LLM filter disabled."
        _log_brain_decision(symbol, result)
        return result

    # Step 5: LLM wisdom
    client = _get_llm_client()
    if client is None:
        result["decision"] = "GO"
        result["reason"] = "RF pass; LLM unavailable, defaulting to GO."
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
        else:
            result["decision"] = "NO_GO"
            result["reason"] = reason or "LLM rejected trade."
    except Exception as e:
        logger.error("LLM ensemble decision failed: %s", e)
        # Fail-open: RF already passed, so if LLM is down we allow the trade
        result["decision"] = "GO"
        result["reason"] = f"RF pass; LLM error (fail-open): {str(e)[:60]}"

    _log_brain_decision(symbol, result)
    return result


def _log_brain_decision(symbol: str, result: Dict[str, Any]) -> None:
    """Log brain prediction to trade_events for audit and tuning (Package C)."""
    try:
        from src.services.trade_events import log_event
        meta = {
            "decision": result.get("decision", ""),
            "rf_prob": result.get("rf_prob"),
            "reason": (result.get("reason") or "")[:300],
            "symbol": symbol,
            "num_rules": len(result.get("rules") or []),
        }
        log_event(None, "brain_prediction", "brain", meta)
    except Exception:
        pass


__all__ = ["load_brain", "get_prediction", "ensemble_decision"]

