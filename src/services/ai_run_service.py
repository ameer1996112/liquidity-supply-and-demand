"""
Sprint 3.3: Persist and link ai_run records (debate guardrail).
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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

        row = {
            "correlation_id": correlation_id,
            "run_type": "debate",
            "recommendation": rec,
            "confidence": conf,
            "reason_codes": codes,
            "memo": memo,
            "votes": votes,
            "transcript": transcript,
        }
        if trace_id:
            row["trace_id"] = trace_id

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
