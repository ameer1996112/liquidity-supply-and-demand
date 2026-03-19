"""
Funding API - Prop firm challenge metrics and daily PnL tracking.

Endpoints:
- GET /api/v1/funding/daily-pnl - Get daily PnL breakdown for equity curve
- GET /api/v1/funding/stats - Get funding account statistics

Author: Trinity Engine v3.0
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.adapters.supabase_api import get_api_supabase as _get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/funding", tags=["Funding"])


# ── Response Models ──────────────────────────────────────


class DailyPnL(BaseModel):
    """Daily PnL record for equity curve."""
    date: str
    pnl: float
    balance: float
    trades: int


class DailyPnLResponse(BaseModel):
    """Response model for daily PnL endpoint."""
    daily_pnl: List[DailyPnL]


class FundingStatsResponse(BaseModel):
    """Response model for funding stats endpoint."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win_usd: float
    avg_loss_usd: float
    profit_factor: float
    total_pnl_usd: float
    avg_trade_usd: float
    trading_days: int
    source: str


# ── Helpers ──────────────────────────────────────────────


def _fetch_closed_signals(mode: str, days: int = 0) -> list:
    """Fetch closed signals from Supabase."""
    sb = _get_supabase()

    query = (
        sb.table("trading_signals")
        .select("id, pnl_usd, pnl, created_at, closed_at, status")
        .in_("status", ["closed", "executed", "CLOSED", "EXECUTED"])
        .order("created_at", desc=False)
    )

    if mode and mode != "ALL":
        if mode == "LIVE":
            query = query.or_("run_mode.eq.LIVE,run_mode.is.null")
        else:
            query = query.eq("run_mode", mode)

    if days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = query.gte("created_at", cutoff)

    resp = query.limit(5000).execute()
    raw = resp.data or []

    # Filter out stale positions (zero PnL)
    def _is_truly_closed(s: dict) -> bool:
        pnl = s.get("pnl_usd") or s.get("pnl") or 0
        if pnl == 0:
            return False
        status = (s.get("status") or "").lower()
        if status == "closed":
            return True
        return s.get("pnl_usd") is not None or bool(s.get("closed_at"))

    return [s for s in raw if _is_truly_closed(s)]


# ── Endpoints ────────────────────────────────────────────


@router.get("/daily-pnl", response_model=DailyPnLResponse)
def get_daily_pnl(
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
    starting_balance: float = Query(50000.0, description="Starting balance for equity curve"),
    mode: str = Query("LIVE", description="Trading mode filter"),
):
    """
    Get daily PnL breakdown for equity curve visualization.

    Returns cumulative balance and daily PnL aggregated by date.
    """
    signals = _fetch_closed_signals(mode, days=days)

    # Group by date
    from collections import defaultdict
    daily_map = defaultdict(lambda: {"pnl": 0.0, "trades": 0})

    for sig in signals:
        pnl = float(sig.get("pnl_usd") or sig.get("pnl") or 0)
        dt_str = sig.get("closed_at") or sig.get("created_at", "")
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            date_key = dt.strftime("%Y-%m-%d")
            daily_map[date_key]["pnl"] += pnl
            daily_map[date_key]["trades"] += 1
        except Exception:
            pass

    # Build equity curve
    daily_pnl = []
    balance = starting_balance
    sorted_dates = sorted(daily_map.keys())

    for date_key in sorted_dates:
        data = daily_map[date_key]
        balance += data["pnl"]
        daily_pnl.append(DailyPnL(
            date=date_key,
            pnl=round(data["pnl"], 2),
            balance=round(balance, 2),
            trades=data["trades"],
        ))

    return DailyPnLResponse(daily_pnl=daily_pnl)


@router.get("/stats", response_model=FundingStatsResponse)
def get_funding_stats(
    mode: str = Query("LIVE", description="Trading mode filter"),
):
    """
    Get aggregate funding account statistics.

    Includes win rate, profit factor, average win/loss, and trading days.
    """
    signals = _fetch_closed_signals(mode)

    if not signals:
        return FundingStatsResponse(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win_usd=0.0,
            avg_loss_usd=0.0,
            profit_factor=0.0,
            total_pnl_usd=0.0,
            avg_trade_usd=0.0,
            trading_days=0,
            source="supabase",
        )

    wins = 0
    losses = 0
    total_pnl = 0.0
    total_win_pnl = 0.0
    total_loss_pnl = 0.0
    trading_dates = set()

    for sig in signals:
        pnl = float(sig.get("pnl_usd") or sig.get("pnl") or 0)
        total_pnl += pnl

        if pnl > 0:
            wins += 1
            total_win_pnl += pnl
        elif pnl < 0:
            losses += 1
            total_loss_pnl += abs(pnl)

        # Track trading days
        dt_str = sig.get("closed_at") or sig.get("created_at", "")
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            trading_dates.add(dt.strftime("%Y-%m-%d"))
        except Exception:
            pass

    total_trades = len(signals)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    avg_win = total_win_pnl / wins if wins > 0 else 0.0
    avg_loss = total_loss_pnl / losses if losses > 0 else 0.0
    profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else (total_win_pnl if total_win_pnl > 0 else 0.0)
    avg_trade = total_pnl / total_trades if total_trades > 0 else 0.0

    return FundingStatsResponse(
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        win_rate=round(win_rate, 2),
        avg_win_usd=round(avg_win, 2),
        avg_loss_usd=round(avg_loss, 2),
        profit_factor=round(profit_factor, 2),
        total_pnl_usd=round(total_pnl, 2),
        avg_trade_usd=round(avg_trade, 2),
        trading_days=len(trading_dates),
        source="supabase",
    )
