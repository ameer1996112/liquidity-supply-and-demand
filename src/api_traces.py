"""
Pipeline Traces API — Sprint 2.1 latency instrumentation endpoints.

Routes
------
GET /api/traces                     List recent traces (paginated)
GET /api/traces/{correlation_id}    Single trace detail
GET /api/traces/stats               Aggregate p50/p95 per hop
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/traces", tags=["traces"])

from src.adapters.supabase_api import get_api_supabase as _get_supabase

# ── Response models ────────────────────────────────────────────────────────────

class TraceHops(BaseModel):
    received_at:         Optional[str] = None
    enqueued_at:         Optional[str] = None
    dequeued_at:         Optional[str] = None
    validated_at:        Optional[str] = None
    risk_started_at:     Optional[str] = None
    risk_finished_at:    Optional[str] = None
    exec_started_at:     Optional[str] = None
    exec_submitted_at:   Optional[str] = None
    broker_ack_at:       Optional[str] = None
    broker_confirmed_at: Optional[str] = None
    reconciled_at:       Optional[str] = None
    error_at:            Optional[str] = None


class TraceSummary(BaseModel):
    trace_id:       Optional[str] = None
    correlation_id: str
    signal_id:      Optional[int] = None
    account_id:     Optional[str] = None
    symbol:         Optional[str] = None
    run_mode:       Optional[str] = None
    received_at:    Optional[str] = None
    total_ms:       Optional[float] = None
    error_type:     Optional[str] = None
    created_at:     Optional[str] = None


class TraceDetail(TraceSummary):
    hops:          TraceHops = TraceHops()
    error_message: Optional[str] = None


class HopStats(BaseModel):
    hop:    str
    count:  int
    p50_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None
    avg_ms: Optional[float] = None


class StatsResponse(BaseModel):
    window_hours: int
    total_traces: int
    hops:         List[HopStats]


# ── Helpers ────────────────────────────────────────────────────────────────────

_HOP_FIELDS = [
    "received_at",
    "enqueued_at",
    "dequeued_at",
    "validated_at",
    "risk_started_at",
    "risk_finished_at",
    "exec_started_at",
    "exec_submitted_at",
    "broker_ack_at",
    "broker_confirmed_at",
    "reconciled_at",
    "error_at",
]

_DETAIL_SELECT = (
    "trace_id,correlation_id,signal_id,account_id,symbol,run_mode,"
    "received_at,enqueued_at,dequeued_at,validated_at,"
    "risk_started_at,risk_finished_at,exec_started_at,exec_submitted_at,"
    "broker_ack_at,broker_confirmed_at,reconciled_at,error_at,"
    "error_type,error_message,created_at,updated_at"
)

_LIST_SELECT = (
    "trace_id,correlation_id,signal_id,account_id,symbol,run_mode,"
    "received_at,exec_submitted_at,error_at,error_type,created_at"
)


def _total_ms(row: Dict[str, Any]) -> Optional[float]:
    """Compute end-to-end ms from received_at to submitted/error."""
    start_str = row.get("received_at")
    end_str = row.get("exec_submitted_at") or row.get("error_at")
    if not start_str or not end_str:
        return None
    try:
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
        return round((end - start).total_seconds() * 1000, 3)
    except (ValueError, TypeError):
        return None


def _to_summary(row: Dict[str, Any]) -> TraceSummary:
    return TraceSummary(
        trace_id=row.get("trace_id"),
        correlation_id=row["correlation_id"],
        signal_id=row.get("signal_id"),
        account_id=row.get("account_id"),
        symbol=row.get("symbol"),
        run_mode=row.get("run_mode"),
        received_at=row.get("received_at"),
        total_ms=_total_ms(row),
        error_type=row.get("error_type"),
        created_at=row.get("created_at"),
    )


def _to_detail(row: Dict[str, Any]) -> TraceDetail:
    hops = TraceHops(**{f: row.get(f) for f in _HOP_FIELDS})
    return TraceDetail(
        trace_id=row.get("trace_id"),
        correlation_id=row["correlation_id"],
        signal_id=row.get("signal_id"),
        account_id=row.get("account_id"),
        symbol=row.get("symbol"),
        run_mode=row.get("run_mode"),
        received_at=row.get("received_at"),
        total_ms=_total_ms(row),
        error_type=row.get("error_type"),
        error_message=row.get("error_message"),
        created_at=row.get("created_at"),
        hops=hops,
    )


def _percentile(data: List[float], pct: float) -> Optional[float]:
    if not data:
        return None
    data_sorted = sorted(data)
    idx = (pct / 100) * (len(data_sorted) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(data_sorted) - 1)
    return round(data_sorted[lo] + (data_sorted[hi] - data_sorted[lo]) * (idx - lo), 3)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TraceSummary])
def list_traces(
    limit:      int            = Query(50, ge=1, le=500),
    account_id: Optional[str]  = Query(None),
    symbol:     Optional[str]  = Query(None),
    run_mode:   Optional[str]  = Query(None),
    hours:      Optional[int]  = Query(None, ge=1, le=720, description="Look-back window in hours"),
    has_error:  Optional[bool] = Query(None, description="Filter to only error/success traces"),
):
    """List recent pipeline traces with a lightweight summary per trace."""
    try:
        sb = _get_supabase()
        q = (
            sb.table("pipeline_traces")
            .select(_LIST_SELECT)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if account_id:
            q = q.eq("account_id", account_id)
        if symbol:
            q = q.eq("symbol", symbol.upper())
        if run_mode:
            q = q.eq("run_mode", run_mode.upper())
        if hours is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            q = q.gte("created_at", cutoff)
        if has_error is True:
            q = q.not_.is_("error_at", "null")
        elif has_error is False:
            q = q.is_("error_at", "null")

        resp = q.execute()
        return [_to_summary(r) for r in (resp.data or [])]
    except Exception as exc:
        logger.error("list_traces error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats", response_model=StatsResponse)
def traces_stats(
    hours: int = Query(24, ge=1, le=720, description="Look-back window in hours"),
):
    """Return p50/p95/p99 latency per hop over the given window."""
    try:
        sb = _get_supabase()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        resp = (
            sb.table("pipeline_traces")
            .select(_DETAIL_SELECT)
            .gte("created_at", cutoff)
            .limit(5000)
            .execute()
        )
        rows = resp.data or []

        # Collect ms durations for adjacent hop pairs
        hop_pairs = [
            ("queue_wait_ms",  "enqueued_at",       "dequeued_at"),
            ("pre_risk_ms",    "dequeued_at",        "risk_started_at"),
            ("risk_ms",        "risk_started_at",    "risk_finished_at"),
            ("exec_ms",        "exec_started_at",    "exec_submitted_at"),
            ("total_ms",       "received_at",        "exec_submitted_at"),
        ]

        buckets: Dict[str, List[float]] = {name: [] for name, *_ in hop_pairs}
        for row in rows:
            for name, t_start, t_end in hop_pairs:
                s = row.get(t_start)
                e = row.get(t_end)
                if s and e:
                    try:
                        ms = (datetime.fromisoformat(e) - datetime.fromisoformat(s)).total_seconds() * 1000
                        if ms >= 0:
                            buckets[name].append(ms)
                    except (ValueError, TypeError):
                        pass

        hop_stats = []
        for name, _, _ in hop_pairs:
            vals = buckets[name]
            hop_stats.append(HopStats(
                hop=name,
                count=len(vals),
                p50_ms=_percentile(vals, 50),
                p95_ms=_percentile(vals, 95),
                p99_ms=_percentile(vals, 99),
                avg_ms=round(statistics.mean(vals), 3) if vals else None,
            ))

        return StatsResponse(
            window_hours=hours,
            total_traces=len(rows),
            hops=hop_stats,
        )
    except Exception as exc:
        logger.error("traces_stats error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{correlation_id}", response_model=TraceDetail)
def get_trace(correlation_id: str):
    """Fetch a single pipeline trace by correlation_id."""
    try:
        sb = _get_supabase()
        resp = (
            sb.table("pipeline_traces")
            .select(_DETAIL_SELECT)
            .eq("correlation_id", correlation_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Trace {correlation_id!r} not found")
        return _to_detail(rows[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_trace error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
