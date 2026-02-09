"""
Prop Firm Metrics API
Real-time compliance tracking for FTMO/MyFundedFX challenges.

Endpoints:
- GET /api/prop-firm/metrics - Get real-time metrics with floating PnL
- GET /api/prop-firm/history - Get historical snapshots
- POST /api/prop-firm/reset - Manual daily reset
- GET /api/prop-firm/consistency - Get consistency analysis

Author: Trinity Engine v3.0
"""

import logging
from typing import Optional
from datetime import datetime, timezone, date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prop-firm", tags=["Prop Firm"])


class PropFirmMetricsResponse(BaseModel):
    """Response model for prop firm metrics."""
    status: str
    account_name: str
    evaluation_phase: str
    metrics: dict


@router.get("/metrics")
async def get_prop_firm_metrics(
    account_name: str = Query(default="default", description="Account identifier")
):
    """
    Get real-time prop firm compliance metrics.

    Includes:
    - Daily high water mark
    - Floating + closed PnL
    - Real-time drawdown percentages
    - Breach status
    - Days remaining in challenge
    - Consistency metrics

    Returns:
        PropFirmMetricsResponse with all compliance data
    """
    try:
        from supabase import create_client
        from src.services.prop_firm_tracker import PropFirmTracker

        settings = get_settings()

        # Initialize Supabase client
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()
        if not settings.supabase_url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        supabase = create_client(settings.supabase_url, key)

        # Get metrics
        tracker = PropFirmTracker(supabase, settings)
        metrics = await tracker.get_current_metrics(
            account_name=account_name,
            evaluation_phase=settings.evaluation_phase
        )

        # Save snapshot for historical tracking
        await tracker.save_snapshot(metrics, account_name)

        # Calculate remaining USD before breach
        daily_remaining_usd = metrics.daily_loss_limit_usd - abs(metrics.daily_pnl_total)

        return {
            "status": "ok",
            "account_name": account_name,
            "evaluation_phase": settings.evaluation_phase,
            "metrics": {
                "equity": {
                    "daily_start_balance": metrics.daily_start_balance,
                    "current_equity": metrics.current_equity,
                    "daily_high_water_mark": metrics.daily_high_water_mark,
                },
                "daily_pnl": {
                    "closed": metrics.daily_pnl_closed,
                    "floating": metrics.daily_pnl_floating,
                    "total": metrics.daily_pnl_total,
                },
                "drawdown": {
                    "daily_pct": round(metrics.daily_drawdown_pct, 2),
                    "daily_limit_pct": 5.0,  # FTMO standard
                    "daily_remaining_usd": round(daily_remaining_usd, 2),
                    "trailing_pct": round(metrics.trailing_drawdown_pct, 2),
                    "trailing_limit_pct": metrics.max_drawdown_limit_pct,
                },
                "status": {
                    "daily_loss_breach": metrics.daily_loss_breach,
                    "drawdown_breach": metrics.drawdown_breach,
                    "safe_to_trade": not (metrics.daily_loss_breach or metrics.drawdown_breach),
                    "consistency_ok": metrics.consistency_ok,
                },
                "consistency": {
                    "best_day_pct": round(metrics.consistency_pct, 2),
                    "limit_pct": 40.0,  # FTMO standard
                    "status": (
                        "violated" if metrics.consistency_pct > 40 else
                        "danger" if metrics.consistency_pct > 38 else
                        "warning" if metrics.consistency_pct > 35 else
                        "safe"
                    )
                },
                "days_remaining": metrics.days_remaining,
            }
        }

    except Exception as e:
        logger.error(f"Failed to get prop firm metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_prop_firm_history(
    account_name: str = Query(default="default", description="Account identifier"),
    days: int = Query(default=7, ge=1, le=30, description="Number of days to fetch")
):
    """
    Get historical prop firm metrics snapshots for trend analysis.

    Args:
        account_name: Account identifier
        days: Number of days to fetch (1-30)

    Returns:
        List of historical snapshots with drawdown trends
    """
    try:
        from supabase import create_client
        from src.services.prop_firm_tracker import PropFirmTracker

        settings = get_settings()

        # Initialize Supabase client
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()
        if not settings.supabase_url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        supabase = create_client(settings.supabase_url, key)

        # Get historical snapshots
        tracker = PropFirmTracker(supabase, settings)
        snapshots = tracker.get_historical_snapshots(account_name, days)

        return {
            "status": "ok",
            "account_name": account_name,
            "days": days,
            "snapshots": snapshots,
            "total_count": len(snapshots),
        }

    except Exception as e:
        logger.error(f"Failed to get prop firm history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def perform_daily_reset(
    account_name: str = Query(default="default", description="Account identifier")
):
    """
    Manually trigger daily reset (normally happens automatically at 00:00 server time).

    Creates new daily starting balance snapshot.
    """
    try:
        from supabase import create_client
        from src.services.prop_firm_tracker import PropFirmTracker

        settings = get_settings()

        # Initialize Supabase client
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()
        if not settings.supabase_url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        supabase = create_client(settings.supabase_url, key)

        # Perform reset
        tracker = PropFirmTracker(supabase, settings)
        await tracker.perform_daily_reset(account_name)

        return {
            "status": "ok",
            "message": "Daily reset performed successfully",
            "account_name": account_name,
        }

    except Exception as e:
        logger.error(f"Failed to perform daily reset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consistency")
async def get_consistency_metrics(
    account_name: str = Query(default="default", description="Account identifier")
):
    """
    Get detailed consistency analysis (FTMO 40% rule).

    Returns:
        - Best day profit
        - Total profit
        - Best day percentage
        - Consistency status
        - Daily profit breakdown
    """
    try:
        from supabase import create_client
        from src.services.consistency_analyzer import ConsistencyAnalyzer

        settings = get_settings()

        # Initialize Supabase client
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()
        if not settings.supabase_url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        supabase = create_client(settings.supabase_url, key)

        # Get consistency data
        consistency = ConsistencyAnalyzer(supabase, settings)
        dashboard_data = consistency.get_consistency_dashboard_data(account_name)
        breakdown = consistency.get_daily_profit_breakdown(account_name)

        return {
            "status": "ok",
            "account_name": account_name,
            "consistency": dashboard_data,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"Failed to get consistency metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mtm")
async def get_mtm_realtime(
    account_name: str = Query(default="default", description="Account identifier")
):
    """
    Get real-time Mark-to-Market data for all open positions.

    Returns:
        - Current equity with floating PnL
        - Position-level PnL breakdown
        - At-risk positions (>50% to stop loss)
    """
    try:
        from supabase import create_client
        from src.services.mtm_guardian import MTMGuardian

        settings = get_settings()

        # Initialize Supabase client
        key = (settings.supabase_service_role_key or settings.supabase_key).strip()
        if not settings.supabase_url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        supabase = create_client(settings.supabase_url, key)

        # Get MTM data
        mtm = MTMGuardian(supabase, settings)
        equity_data = mtm.get_real_time_equity(account_name)
        position_summary = mtm.get_position_summary(account_name)
        at_risk = mtm.get_at_risk_positions()

        return {
            "status": "ok",
            "account_name": account_name,
            "equity": equity_data,
            "summary": position_summary,
            "at_risk_positions": at_risk,
        }

    except Exception as e:
        logger.error(f"Failed to get MTM data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
