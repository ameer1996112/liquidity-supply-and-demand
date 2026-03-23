"""Signal performance analytics for the PM dashboard (ANALYTICS-01, -02, -03)."""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.api_analytics import _fetch_closed_signals, PERIOD_MAP
from src.adapters.supabase_api import get_api_supabase as _get_supabase

router = APIRouter(prefix="/analytics", tags=["analytics-v11"])


@router.get("/signals-perf")
def get_signals_perf(
    period: str = Query("30d", pattern="^(24h|7d|30d|all)$"),
    mode: str = Query("LIVE"),
    account_id: Optional[str] = Query(None),
):
    """
    Per-symbol signal performance: win rate, avg R:R, slippage, long/short P&L breakdown.

    Satisfies:
    - ANALYTICS-01: win rate, avg R:R, total P&L per symbol
    - ANALYTICS-02: avg slippage per signal (entry vs fill_price)
    - ANALYTICS-03: P&L by side (BUY vs SELL) per symbol and overall
    """
    sb = _get_supabase()
    query = (
        sb.table("trading_signals")
        .select(
            "id, symbol, side, entry, pnl_usd, pnl_r, run_mode, "
            "created_at, closed_at, status, fill_price"
        )
        .in_("status", ["closed", "executed", "CLOSED", "EXECUTED"])
        .order("created_at", desc=False)
    )
    if mode and mode != "ALL":
        if mode == "LIVE":
            query = query.or_("run_mode.eq.LIVE,run_mode.is.null")
        else:
            query = query.eq("run_mode", mode)
    if account_id:
        query = query.eq("account_id", account_id)

    td = PERIOD_MAP.get(period)
    if td:
        cutoff = (datetime.now(timezone.utc) - td).isoformat()
        query = query.or_(
            f"closed_at.gte.{cutoff},"
            f"and(closed_at.is.null,created_at.gte.{cutoff})"
        )

    resp = query.limit(5000).execute()
    raw = [s for s in (resp.data or []) if float(s.get("pnl_usd") or 0) != 0]

    # Group by symbol
    groups: Dict[str, list] = defaultdict(list)
    for sig in raw:
        groups[sig.get("symbol") or "UNKNOWN"].append(sig)

    total_long_pnl = total_short_pnl = 0.0
    rows: List[dict] = []

    for sym, trades in sorted(groups.items()):
        wins = losses = 0
        total_pnl = long_pnl = short_pnl = rr_sum = slippage_sum = 0.0
        rr_count = slippage_count = 0

        for t in trades:
            pnl = float(t.get("pnl_usd") or 0)
            side = (t.get("side") or "").upper()
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            if side == "BUY":
                long_pnl += pnl
            else:
                short_pnl += pnl
            if t.get("pnl_r") is not None:
                rr_sum += float(t["pnl_r"])
                rr_count += 1
            # Slippage: |fill_price - entry| if both available
            entry = t.get("entry")
            fill = t.get("fill_price")
            if entry is not None and fill is not None:
                slippage_sum += abs(float(fill) - float(entry))
                slippage_count += 1

        n = len(trades)
        total_long_pnl += long_pnl
        total_short_pnl += short_pnl
        rows.append({
            "symbol": sym,
            "total_trades": n,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / n * 100, 1) if n else 0.0,
            "avg_rr": round(rr_sum / rr_count, 2) if rr_count else 0.0,
            "total_pnl": round(total_pnl, 2),
            "avg_slippage_pts": round(slippage_sum / slippage_count, 5) if slippage_count else 0.0,
            "long_pnl": round(long_pnl, 2),
            "short_pnl": round(short_pnl, 2),
        })

    rows.sort(key=lambda x: x["total_pnl"], reverse=True)

    return {
        "symbols": rows,
        "total_trades": len(raw),
        "long_pnl": round(total_long_pnl, 2),
        "short_pnl": round(total_short_pnl, 2),
        "period": period,
        "mode": mode,
    }
