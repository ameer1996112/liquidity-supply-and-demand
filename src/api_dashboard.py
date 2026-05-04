"""Dashboard Summary API — aggregates multi-account PnL, positions, and stats."""

import logging
import json
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Any
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.adapters.supabase_api import get_api_supabase as _get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION_RESULTS_DIR = PROJECT_ROOT / "scripts" / "optimization_results"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _derive_account_type(profile: dict) -> str:
    """Derive account_type string from evaluation_mode + evaluation_phase.
    Mirrors _infer_account_type() in api_broker_profiles.py."""
    if not profile.get("evaluation_mode"):
        return "personal"
    phase = profile.get("evaluation_phase", "phase1")
    if phase == "funded":
        return "funded"
    return "evaluation"


def _signal_pnl(s: dict) -> float:
    """Return broker-actual realized PnL, falling back to legacy pnl field."""
    return s.get("pnl_usd") or s.get("pnl") or 0


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


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default
    return payload if isinstance(payload, dict) else default


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    from src.adapters.supabase_api import is_supabase_connection_error, reset_api_supabase
    sb = _get_supabase()

    profiles: list = []
    signals: list = []
    open_signals: list = []

    # 1. Fetch trading-enabled broker profiles only
    try:
        profiles_resp = sb.table("broker_profiles").select(
            "id, name, evaluation_mode, evaluation_phase, run_mode, connection_status,"
            "is_active, selected_for_trading"
        ).execute()
        profiles = [
            profile for profile in (profiles_resp.data or [])
            if profile.get("is_active", True) and profile.get("selected_for_trading") is True
        ]
    except Exception as exc:
        if is_supabase_connection_error(exc):
            reset_api_supabase()
        logger.warning("dashboard/summary: failed to fetch broker profiles: %s", exc)

    active_profile_ids = {profile["id"] for profile in profiles if profile.get("id") is not None}

    # 2. Fetch closed signals for PnL stats (last 90 days)
    since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    if active_profile_ids:
        try:
            signals_resp = sb.table("trading_signals").select(
                "broker_profile_id, status, pnl, pnl_usd, created_at, closed_at"
            ).gte("created_at", since).in_(
                "status", ["closed", "CLOSED", "executed", "EXECUTED"]
            ).execute()
            signals = [
                signal for signal in (signals_resp.data or [])
                if signal.get("broker_profile_id") in active_profile_ids
            ]
        except Exception as exc:
            if is_supabase_connection_error(exc):
                reset_api_supabase()
            logger.warning("dashboard/summary: failed to fetch signals: %s", exc)

    # 3. Fetch open positions count
    if active_profile_ids:
        try:
            open_resp = sb.table("trading_signals").select(
                "broker_profile_id"
            ).in_("status", ["active", "ACTIVE", "open", "OPEN"]).execute()
            open_signals = [
                signal for signal in (open_resp.data or [])
                if signal.get("broker_profile_id") in active_profile_ids
            ]
        except Exception as exc:
            if is_supabase_connection_error(exc):
                reset_api_supabase()
            logger.warning("dashboard/summary: failed to fetch open positions: %s", exc)

    today_str = date.today().isoformat()

    def _is_today(s: dict) -> bool:
        ts = s.get("closed_at") or s.get("created_at") or ""
        return ts.startswith(today_str)

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

        pnl_total = sum(_signal_pnl(s) for s in acct_signals)
        pnl_today = sum(_signal_pnl(s) for s in acct_signals if _is_today(s))
        trades_today = sum(1 for s in acct_signals if _is_today(s))
        wins = sum(1 for s in acct_signals if _signal_pnl(s) > 0)
        win_rate = round((wins / len(acct_signals) * 100), 1) if acct_signals else 0.0

        total_pnl_today += pnl_today
        total_pnl_all_time += pnl_total
        total_wins += wins
        total_closed += len(acct_signals)
        total_trades_today += trades_today

        account_items.append(AccountSummaryItem(
            id=pid,
            name=profile["name"],
            account_type=_derive_account_type(profile),
            run_mode=profile.get("run_mode", "PAPER"),
            connection_status=profile.get("connection_status", "unknown"),
            pnl_today=round(pnl_today, 2),
            pnl_total=round(pnl_total, 2),
            positions_count=len(acct_open),
            win_rate=win_rate,
            trades_today=trades_today,
        ))

    overall_win_rate = round((total_wins / total_closed * 100), 1) if total_closed else 0.0

    # Max drawdown — best-effort from daily_stats (Table unimplemented)
    max_drawdown_pct = 0.0

    return DashboardSummary(
        total_pnl_today=round(total_pnl_today, 2),
        total_pnl_all_time=round(total_pnl_all_time, 2),
        total_win_rate=overall_win_rate,
        total_active_positions=len(open_signals),
        total_trades_today=total_trades_today,
        max_drawdown_pct=max_drawdown_pct,
        accounts=account_items,
    )


@router.get("/trade-permissions")
async def get_trade_permissions_dashboard() -> dict[str, Any]:
    daily = _read_json(
        OPTIMIZATION_RESULTS_DIR / "daily_trade_permissions.json",
        {"global_decision": "NO_TRADE", "permissions": {}, "blocked": {}, "watch_only": {}},
    )
    approved = _read_json(
        OPTIMIZATION_RESULTS_DIR / "approved_candidates.json",
        {"candidates": {}},
    )
    summary = _read_json(
        OPTIMIZATION_RESULTS_DIR / "pipeline_summary.json",
        {},
    )
    candidates = approved.get("candidates") if isinstance(approved.get("candidates"), dict) else {}
    return {
        "global_decision": daily.get("global_decision", "NO_TRADE"),
        "allowed_today": daily.get("permissions", {}),
        "blocked_today": daily.get("blocked", {}),
        "watch_only": daily.get("watch_only", {}),
        "no_trade_reasons": daily.get("reasons", summary.get("no_trade_reasons", [])),
        "research_approved_candidates": candidates,
        "expiring_candidates": summary.get("expiring_candidates", []),
        "recent_rejects": summary.get("recent_rejects", []),
        "issue_detector": summary.get("issue_detector", {"status": "not_available"}),
        "execution_health": summary.get("execution_health", {"status": "not_available"}),
        "account_risk_buffer": summary.get("account_risk_buffer", {"status": "not_available"}),
    }
