from __future__ import annotations

from typing import Any, Dict


def _base_layered_output() -> Dict[str, Any]:
    return {
        "top_level": {"verdict": "unclear", "confidence": 0},
        "scorecard": {"confluence": [], "risks": [], "evidence": []},
        "deep_layer": {"agent_opinions": [], "disagreements": []},
    }


def build_shadow_pretrade_run(
    signal_payload: Dict[str, Any],
    chart_context: Dict[str, Any],
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "analysis_mode": "shadow_pretrade",
        "signal_payload": signal_payload,
        "chart_context": chart_context,
        "pine_context": pine_context,
        "module_status": {
            "chart_context": {
                "status": chart_context.get("status", "degraded"),
                "reason": chart_context.get("reason", ""),
            }
        },
        "layered_output": _base_layered_output(),
    }


def build_posttrade_review_run(
    signal_payload: Dict[str, Any],
    trade_outcome: Dict[str, Any],
    chart_context: Dict[str, Any],
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    payload = build_shadow_pretrade_run(signal_payload, chart_context, pine_context)
    payload["analysis_mode"] = "posttrade_review"
    payload["trade_outcome"] = trade_outcome
    return payload
