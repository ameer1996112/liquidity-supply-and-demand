"""
Sprint 4.1: Backtest Lab API — jobs, SSE progress, metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtests", tags=["backtests"])

# In-memory progress for SSE (job_id -> thread-safe queue)
_progress_queues: Dict[int, queue.Queue] = {}


def _get_supabase():
    try:
        from src.adapters.supabase import supabase as sb
        if sb is None:
            from src.adapters.supabase import init_supabase
            init_supabase()
            from src.adapters.supabase import supabase as sb2
            return sb2
        return sb
    except Exception:
        return None


class BacktestStartBody(BaseModel):
    symbol: str = ""
    start_date: str = "2025-01-01"
    end_date: str = "2026-12-31"
    initial_cash: float = 10000.0
    daily_loss_limit: float = -500.0


def _run_backtest_job(backtest_id: int) -> None:
    """Background task: run engine, update DB, emit progress."""
    from src.services.backtest_engine import run_backtest

    sb = _get_supabase()
    if not sb:
        _emit_progress(backtest_id, 100, "Database unavailable", {"error": "No DB"})
        _update_status(sb, backtest_id, "failed", 100, error_message="Database unavailable")
        return

    try:
        row = sb.table("backtests").select("config_snapshot").eq("id", backtest_id).single().execute()
        config = (row.data or {}).get("config_snapshot") or {}
    except Exception:
        config = {}

    sb.table("backtests").update({
        "status": "running",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "progress": 0,
    }).eq("id", backtest_id).execute()

    def on_progress(percent: int, msg: str, extra: Dict):
        _emit_progress(backtest_id, percent, msg, extra)
        sb2 = _get_supabase()
        if sb2:
            sb2.table("backtests").update({"progress": percent}).eq("id", backtest_id).execute()

    try:
        metrics = run_backtest(backtest_id, config, sb, on_progress=on_progress)
        sb.table("backtests").update({
            "status": "completed",
            "progress": 100,
            "end_time": datetime.now(timezone.utc).isoformat(),
            "metrics_json": metrics,
        }).eq("id", backtest_id).execute()
        _emit_progress(backtest_id, 100, "Done", metrics)
    except Exception as e:
        logger.exception("Backtest %s failed: %s", backtest_id, e)
        sb.table("backtests").update({
            "status": "failed",
            "progress": 100,
            "end_time": datetime.now(timezone.utc).isoformat(),
            "error_message": str(e),
        }).eq("id", backtest_id).execute()
        _emit_progress(backtest_id, 100, "Failed", {"error": str(e)})
    finally:
        _close_progress_queue(backtest_id)


def _emit_progress(job_id: int, percent: int, message: str, extra: Dict) -> None:
    q = _progress_queues.get(job_id)
    if q:
        try:
            q.put_nowait({"percent": percent, "message": message, "extra": extra})
        except queue.Full:
            pass


def _close_progress_queue(job_id: int) -> None:
    q = _progress_queues.pop(job_id, None)
    if q:
        try:
            q.put_nowait(None)  # sentinel
        except queue.Full:
            pass


def _update_status(sb, job_id: int, status: str, progress: int, error_message: Optional[str] = None) -> None:
    if not sb:
        return
    try:
        data = {"status": status, "progress": progress}
        if error_message:
            data["error_message"] = error_message
        sb.table("backtests").update(data).eq("id", job_id).execute()
    except Exception as e:
        logger.warning("Failed to update backtest status: %s", e)


@router.post("")
def start_backtest(body: BacktestStartBody, background_tasks: BackgroundTasks):
    """Start a backtest job. Returns job id."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    config = {
        "symbol": body.symbol,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "initial_cash": body.initial_cash,
        "daily_loss_limit": body.daily_loss_limit,
    }
    try:
        resp = sb.table("backtests").insert({
            "status": "pending",
            "progress": 0,
            "config_snapshot": config,
        }).execute()
        if not resp.data or len(resp.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to create job")
        job_id = int(resp.data[0]["id"])
        _progress_queues[job_id] = queue.Queue()
        background_tasks.add_task(_run_backtest_job, job_id)
        return {"id": job_id, "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_backtests(limit: int = 20):
    """List backtest jobs."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = (
            sb.table("backtests")
            .select("*")
            .order("created_at", desc=True)
            .limit(min(limit, 100))
            .execute()
        )
        return {"jobs": resp.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
def get_backtest(job_id: int):
    """Get backtest status + metrics."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = sb.table("backtests").select("*").eq("id", job_id).single().execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Backtest not found")
        return resp.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/stream")
async def stream_backtest(job_id: int):
    """SSE stream of progress events."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = sb.table("backtests").select("id").eq("id", job_id).single().execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Backtest not found")
    except HTTPException:
        raise

    q = _progress_queues.get(job_id)
    if not q:
        q = queue.Queue()
        _progress_queues[job_id] = q

    async def event_generator():
        try:
            while True:
                try:
                    ev = await asyncio.to_thread(lambda: q.get(timeout=60))
                    if ev is None:
                        break
                    yield f"data: {json.dumps(ev)}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'percent': -1, 'message': 'ping', 'extra': {}})}\n\n"
        finally:
            _progress_queues.pop(job_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
