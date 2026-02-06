"""Backtest API -- run, list, and compare backtest runs."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])

# ── Lazy Supabase ────────────────────────────────────────────

_client = None


def _get_supabase():
    global _client
    if _client is not None:
        return _client
    s = get_settings()
    key = (s.supabase_service_role_key or s.supabase_key or "").strip()
    if not s.supabase_url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    from supabase import create_client

    _client = create_client(s.supabase_url, key)
    return _client


# ── Models ───────────────────────────────────────────────────


class BacktestRunRequest(BaseModel):
    name: str = Field(default="Unnamed Backtest")
    config_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Settings overrides: risk_percent, pine_min_score, ml_min_confidence, etc.",
    )
    signal_source: str = Field(
        default="date_range",
        description="'date_range' to pull from DB, 'payload_list' to supply signals inline",
    )
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    signals: Optional[List[Dict[str, Any]]] = None


class BacktestRunResponse(BaseModel):
    run_id: str
    status: str


# ── Background task ──────────────────────────────────────────


def _run_backtest_task(run_id: str, request: BacktestRunRequest) -> None:
    from src.services.backtest_engine import BacktestEngine

    sb = _get_supabase()
    engine = BacktestEngine(config_overrides=request.config_overrides, run_id=run_id)

    try:
        sb.table("backtest_runs").update(
            {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
        ).eq("run_id", run_id).execute()

        # Load signals
        if request.signal_source == "payload_list" and request.signals:
            signals = request.signals
        else:
            query = sb.table("trading_signals").select("*").eq("run_mode", "LIVE")
            if request.date_from:
                query = query.gte("created_at", request.date_from)
            if request.date_to:
                query = query.lte("created_at", request.date_to)
            query = query.order("created_at").limit(500)
            resp = query.execute()
            signals = resp.data or []

        engine.run(signals)
    except Exception as exc:
        logger.error("Backtest %s failed: %s", run_id, exc)
        try:
            sb.table("backtest_runs").update(
                {
                    "status": "failed",
                    "result_summary": f'{{"error": "{str(exc)[:200]}"}}',
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("run_id", run_id).execute()
        except Exception:
            pass


# ── Endpoints ────────────────────────────────────────────────


@router.post("/run", response_model=BacktestRunResponse)
def start_backtest(body: BacktestRunRequest, background_tasks: BackgroundTasks):
    """Start a backtest run asynchronously."""
    run_id = f"bt-{int(time.time())}"
    sb = _get_supabase()

    sb.table("backtest_runs").insert(
        {"run_id": run_id, "name": body.name, "config": body.config_overrides, "status": "pending"}
    ).execute()

    background_tasks.add_task(_run_backtest_task, run_id, body)
    return BacktestRunResponse(run_id=run_id, status="pending")


@router.get("/runs")
def list_backtest_runs(limit: int = 20):
    """List all backtest runs, newest first."""
    sb = _get_supabase()
    resp = sb.table("backtest_runs").select("*").order("created_at", desc=True).limit(limit).execute()
    return {"runs": resp.data or []}


@router.get("/runs/{run_id}")
def get_backtest_run(run_id: str):
    """Get details of a specific backtest run."""
    sb = _get_supabase()
    resp = sb.table("backtest_runs").select("*").eq("run_id", run_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Run not found")
    return resp.data[0]


@router.get("/compare")
def compare_runs(run_id_1: str = "live", run_id_2: str = ""):
    """Side-by-side comparison of two runs (e.g. live vs backtest)."""
    from src.adapters.supabase import get_statistics

    stats_1 = get_statistics(
        run_mode="LIVE" if run_id_1 == "live" else "BACKTEST",
        run_id=None if run_id_1 == "live" else run_id_1,
    )
    stats_2 = (
        get_statistics(run_mode="BACKTEST", run_id=run_id_2) if run_id_2 else {}
    )

    return {
        "run_1": {"run_id": run_id_1, "stats": stats_1},
        "run_2": {"run_id": run_id_2, "stats": stats_2} if run_id_2 else None,
    }
