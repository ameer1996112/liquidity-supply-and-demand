"""Analytics API -- server-side aggregation for performance intelligence."""

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# ── Shared Supabase client with auto-reconnect ──────────────────

from src.adapters.supabase_api import get_api_supabase as _get_supabase


# ── Helpers ──────────────────────────────────────────────────

PERIOD_MAP = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _fetch_closed_signals(
    period: str,
    mode: Optional[str],
    account_id: Optional[str] = None,
) -> list:
    """Fetch closed signals from Supabase with optional period/mode/account filters."""
    sb = _get_supabase()

    query = (
        sb.table("trading_signals")
        .select(
            "id, symbol, side, entry, sl, tp, size, pnl_usd, pnl_r, outcome, "
            "zone_type, entry_model, ai_confidence, rr_ratio, "
            "created_at, closed_at, status"
        )
        .eq("status", "closed")
        .order("created_at", desc=False)
    )

    if mode and mode != "ALL":
        query = query.eq("run_mode", mode)

    # Sprint 2.3: per-account filtering.  Omitting account_id (or passing None)
    # returns all accounts — identical to pre-Sprint-2.3 behaviour.
    if account_id:
        query = query.eq("account_id", account_id)

    td = PERIOD_MAP.get(period)
    if td:
        cutoff = (datetime.now(timezone.utc) - td).isoformat()
        query = query.gte("created_at", cutoff)

    resp = query.limit(5000).execute()
    return resp.data or []


def _bucket(signals: list, key_fn) -> Dict[str, Dict[str, Any]]:
    """Group signals into buckets and compute stats per bucket."""
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0}
    )
    for s in signals:
        k = key_fn(s)
        if k is None:
            continue
        b = buckets[k]
        pnl = float(s.get("pnl_usd") or 0)
        b["count"] += 1
        b["pnl"] += pnl
        if pnl > 0:
            b["wins"] += 1
        elif pnl < 0:
            b["losses"] += 1

    # Compute win_rate and round pnl
    result = {}
    for k, b in buckets.items():
        b["win_rate"] = round(b["wins"] / b["count"] * 100, 1) if b["count"] > 0 else 0
        b["pnl"] = round(b["pnl"], 2)
        result[k] = b
    return result


# ── Response Models ──────────────────────────────────────────


class BucketStats(BaseModel):
    count: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    win_rate: float = 0.0


class BreakdownResponse(BaseModel):
    pnl_by_hour: Dict[str, BucketStats]
    pnl_by_day_of_week: Dict[str, BucketStats]
    pnl_by_symbol: Dict[str, BucketStats]
    pnl_by_zone_type: Dict[str, BucketStats]
    pnl_by_entry_model: Dict[str, BucketStats]
    win_rate_by_ai_confidence: Dict[str, BucketStats]


class Streak(BaseModel):
    type: str  # "win" or "loss"
    count: int
    pnl: float
    start_date: str
    end_date: str


class StreaksResponse(BaseModel):
    max_win_streak: int
    max_loss_streak: int
    current_streak: int
    current_streak_type: str
    streaks: List[Streak]


class DrawdownPoint(BaseModel):
    date: str
    equity: float
    drawdown_pct: float
    peak: float


class DrawdownResponse(BaseModel):
    data: List[DrawdownPoint]
    max_drawdown_pct: float
    max_drawdown_amount: float


class SummaryResponse(BaseModel):
    sharpe_ratio: float
    sortino_ratio: float
    avg_hold_time_hours: float
    total_r_won: float
    total_r_lost: float
    expectancy: float
    total_trades: int


# ── Endpoints ────────────────────────────────────────────────


@router.get("/breakdown", response_model=BreakdownResponse)
def get_breakdown(
    period: str = Query("7d", pattern="^(24h|7d|30d|all)$"),
    mode: str = Query("LIVE"),
    account_id: Optional[str] = Query(None, description="Filter to a specific account_id"),
):
    """Multi-dimensional performance breakdown."""
    signals = _fetch_closed_signals(period, mode, account_id=account_id)

    def hour_key(s):
        try:
            dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
            return f"{dt.hour:02d}:00"
        except Exception:
            return None

    def dow_key(s):
        try:
            dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
            return DAY_NAMES[dt.weekday()]
        except Exception:
            return None

    def symbol_key(s):
        return s.get("symbol")

    def zone_type_key(s):
        return s.get("zone_type") or "unknown"

    def entry_model_key(s):
        return s.get("entry_model") or "unknown"

    def confidence_key(s):
        conf = s.get("ai_confidence")
        if conf is None:
            return "unknown"
        c = float(conf)
        if c >= 0.9:
            return "0.9-1.0"
        if c >= 0.8:
            return "0.8-0.9"
        if c >= 0.7:
            return "0.7-0.8"
        if c >= 0.6:
            return "0.6-0.7"
        return "0.5-0.6"

    return BreakdownResponse(
        pnl_by_hour=_bucket(signals, hour_key),
        pnl_by_day_of_week=_bucket(signals, dow_key),
        pnl_by_symbol=_bucket(signals, symbol_key),
        pnl_by_zone_type=_bucket(signals, zone_type_key),
        pnl_by_entry_model=_bucket(signals, entry_model_key),
        win_rate_by_ai_confidence=_bucket(signals, confidence_key),
    )


