"""
Sprint 3.3: API for ai_run records (debate transcript + votes).
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from config import get_settings

router = APIRouter(prefix="/api/ai-runs", tags=["ai-runs"])


def _get_supabase():
    from supabase import create_client
    s = get_settings()
    raw_key = s.supabase_service_role_key or s.supabase_key or ""
    key = raw_key.strip().strip('"\'').strip()
    if key.upper().startswith("SUPA") and "=" in key[:50]:
        key = key.split("=", 1)[-1].strip().strip('"\'').strip()
    if not s.supabase_url or not key:
        return None
    return create_client(s.supabase_url, key)


@router.get("", response_model=Dict[str, Any])
def get_ai_run_by_signal(signal_id: int = Query(..., description="Trading signal ID")):
    """
    Fetch ai_run (debate transcript + votes) for a signal.
    Looks up by signal_id first, then by correlation_id from pipeline_traces.
    Returns 404 if no ai_run exists for this signal.
    """
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = (
            sb.table("ai_runs")
            .select("*")
            .eq("signal_id", signal_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data or len(resp.data) == 0:
            # Fallback: get correlation_id from pipeline_traces, then fetch ai_run
            trace_resp = (
                sb.table("pipeline_traces")
                .select("correlation_id")
                .eq("signal_id", signal_id)
                .limit(1)
                .execute()
            )
            if trace_resp.data and trace_resp.data[0].get("correlation_id"):
                corr = trace_resp.data[0]["correlation_id"]
                resp = (
                    sb.table("ai_runs")
                    .select("*")
                    .eq("correlation_id", corr)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
        if not resp.data or len(resp.data) == 0:
            raise HTTPException(status_code=404, detail="No AI run found for this signal")
        row = resp.data[0]
        return {
            "id": row["id"],
            "correlation_id": row.get("correlation_id"),
            "signal_id": row.get("signal_id"),
            "run_type": row.get("run_type", "debate"),
            "recommendation": row.get("recommendation", "allow"),
            "confidence": row.get("confidence", 0),
            "reason_codes": row.get("reason_codes") or [],
            "memo": row.get("memo") or "",
            "votes": row.get("votes") or {},
            "transcript": row.get("transcript") or [],
            "created_at": row.get("created_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
