"""
Supervisor — The Council Room Orchestrator

Logic:
  1. Receive signal from worker.
  2. Query Quant Agent for a probability score.
  3. If score > QUANT_THRESHOLD (0.35): consult Risk Agent.
  4. If both approve → EXECUTE.

All debate steps are published to Redis pub/sub channel `trading:debate_logs`
so the frontend WebSocket can stream them live to the AI Terminal.

Returns a dict backward-compatible with the old ensemble_decision() format:
  {"decision": "GO"|"NO_GO", "rf_prob": float, "reason": str, ...}
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

QUANT_THRESHOLD = float(os.environ.get("MAS_QUANT_THRESHOLD", "0.35"))
DEBATE_CHANNEL  = "trading:debate_logs"


def _confidence_label(conf: float) -> str:
    if conf >= 0.70:
        return "High"
    if conf >= 0.45:
        return "Medium"
    return "Low"


class Supervisor:
    """
    The Council Room: orchestrates the Quant → Risk debate for each signal.

    Instantiate once per signal so each evaluation sees a fresh snapshot of
    the database state (via the Risk Agent).
    """

    def __init__(self, supabase_client=None, redis_client=None):
        from src.agents.quant_agent import QuantAgent
        from src.agents.risk_agent  import RiskAgent

        self.quant = QuantAgent()
        self.risk  = RiskAgent(supabase_client)
        self._redis = redis_client

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the full council debate for one signal.

        Returns:
            {
                "decision":   "GO" | "NO_GO",
                "rf_prob":    float,   # backward-compat with old ensemble_decision
                "reason":     str,
                "quant_vote": "YES" | "NO",
                "risk_vote":  "YES" | "NO" | "SKIPPED",
            }
        """
        symbol = payload.get("symbol", "UNKNOWN")
        side   = (payload.get("side") or "?").upper()

        self._log("supervisor", f"Received Signal {symbol} {side}.", "INFO")

        # ── Round 1: Quant ────────────────────────────────────────────────────
        quant_result = self.quant.evaluate(payload)
        conf  = quant_result["confidence"]
        label = _confidence_label(conf)

        self._log(
            "quant_agent",
            f"Model Confidence {conf:.2f} ({label}).",
            "EXEC" if quant_result["vote"] == "YES" else "WARN",
        )

        if conf < QUANT_THRESHOLD:
            reason = f"Score {conf:.2f} below threshold {QUANT_THRESHOLD}. {quant_result['reason']}"
            self._log("supervisor", f"Final Decision - BLOCKED. ({reason})", "ERR")
            return {
                "decision":   "NO_GO",
                "rf_prob":    conf,
                "reason":     f"[MAS] Quant blocked: {reason}",
                "quant_vote": quant_result["vote"],
                "risk_vote":  "SKIPPED",
            }

        # ── Round 2: Risk ─────────────────────────────────────────────────────
        risk_result = self.risk.evaluate(symbol)

        if risk_result["vote"] == "NO":
            self._log("risk_agent", f"BLOCK. {risk_result['reason']}", "ERR")
            self._log("supervisor", "Final Decision - BLOCKED.", "ERR")
            return {
                "decision":   "NO_GO",
                "rf_prob":    conf,
                "reason":     f"[MAS] Risk blocked: {risk_result['reason']}",
                "quant_vote": quant_result["vote"],
                "risk_vote":  "NO",
            }

        self._log("risk_agent", f"APPROVE. {risk_result['reason']}", "EXEC")
        self._log(
            "supervisor",
            f"Final Decision - EXECUTE. (conf={conf:.2f}, {risk_result['reason']})",
            "EXEC",
        )

        return {
            "decision":   "GO",
            "rf_prob":    conf,
            "reason":     f"[MAS] Quant={conf:.0%} | {risk_result['reason']}",
            "quant_vote": quant_result["vote"],
            "risk_vote":  "YES",
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _log(self, agent: str, message: str, level: str = "INFO") -> None:
        """Log to Python logger and publish to Redis for WebSocket streaming."""
        logger.info("[%s] %s", agent.upper(), message)
        if not self._redis:
            return
        try:
            self._redis.publish(
                DEBATE_CHANNEL,
                json.dumps({"agent": agent, "message": message, "level": level}),
            )
        except Exception as exc:
            logger.warning("[SUPERVISOR] Redis publish failed: %s", exc)
