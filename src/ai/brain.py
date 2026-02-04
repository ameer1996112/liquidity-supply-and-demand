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
MODEL_PATH = _ROOT / "ml" / "model.pkl"
ENCODERS_PATH = _ROOT / "ml" / "encoders.pkl"

AI_MODEL = None
AI_ENCODERS = None
_RAG_ENGINE: Optional[RagEngine] = None
_LLM_CLIENT: Optional[OpenAI] = None


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

    This remains a pure RF call for backward compatibility. The full
    ensemble decision is implemented in `ensemble_decision`.
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
        # Use standard OpenAI client with OPENAI_API_KEY
        _LLM_CLIENT = OpenAI()
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

    # Step 1: RF filter
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

    if rf_prob < 0.60:
        result["reason"] = f"RF probability {rf_prob:.1%} below 60% threshold."
        return result

    # If LLM filter disabled, accept RF decision
    if not getattr(settings, "enable_llm_filter", True):
        result["decision"] = "GO"
        result["reason"] = "RF pass and LLM filter disabled."
        return result

    symbol = payload.get("symbol", "UNKNOWN")

    # Step 2: Market narrative
    try:
        narrative = get_market_narrative(symbol)
    except Exception as e:
        logger.error("Market narrative failed for %s: %s", symbol, e)
        narrative = f"{symbol} market narrative unavailable."
    result["narrative"] = narrative

    # Step 2b: RAG retrieval
    rag = _get_rag_engine()
    rules_texts: list[str] = []
    if rag is not None:
        try:
            # Restrict RAG to 5-minute S&D strategy rules
            docs = rag.query_rules(
                narrative,
                k=4,
                filter={"timeframe": "5m"},
            )
            rules_texts = [d.page_content for d in docs]
        except Exception as e:
            logger.error("RAG query failed: %s", e)
    else:
        logger.warning("RagEngine unavailable; skipping RAG retrieval.")
    result["rules"] = rules_texts

    # Step 3: LLM wisdom
    client = _get_llm_client()
    if client is None:
        # Fallback: trust RF
        result["decision"] = "GO"
        result["reason"] = "RF pass; LLM unavailable, defaulting to GO."
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
        # On failure, be conservative or trust RF – choose conservative:
        result["decision"] = "NO_GO"
        result["reason"] = f"LLM error: {str(e)[:80]}"

    return result


__all__ = ["load_brain", "get_prediction", "ensemble_decision"]

