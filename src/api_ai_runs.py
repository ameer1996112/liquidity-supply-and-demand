"""
Sprint 3.3: API for ai_run records (debate transcript + votes).
"""

from typing import Any, Dict, List

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


def _run_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    rec = str(row.get("recommendation") or "allow").lower()
    return {
        "recommendation": rec,
        "confidence": row.get("confidence", 0),
        "votes": row.get("votes") or {},
        "status": "pending" if rec == "pending" else "complete",
    }


def _prefer_run_summary(
    runs: Dict[str, Any],
    signal_id: str,
    row: Dict[str, Any],
) -> None:
    """Keep completed council rows ahead of pending placeholders."""
    summary = _run_summary(row)
    existing = runs.get(signal_id)
    if existing and existing.get("status") != "pending":
        return
    if summary["status"] == "complete" or not existing:
        runs[signal_id] = summary


def _signal_score_summary(row: Dict[str, Any]) -> Dict[str, Any] | None:
    """Build a display fallback from the signal's stored score fields."""
    raw_score = row.get("score")
    if raw_score is None:
        raw_score = row.get("ai_confidence")
    if raw_score is None:
        return None
    try:
        confidence = int(round(float(raw_score)))
    except (TypeError, ValueError):
        return None
    confidence = max(0, min(100, confidence))
    return {
        "recommendation": "allow",
        "confidence": confidence,
        "votes": {},
        "status": "complete",
        "source": "signal_score",
    }


def _fill_signal_score_fallbacks(
    sb: Any,
    runs: Dict[str, Any],
    signal_ids: List[int],
) -> None:
    """Fill missing/stuck council summaries from trading_signals score columns."""
    fallback_ids = [
        sid
        for sid in signal_ids
        if str(sid) not in runs or runs[str(sid)].get("status") == "pending"
    ]
    if not fallback_ids:
        return

    signals_resp = (
        sb.table("trading_signals")
        .select("id, score, ai_confidence")
        .in_("id", fallback_ids)
        .execute()
    )
    for row in signals_resp.data or []:
        sid = str(row.get("id"))
        summary = _signal_score_summary(row)
        if summary:
            runs[sid] = summary


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
            return {"data": None}
        row = resp.data[0]
        return {
            "id": row["id"],
            "correlation_id": row.get("correlation_id"),
            "signal_id": row.get("signal_id"),
            "run_type": row.get("run_type", "debate"),
            "analysis_mode": row.get("analysis_mode", "shadow_pretrade"),
            "recommendation": row.get("recommendation", "allow"),
            "confidence": row.get("confidence", 0),
            "reason_codes": row.get("reason_codes") or [],
            "memo": row.get("memo") or "",
            "votes": row.get("votes") or {},
            "transcript": row.get("transcript") or [],
            "chart_context": row.get("chart_context") or {},
            "pine_context": row.get("pine_context") or {},
            "module_status": row.get("module_status") or {},
            "layered_output": row.get("layered_output") or {},
            "council_report": row.get("council_report") or {},
            "created_at": row.get("created_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bulk", response_model=Dict[str, Any])
def get_ai_runs_bulk(signal_ids: str = Query(..., description="Comma-separated signal IDs")):
    """
    Fetch council summary (recommendation, confidence, votes) for multiple signals at once.
    Returns a dict keyed by signal_id (as string) → {recommendation, confidence, votes}.
    Missing signals are omitted from the response.

    Two-pass strategy:
      1. Direct query on ai_runs.signal_id (fast path for new signals)
      2. Fallback via pipeline_traces.correlation_id for older signals where
         ai_runs.signal_id was never populated (handles the pre-fix race condition)
    """
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        raw_ids = [x.strip() for x in signal_ids.split(",") if x.strip()]
        int_ids: List[int] = []
        for x in raw_ids:
            try:
                int_ids.append(int(x))
            except ValueError:
                pass
        if not int_ids:
            return {"runs": {}}

        # Pass 1: direct signal_id lookup
        resp = (
            sb.table("ai_runs")
            .select("signal_id, recommendation, confidence, votes, created_at")
            .in_("signal_id", int_ids)
            .order("created_at", desc=True)
            .execute()
        )
        runs: Dict[str, Any] = {}
        if resp.data:
            for row in resp.data:
                sid = str(row.get("signal_id"))
                _prefer_run_summary(runs, sid, row)

        # Pass 2: fallback via pipeline_traces for any still-missing signals
        # (covers older positions recorded before the race condition fix)
        missing_ids = [
            sid
            for sid in int_ids
            if str(sid) not in runs or runs[str(sid)].get("status") == "pending"
        ]
        if missing_ids:
            try:
                traces_resp = (
                    sb.table("pipeline_traces")
                    .select("signal_id, correlation_id")
                    .in_("signal_id", missing_ids)
                    .execute()
                )
                if traces_resp.data:
                    corr_to_signal: Dict[str, int] = {}
                    for t in traces_resp.data:
                        if t.get("correlation_id") and t.get("signal_id"):
                            corr_to_signal[t["correlation_id"]] = int(t["signal_id"])

                    if corr_to_signal:
                        corr_ids = list(corr_to_signal.keys())
                        ai_resp = (
                            sb.table("ai_runs")
                            .select("correlation_id, recommendation, confidence, votes, created_at")
                            .in_("correlation_id", corr_ids)
                            .order("created_at", desc=True)
                            .execute()
                        )
                        if ai_resp.data:
                            for row in ai_resp.data:
                                corr = row.get("correlation_id")
                                if corr and corr in corr_to_signal:
                                    sid = str(corr_to_signal[corr])
                                    if str(row.get("recommendation") or "").lower() != "pending":
                                        _prefer_run_summary(runs, sid, row)
            except Exception:
                pass  # Fallback failure is silent — never break the main response

        _fill_signal_score_fallbacks(sb, runs, int_ids)

        return {"runs": runs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
