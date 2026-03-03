"""
Quant Agent — The Brain

Wraps the trained MLGuardian (LightGBM) to produce a structured YES/NO vote
for the Supervisor.

Input:  signal payload dict
Output: {"vote": "YES"|"NO", "confidence": float, "reason": str}
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Minimum confidence to vote YES (overridable via env through MLGuardian settings)
_THRESHOLD = 0.35


class QuantAgent:
    """Scores signals with the trained ML model and returns a council vote."""

    def __init__(self):
        try:
            from src.ai.ml_guardian import create_ml_guardian_from_settings
            self._guardian = create_ml_guardian_from_settings()
        except Exception as exc:
            logger.warning("[QUANT] MLGuardian init failed (will fail-open): %s", exc)
            self._guardian = None

    def evaluate(self, payload: Dict[str, Any]) -> dict:
        """
        Score a signal and return a YES/NO vote.

        Returns:
            {
                "vote":       "YES" | "NO",
                "confidence": float (0–1),
                "reason":     str,
            }
        """
        if not self._guardian:
            logger.warning("[QUANT] No model loaded — fail-open with 0.5 confidence")
            return {
                "vote":       "YES",
                "confidence": 0.5,
                "reason":     "Model unavailable (fail-open)",
            }

        try:
            passed, confidence, details = self._guardian.analyze(payload)
            decision_label = details.get("decision", "UNKNOWN")
            vote = "YES" if confidence >= _THRESHOLD else "NO"

            reason = (
                f"conf={confidence:.2f} | {decision_label}"
                if vote == "YES"
                else f"conf={confidence:.2f} below threshold={_THRESHOLD} | {decision_label}"
            )
            logger.info("[QUANT] vote=%s conf=%.4f | %s", vote, confidence, reason)
            return {"vote": vote, "confidence": round(confidence, 4), "reason": reason}

        except Exception as exc:
            logger.error("[QUANT] Evaluation error: %s", exc, exc_info=True)
            return {"vote": "NO", "confidence": 0.0, "reason": f"Quant agent error: {exc}"}
