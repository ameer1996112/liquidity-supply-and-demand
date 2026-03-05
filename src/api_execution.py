"""
Execution Quality API - Transaction Cost Analysis (TCA) endpoints.

Provides metrics on execution quality including:
- Slippage analysis
- Latency tracking
- Spread costs
- TCA alerts and reports
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_settings
from src.services.tca_analyzer import TCAAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution", tags=["execution"])


# ── Shared Supabase client with auto-reconnect ──────────────────

from src.adapters.supabase_api import get_api_supabase as _get_supabase, supabase_query


# ── Response Models ───────────────────────────────────────────────


class TCAMetricsResponse(BaseModel):
    """Aggregate TCA metrics for a time period"""
    total_trades: int
    avg_slippage_pips: float
    avg_slippage_bps: float
    total_slippage_cost_usd: float
    avg_spread_cost_usd: float
    avg_execution_time_ms: float
    worst_slippage_pips: float
    best_slippage_pips: float
    median_slippage_pips: float = 0.0
    total_spread_cost_usd: float = 0.0


class SlippageBySymbolResponse(BaseModel):
    """Slippage metrics grouped by symbol"""
    symbol: str
    avg_slippage_pips: float
    trade_count: int
    total_cost_usd: float
    worst_slippage_pips: float


class LatencyBreakdownResponse(BaseModel):
    """Latency statistics"""
    avg_signal_to_submit_ms: float
    avg_submit_to_fill_ms: float
    avg_total_execution_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    median_latency_ms: float


class TCAAlertResponse(BaseModel):
    """TCA alert/threshold violation"""
    id: int
    signal_id: int
    alert_type: str
    slippage_pips: Optional[float] = None
    total_execution_ms: Optional[int] = None
    exceeds_slippage_threshold: bool
    exceeds_latency_threshold: bool
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/tca-summary", response_model=TCAMetricsResponse)
@supabase_query
def get_tca_summary(
    days: int = Query(1, ge=1, le=90, description="Number of days to look back"),
    run_mode: Optional[str] = Query(None, description="Filter by LIVE or PAPER mode")
):
    """
    Get aggregate TCA metrics for the last N days.

    Returns execution quality statistics including:
    - Average slippage (pips and basis points)
    - Total transaction costs
    - Average execution latency
    - Best/worst slippage
    """
    try:
        client = _get_supabase()
        analyzer = TCAAnalyzer(client)
        metrics = analyzer.get_daily_tca_summary(days=days, run_mode=run_mode)

        return TCAMetricsResponse(
            total_trades=metrics.total_trades,
            avg_slippage_pips=metrics.avg_slippage_pips,
            avg_slippage_bps=metrics.avg_slippage_bps,
            total_slippage_cost_usd=metrics.total_slippage_cost_usd,
            avg_spread_cost_usd=metrics.avg_spread_cost_usd,
            avg_execution_time_ms=metrics.avg_execution_time_ms,
            worst_slippage_pips=metrics.worst_slippage_pips,
            best_slippage_pips=metrics.best_slippage_pips,
            median_slippage_pips=metrics.median_slippage_pips,
            total_spread_cost_usd=metrics.total_spread_cost_usd,
        )
    except Exception as e:
        logger.error(f"Failed to get TCA summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slippage-by-symbol", response_model=List[SlippageBySymbolResponse])
@supabase_query
def get_slippage_by_symbol(
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    run_mode: Optional[str] = Query(None, description="Filter by LIVE or PAPER mode")
):
    """
    Get average slippage grouped by trading symbol.

    Helps identify which instruments have best/worst execution quality.
    """
    try:
        client = _get_supabase()
        analyzer = TCAAnalyzer(client)
        results = analyzer.get_slippage_by_symbol(days=days, run_mode=run_mode)

        return [
            SlippageBySymbolResponse(
                symbol=r.symbol,
                avg_slippage_pips=r.avg_slippage_pips,
                trade_count=r.trade_count,
                total_cost_usd=r.total_cost_usd,
                worst_slippage_pips=r.worst_slippage_pips,
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Failed to get slippage by symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slippage-by-hour")
def get_slippage_by_hour(
    days: int = Query(7, ge=1, le=30, description="Number of days to look back")
):
    """
    Get average slippage by hour of day (0-23 UTC).

    Helps identify which trading hours have best execution quality.
    Useful for optimizing trade timing.
    """
    try:
        client = _get_supabase()
        analyzer = TCAAnalyzer(client)
        results = analyzer.get_slippage_by_hour(days=days)

        # Format as list of {hour, avg_slippage_pips} for easier charting
        return [
            {"hour": hour, "avg_slippage_pips": slippage}
            for hour, slippage in results.items()
        ]
    except Exception as e:
        logger.error(f"Failed to get slippage by hour: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latency-breakdown", response_model=LatencyBreakdownResponse)
@supabase_query
def get_latency_breakdown(
    days: int = Query(7, ge=1, le=30, description="Number of days to look back")
):
    """
    Get execution latency statistics with percentiles.

    Returns:
    - Average latency from signal → submit → fill
    - P95/P99 latency (tail performance)
    - Median latency
    """
    try:
        client = _get_supabase()
        analyzer = TCAAnalyzer(client)
        breakdown = analyzer.get_latency_breakdown(days=days)

        return LatencyBreakdownResponse(
            avg_signal_to_submit_ms=breakdown.avg_signal_to_submit_ms,
            avg_submit_to_fill_ms=breakdown.avg_submit_to_fill_ms,
            avg_total_execution_ms=breakdown.avg_total_execution_ms,
            p95_latency_ms=breakdown.p95_latency_ms,
            p99_latency_ms=breakdown.p99_latency_ms,
            median_latency_ms=breakdown.median_latency_ms,
        )
    except Exception as e:
        logger.error(f"Failed to get latency breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=List[TCAAlertResponse])
def get_tca_alerts(
    days: int = Query(7, ge=1, le=30, description="Number of days to look back"),
    limit: int = Query(50, ge=1, le=200, description="Max number of alerts to return")
):
    """
    Get recent TCA alerts (threshold violations).

    Returns trades that exceeded:
    - Slippage threshold (configured in settings)
    - Latency threshold (configured in settings)
    """
    try:
        client = _get_supabase()

        # Query tca_execution_metrics for alerts
        from datetime import datetime, timedelta, timezone
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        response = client.table("tca_execution_metrics").select(
            "id,signal_id,slippage_pips,total_execution_ms,"
            "exceeds_slippage_threshold,exceeds_latency_threshold,created_at,"
            "trading_signals(symbol)"
        ).gte(
            "created_at", start_date.isoformat()
        ).or_(
            "exceeds_slippage_threshold.eq.true,exceeds_latency_threshold.eq.true"
        ).order("created_at", desc=True).limit(limit).execute()

        alerts = []
        for record in response.data:
            signal = record.get("trading_signals") or {}
            symbol = signal.get("symbol", "UNKNOWN")

            # Determine alert type
            if record.get("exceeds_slippage_threshold"):
                alert_type = "high_slippage"
            elif record.get("exceeds_latency_threshold"):
                alert_type = "high_latency"
            else:
                alert_type = "unknown"

            alerts.append(TCAAlertResponse(
                id=record["id"],
                signal_id=record["signal_id"],
                alert_type=alert_type,
                slippage_pips=record.get("slippage_pips"),
                total_execution_ms=record.get("total_execution_ms"),
                exceeds_slippage_threshold=record.get("exceeds_slippage_threshold", False),
                exceeds_latency_threshold=record.get("exceeds_latency_threshold", False),
                created_at=record["created_at"],
            ))

        return alerts

    except Exception as e:
        logger.error(f"Failed to get TCA alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
def get_tca_settings():
    """
    Get current TCA configuration settings.

    Returns thresholds and enabled status.
    """
    s = get_settings()
    return {
        "tca_enabled": s.tca_enabled,
        "slippage_threshold_pips": s.tca_slippage_threshold_pips,
        "latency_threshold_ms": s.tca_latency_threshold_ms,
        "spread_threshold_pips": s.tca_spread_threshold_pips,
    }
