"""
Sprint 3.3: Persist and link ai_run records (debate guardrail).
"""

import logging
from typing import Any, Dict, Optional

from src.services.strategy_config import get_active_strategy

logger = logging.getLogger(__name__)


def build_ai_run_row(correlation_id: str, run_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "run_type": "debate",
        "analysis_mode": run_payload.get("analysis_mode", "shadow_pretrade"),
        "recommendation": run_payload.get("recommendation", "allow"),
        "confidence": run_payload.get("confidence", 0),
        "chart_context": run_payload.get("chart_context", {}),
        "pine_context": run_payload.get("pine_context", {}),
        "module_status": run_payload.get("module_status", {}),
        "layered_output": run_payload.get("layered_output", {}),
        "reason_codes": run_payload.get("reason_codes", []),
        "memo": run_payload.get("memo", ""),
        "votes": run_payload.get("votes", {}),
        "transcript": run_payload.get("transcript", []),
    }


def _get_trace_id_by_correlation(supabase: Any, correlation_id: str) -> Optional[str]:
    """Fetch trace_id from pipeline_traces by correlation_id. Returns None if not found."""
    if not supabase or not correlation_id:
        return None
    try:
        resp = (
            supabase.table("pipeline_traces")
            .select("trace_id")
            .eq("correlation_id", correlation_id)
            .limit(1)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            tid = resp.data[0].get("trace_id")
            return str(tid) if tid else None
    except Exception as e:
        logger.debug("Failed to fetch trace_id for %s: %s", correlation_id, e)
    return None


def init_ai_run(supabase: Any, correlation_id: str) -> bool:
    """Synchronously create a placeholder ai_run so later async steps can find it and logic.py can link signal_id."""
    if not supabase or not correlation_id:
        return False
    try:
        supabase.table("ai_runs").insert({
            "correlation_id": correlation_id,
            "run_type": "debate",
            "recommendation": "pending",
            "confidence": 0,
        }).execute()
        return True
    except Exception as e:
        logger.warning("Failed to init ai_run for %s: %s", correlation_id, e)
        return False


def persist_debate(
    supabase: Any,
    correlation_id: str,
    debate_result: Dict[str, Any],
    *,
    trace_id: Optional[str] = None,
) -> Optional[int]:
    """
    Persist debate result to ai_runs. Returns ai_run id or None.
    """
    if not supabase or not correlation_id:
        return None
    try:
        rec = debate_result.get("recommendation", "allow")
        conf = int(debate_result.get("confidence", 50))
        conf = max(0, min(100, conf))
        codes = debate_result.get("reason_codes", [])
        if not isinstance(codes, list):
            codes = []
        memo = (debate_result.get("memo") or "")[:500]
        votes = debate_result.get("votes", {})
        if not isinstance(votes, dict):
            votes = {}
        transcript = debate_result.get("transcript", [])
        if not isinstance(transcript, list):
            transcript = []

        row = build_ai_run_row(
            correlation_id,
            {
                "recommendation": rec,
                "confidence": conf,
                "reason_codes": codes,
                "memo": memo,
                "votes": votes,
                "transcript": transcript,
                "analysis_mode": debate_result.get("analysis_mode", "shadow_pretrade"),
                "chart_context": debate_result.get("chart_context", {}),
                "pine_context": debate_result.get("pine_context", {}),
                "module_status": debate_result.get("module_status", {}),
                "layered_output": debate_result.get("layered_output", {}),
            },
        )
        # Snapshot current active strategy (if any) onto this ai_run
        try:
            active = get_active_strategy(supabase)
        except Exception as strat_exc:  # noqa: BLE001
            active = None
            logger.debug("ai_runs: active strategy lookup failed: %s", strat_exc)

        if active:
            row["strategy_id"] = active.get("id")
            row["strategy_version"] = active.get("version")
            cfg = active.get("config") or {}
            row["strategy_config_snapshot"] = cfg
        if trace_id:
            row["trace_id"] = trace_id

        # Try to modify existing placeholder first
        existing = supabase.table("ai_runs").select("id").eq("correlation_id", correlation_id).execute()
        if existing.data and len(existing.data) > 0:
            resp = supabase.table("ai_runs").update(row).eq("correlation_id", correlation_id).execute()
        else:
            resp = supabase.table("ai_runs").insert(row).execute()

        if resp.data and len(resp.data) > 0:
            return int(resp.data[0]["id"])
        return None
    except Exception as e:
        logger.warning("Failed to persist ai_run: %s", e)
        return None


def link_ai_run_to_signal(
    supabase: Any,
    correlation_id: str,
    signal_id: int,
) -> bool:
    """
    Update ai_run and pipeline_traces with signal_id when signal is created.
    Returns True if updated.
    """
    if not supabase or not correlation_id or not signal_id:
        return False
    ok = False
    try:
        supabase.table("ai_runs").update({"signal_id": signal_id}).eq(
            "correlation_id", correlation_id
        ).execute()
        ok = True
    except Exception as e:
        logger.warning("Failed to link ai_run to signal: %s", e)
    try:
        supabase.table("pipeline_traces").update({"signal_id": signal_id}).eq(
            "correlation_id", correlation_id
        ).execute()
    except Exception as e:
        logger.debug("Failed to update pipeline_traces signal_id: %s", e)
    return ok