@router.get("/streaks", response_model=StreaksResponse)
def get_streaks(
    mode: str = Query("LIVE"),
    account_id: Optional[str] = Query(None, description="Filter to a specific account_id"),
):
    """Consecutive win/loss streaks analysis."""
    signals = _fetch_closed_signals("all", mode, account_id=account_id)

    streaks: List[Streak] = []
    max_win = 0
    max_loss = 0
    current_type = ""
    current_count = 0
    current_pnl = 0.0
    streak_start = ""

    for s in signals:
        pnl = float(s.get("pnl_usd") or 0)
        stype = "win" if pnl > 0 else "loss" if pnl < 0 else ""
        if not stype:
            continue

        dt_str = s.get("created_at", "")

        if stype == current_type:
            current_count += 1
            current_pnl += pnl
        else:
            # Save previous streak if any
            if current_count > 0:
                streaks.append(
                    Streak(
                        type=current_type,
                        count=current_count,
                        pnl=round(current_pnl, 2),
                        start_date=streak_start,
                        end_date=dt_str,
                    )
                )
                if current_type == "win":
                    max_win = max(max_win, current_count)
                else:
                    max_loss = max(max_loss, current_count)

            current_type = stype
            current_count = 1
            current_pnl = pnl
            streak_start = dt_str

    # Final streak
    if current_count > 0:
        streaks.append(
            Streak(
                type=current_type,
                count=current_count,
                pnl=round(current_pnl, 2),
                start_date=streak_start,
                end_date=signals[-1].get("created_at", "") if signals else "",
            )
        )
        if current_type == "win":
            max_win = max(max_win, current_count)
        else:
            max_loss = max(max_loss, current_count)

    return StreaksResponse(
        max_win_streak=max_win,
        max_loss_streak=max_loss,
        current_streak=current_count,
        current_streak_type=current_type or "none",
        streaks=streaks[-50:],  # Last 50 streaks
    )


@router.get("/drawdown", response_model=DrawdownResponse)
def get_drawdown(
    mode: str = Query("LIVE"),
    account_id: Optional[str] = Query(None, description="Filter to a specific account_id"),
):
    """Equity curve with underwater (drawdown) plot data."""
    s = get_settings()
    signals = _fetch_closed_signals("all", mode, account_id=account_id)

    equity = s.account_balance
    peak = equity
    max_dd_pct = 0.0
    max_dd_amt = 0.0
    data = []

    for sig in signals:
        pnl = float(sig.get("pnl_usd") or 0)
        equity += pnl
        peak = max(peak, equity)
        dd_amt = peak - equity
        dd_pct = (dd_amt / peak * 100) if peak > 0 else 0

        max_dd_pct = max(max_dd_pct, dd_pct)
        max_dd_amt = max(max_dd_amt, dd_amt)

        dt_str = sig.get("closed_at") or sig.get("created_at", "")
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            date_label = dt.strftime("%b %d")
        except Exception:
            date_label = dt_str[:10]

        data.append(
            DrawdownPoint(
                date=date_label,
                equity=round(equity, 2),
                drawdown_pct=round(-dd_pct, 2),  # Negative for underwater
                peak=round(peak, 2),
            )
        )

    return DrawdownResponse(
        data=data,
        max_drawdown_pct=round(max_dd_pct, 2),
        max_drawdown_amount=round(max_dd_amt, 2),
    )


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    mode: str = Query("LIVE"),
    account_id: Optional[str] = Query(None, description="Filter to a specific account_id"),
):
    """Rolling performance metrics: Sharpe, Sortino, expectancy."""
    s = get_settings()
    signals = _fetch_closed_signals("all", mode, account_id=account_id)

    if not signals:
        return SummaryResponse(
            sharpe_ratio=0, sortino_ratio=0, avg_hold_time_hours=0,
            total_r_won=0, total_r_lost=0, expectancy=0, total_trades=0,
        )

    returns = []
    neg_returns = []
    total_r_won = 0.0
    total_r_lost = 0.0
    hold_times = []
    wins = 0
    total_win_pnl = 0.0
    total_loss_pnl = 0.0

    for sig in signals:
        pnl = float(sig.get("pnl_usd") or 0)
        pnl_r = float(sig.get("pnl_r") or 0)
        ret = pnl / s.account_balance if s.account_balance > 0 else 0
        returns.append(ret)
        if ret < 0:
            neg_returns.append(ret)

        if pnl_r > 0:
            total_r_won += pnl_r
        elif pnl_r < 0:
            total_r_lost += abs(pnl_r)

        if pnl > 0:
            wins += 1
            total_win_pnl += pnl
        elif pnl < 0:
            total_loss_pnl += abs(pnl)

        # Hold time
        created = sig.get("created_at", "")
        closed = sig.get("closed_at", "")
        if created and closed:
            try:
                c1 = datetime.fromisoformat(created.replace("Z", "+00:00"))
                c2 = datetime.fromisoformat(closed.replace("Z", "+00:00"))
                hold_times.append((c2 - c1).total_seconds() / 3600)
            except Exception:
                pass

    n = len(returns)
    mean_ret = sum(returns) / n if n > 0 else 0
    std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / n) if n > 1 else 0
    std_neg = (
        math.sqrt(sum(r ** 2 for r in neg_returns) / len(neg_returns))
        if neg_returns
        else 0
    )

    sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0
    sortino = (mean_ret / std_neg * math.sqrt(252)) if std_neg > 0 else 0

    win_rate = wins / n if n > 0 else 0
    loss_rate = 1 - win_rate
    avg_win = total_win_pnl / wins if wins > 0 else 0
    avg_loss = total_loss_pnl / (n - wins) if (n - wins) > 0 else 0
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

    avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0

    return SummaryResponse(
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        avg_hold_time_hours=round(avg_hold, 1),
        total_r_won=round(total_r_won, 2),
        total_r_lost=round(total_r_lost, 2),
        expectancy=round(expectancy, 2),
        total_trades=n,
    )
