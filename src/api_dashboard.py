"""Dashboard Summary API — aggregates multi-account PnL, positions, and stats."""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.adapters.supabase_api import get_api_supabase as _get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class AccountSummaryItem(BaseModel):
    id: int
    name: str
    account_type: str
    run_mode: str
    connection_status: str
    pnl_today: float
    pnl_total: float
    positions_count: int
    win_rate: float
    trades_today: int


class DashboardSummary(BaseModel):
    total_pnl_today: float
    total_pnl_all_time: float
    total_win_rate: float
    total_active_positions: int
    total_trades_today: int
    max_drawdown_pct: float
    accounts: List[AccountSummaryItem]


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    sb = _get_supabase()

    # 1. Fetch all broker profiles
    profiles_resp = sb.table("broker_profiles").select(
        "id, name, account_type, run_mode, connection_status"
    ).execute()
    profiles = profiles_resp.data or []

    # 2. Fetch closed signals for PnL stats (last 90 days)
    since = (datetime.utcnow() - timedelta(days=90)).isoformat()
    signals_resp = sb.table("trading_signals").select(
        "broker_profile_id, status, pnl, created_at"
    ).gte("created_at", since).in_(
        "status", ["closed", "CLOSED", "executed", "EXECUTED"]
    ).execute()
    signals = signals_resp.data or []

    # 3. Fetch open positions count
    open_resp = sb.table("trading_signals").select(
        "broker_profile_id"
    ).in_("status", ["active", "ACTIVE", "open", "OPEN"]).execute()
    open_signals = open_resp.data or []

    today_str = date.today().isoformat()
    account_items = []
    total_pnl_today = 0.0
    total_pnl_all_time = 0.0
    total_wins = 0
    total_closed = 0
    total_trades_today = 0

    for profile in profiles:
        pid = profile["id"]
        acct_signals = [s for s in signals if s.get("broker_profile_id") == pid]
        acct_open = [s for s in open_signals if s.get("broker_profile_id") == pid]

        pnl_total = sum(s.get("pnl") or 0 for s in acct_signals)
        pnl_today = sum(
            s.get("pnl") or 0 for s in acct_signals
            if (s.get("created_at") or "").startswith(today_str)
        )
        trades_today = sum(
            1 for s in acct_signals
            if (s.get("created_at") or "").startswith(today_str)
        )
        wins = sum(1 for s in acct_signals if (s.get("pnl") or 0) > 0)
        win_rate = round((wins / len(acct_signals) * 100), 1) if acct_signals else 0.0

        total_pnl_today += pnl_today
        total_pnl_all_time += pnl_total
        total_wins += wins
        total_closed += len(acct_signals)
        total_trades_today += trades_today

        account_items.append(AccountSummaryItem(
            id=pid,
            name=profile["name"],
            account_type=profile.get("account_type", "personal"),
            run_mode=profile.get("run_mode", "PAPER"),
            connection_status=profile.get("connection_status", "unknown"),
            pnl_today=round(pnl_today, 2),
            pnl_total=round(pnl_total, 2),
            positions_count=len(acct_open),
            win_rate=win_rate,
            trades_today=trades_today,
        ))

    overall_win_rate = round((total_wins / total_closed * 100), 1) if total_closed else 0.0

    # Max drawdown — best-effort from daily_stats
    max_drawdown_pct = 0.0
    try:
        dd_resp = sb.table("daily_stats").select("max_drawdown_pct").order(
            "date", desc=True
        ).limit(1).execute()
        if dd_resp.data:
            max_drawdown_pct = dd_resp.data[0].get("max_drawdown_pct") or 0.0
    except Exception:
        pass

    return DashboardSummary(
        total_pnl_today=round(total_pnl_today, 2),
        total_pnl_all_time=round(total_pnl_all_time, 2),
        total_win_rate=overall_win_rate,
        total_active_positions=len(open_signals),
        total_trades_today=total_trades_today,
        max_drawdown_pct=round(max_drawdown_pct, 2),
        accounts=account_items,
    )
