"""Position Command Center API -- manage open positions + account status."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/positions", tags=["positions"])

# ── Lazy Supabase client (same pattern as api_risk.py) ──────

from src.adapters.supabase_api import get_api_supabase as _get_supabase


def _get_adapter():
    """Get the execution adapter for the current run mode."""
    from src.adapters.execution.router import get_adapter

    s = get_settings()
    return get_adapter(run_mode=s.run_mode, settings=s)


def _is_signal_closed(r: Dict[str, Any]) -> bool:
    status = str(r.get("status") or "").strip().lower()
    if status == "closed":
        return True
    if status not in ("executed", "open"):
        return False
    if r.get("closed_at") is not None or r.get("exit_price") is not None or r.get("pnl") is not None:
        return True
    return False


def _is_signal_open_strict(r: Dict[str, Any]) -> bool:
    status = str(r.get("status") or "").strip().lower()
    if status == "open" and r.get("execution_source") == "metaapi" and r.get("broker_position_id") is not None:
        return True
    if status in ("active", "pending", "executed") and not _is_signal_closed(r):
        return r.get("broker_position_id") is not None
    return False


# ── Request / Response Models ────────────────────────────────


class ActivePosition(BaseModel):
    id: int
    symbol: str
    side: str
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: float = 0.0
    broker_order_id: Optional[str] = None
    current_price: Optional[float] = None
    live_pnl: Optional[float] = None
    hold_duration_seconds: int = 0
    created_at: str
    zone_type: Optional[str] = None
    entry_model: Optional[str] = None
    rr_ratio: Optional[float] = None


class ActivePositionsResponse(BaseModel):
    positions: List[ActivePosition]
    count: int


class ClosePositionRequest(BaseModel):
    reason: str = Field(default="Manual close from UI")


class ModifySLTPRequest(BaseModel):
    sl: Optional[float] = None
    tp: Optional[float] = None


class PartialCloseRequest(BaseModel):
    close_percent: float = Field(..., ge=1, le=100)
    reason: str = Field(default="Partial close from UI")


class AccountStatusResponse(BaseModel):
    balance: float
    equity: float
    free_margin: float
    margin_used: float
    margin_level_pct: float
    active_positions_count: int


# ── Endpoints ────────────────────────────────────────────────


@router.get("/active", response_model=ActivePositionsResponse)
def get_active_positions(
    account_id: Optional[str] = Query(
        None,
        description=(
            "Filter positions to a specific account (e.g. 'default', 'prop-1'). "
            "Omit to return all accounts."
        ),
    ),
):
    """List active positions enriched with live prices and PnL."""
    sb = _get_supabase()
    now = datetime.now(timezone.utc)

    try:
        q = (
            sb.table("trading_signals")
            .select(
                "id, symbol, side, entry, sl, tp, size, broker_order_id, "
                "created_at, zone_type, entry_model, rr_ratio, "
                "status, execution_source, broker_position_id, closed_at, exit_price, pnl"
            )
            .in_("status", ["OPEN", "open", "active", "executed", "PENDING", "pending"])
        )
        if account_id:
            q = q.eq("account_id", account_id)
        resp = q.execute()
        raw_rows = resp.data or []
        rows = [r for r in raw_rows if _is_signal_open_strict(r)]
    except Exception as exc:
        logger.error("Failed to fetch active positions: %s", exc)
        rows = []

    # Batch-fetch live prices per unique symbol
    price_cache: Dict[str, tuple] = {}
    adapter = _get_adapter()

    if hasattr(adapter, "_get_symbol_price"):
        symbols = {r.get("symbol") for r in rows if r.get("symbol")}
        for sym in symbols:
            try:
                bid, ask = adapter._get_symbol_price(sym)
                price_cache[sym] = (bid, ask)
            except Exception:
                price_cache[sym] = (None, None)

    positions = []
    for r in rows:
        symbol = r.get("symbol", "")
        side = (r.get("side") or "").lower()
        entry = r.get("entry")
        size = float(r.get("size") or 0)

        # Current price from cache
        bid, ask = price_cache.get(symbol, (None, None))
        current_price = bid if side == "buy" else ask if side == "sell" else None

        # Live PnL
        live_pnl = None
        if current_price is not None and entry is not None and size > 0:
            direction = 1 if side == "buy" else -1
            live_pnl = round((current_price - entry) * size * direction, 2)

        # Hold duration
        hold_seconds = 0
        created_str = r.get("created_at", "")
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                hold_seconds = int((now - created).total_seconds())
            except Exception:
                pass

        positions.append(
            ActivePosition(
                id=r.get("id", 0),
                symbol=symbol,
                side=r.get("side", ""),
                entry=entry,
                sl=r.get("sl"),
                tp=r.get("tp"),
                size=size,
                broker_order_id=r.get("broker_order_id"),
                current_price=current_price,
                live_pnl=live_pnl,
                hold_duration_seconds=hold_seconds,
                created_at=created_str,
                zone_type=r.get("zone_type"),
                entry_model=r.get("entry_model"),
                rr_ratio=r.get("rr_ratio"),
            )
        )

    return ActivePositionsResponse(positions=positions, count=len(positions))


@router.post("/{signal_id}/close")
def close_position(signal_id: int, body: ClosePositionRequest):
    """Manually close a position via the broker and update DB."""
    sb = _get_supabase()

    # Fetch the signal
    try:
        resp = (
            sb.table("trading_signals")
            .select("*")
            .eq("id", signal_id)
            .in_("status", ["OPEN", "active", "executed"])
            .single()
            .execute()
        )
        signal = resp.data
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Position not found: {exc}")

    if not signal:
        raise HTTPException(status_code=404, detail="Position not found or already closed")

    adapter = _get_adapter()

    # Build close request
    from src.adapters.execution.interfaces import CloseRequest

    close_req = CloseRequest(
        client_order_id=f"manual-close-{signal_id}",
        signal_id=signal_id,
        broker_order_id=signal.get("broker_order_id"),
        symbol=signal.get("symbol", ""),
        side=signal.get("side", ""),
        size=float(signal.get("size") or 0),
    )

    exec_result = adapter.close_order(close_req)

    # Update DB regardless of broker result (manual close = intent to close)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("trading_signals").update(
            {
                "status": "CLOSED",
                "closed_at": now_iso,
                "exit_type": "MANUAL",
            }
        ).eq("id", signal_id).execute()
    except Exception as exc:
        logger.error("Failed to update signal %s after close: %s", signal_id, exc)

    # Audit log
    try:
        from src.services.trade_events import log_event

        log_event(
            signal_id, "manual_close", "api",
            {"reason": body.reason, "broker_status": exec_result.status},
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "signal_id": signal_id,
        "broker_status": exec_result.status,
        "message": exec_result.message,
    }


@router.patch("/{signal_id}/sl-tp")
def modify_sl_tp(signal_id: int, body: ModifySLTPRequest):
    """Modify SL/TP on an open position."""
    if body.sl is None and body.tp is None:
        raise HTTPException(status_code=400, detail="Provide at least sl or tp")

    sb = _get_supabase()

    try:
        resp = (
            sb.table("trading_signals")
            .select("id, broker_order_id, sl, tp")
            .eq("id", signal_id)
            .in_("status", ["OPEN", "active", "executed"])
            .single()
            .execute()
        )
        signal = resp.data
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Position not found: {exc}")

    if not signal:
        raise HTTPException(status_code=404, detail="Position not found or already closed")

    adapter = _get_adapter()
    broker_result = None

    # Try broker modification if adapter supports it
    if hasattr(adapter, "modify_position") and signal.get("broker_order_id"):
        broker_result = adapter.modify_position(
            position_id=signal["broker_order_id"],
            sl=body.sl,
            tp=body.tp,
        )
        if broker_result.status == "failed":
            raise HTTPException(
                status_code=502,
                detail=f"Broker modification failed: {broker_result.message}",
            )

    # Update DB
    update_data: Dict[str, Any] = {}
    if body.sl is not None:
        update_data["sl"] = body.sl
    if body.tp is not None:
        update_data["tp"] = body.tp

    try:
        sb.table("trading_signals").update(update_data).eq("id", signal_id).execute()
    except Exception as exc:
        logger.error("Failed to update SL/TP for signal %s: %s", signal_id, exc)

    try:
        from src.services.trade_events import log_event

        log_event(
            signal_id, "sl_tp_modified", "api",
            {"new_sl": body.sl, "new_tp": body.tp},
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "signal_id": signal_id,
        "new_sl": body.sl or signal.get("sl"),
        "new_tp": body.tp or signal.get("tp"),
        "broker_modified": broker_result is not None,
    }


@router.post("/{signal_id}/partial-close")
def partial_close(signal_id: int, body: PartialCloseRequest):
    """Partially close a position (close N% of volume)."""
    sb = _get_supabase()

    try:
        resp = (
            sb.table("trading_signals")
            .select("*")
            .eq("id", signal_id)
            .in_("status", ["OPEN", "active", "executed"])
            .single()
            .execute()
        )
        signal = resp.data
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Position not found: {exc}")

    if not signal:
        raise HTTPException(status_code=404, detail="Position not found or already closed")

    full_size = float(signal.get("size") or 0)
    if full_size <= 0:
        raise HTTPException(status_code=400, detail="Position has no size")

    partial_volume = round(full_size * (body.close_percent / 100), 2)
    remaining = round(full_size - partial_volume, 2)

    if partial_volume <= 0:
        raise HTTPException(status_code=400, detail="Partial volume too small")

    adapter = _get_adapter()

    # Submit partial close to broker
    from src.adapters.execution.interfaces import CloseRequest

    close_req = CloseRequest(
        client_order_id=f"partial-close-{signal_id}",
        signal_id=signal_id,
        broker_order_id=signal.get("broker_order_id"),
        symbol=signal.get("symbol", ""),
        side=signal.get("side", ""),
        size=partial_volume,
    )

    exec_result = adapter.close_order(close_req)

    # Update DB: reduce size or close if fully closed
    try:
        if remaining <= 0:
            sb.table("trading_signals").update(
                {
                    "status": "CLOSED",
                    "closed_at": datetime.now(timezone.utc).isoformat(),
                    "size": 0,
                    "exit_type": "MANUAL",
                }
            ).eq("id", signal_id).execute()
        else:
            sb.table("trading_signals").update(
                {"size": remaining}
            ).eq("id", signal_id).execute()
    except Exception as exc:
        logger.error("Failed to update size for signal %s: %s", signal_id, exc)

    try:
        from src.services.trade_events import log_event

        log_event(
            signal_id, "partial_close", "api",
            {
                "close_percent": body.close_percent,
                "closed_volume": partial_volume,
                "remaining_volume": remaining,
                "reason": body.reason,
            },
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "signal_id": signal_id,
        "closed_volume": partial_volume,
        "remaining_volume": remaining,
        "broker_status": exec_result.status,
    }


# ── Account Status (separate prefix for cleaner API) ────────


@router.get("/account", response_model=AccountStatusResponse)
def get_account_status():
    """Fetch live account information from broker."""
    sb = _get_supabase()
    adapter = _get_adapter()

    # Get account info from broker
    account_info = {"balance": 0.0, "equity": 0.0}
    if hasattr(adapter, "get_account_information"):
        try:
            account_info = adapter.get_account_information()
        except Exception as exc:
            logger.error("Failed to fetch account info: %s", exc)

    balance = float(account_info.get("balance", 0))
    equity = float(account_info.get("equity", 0))
    margin = float(account_info.get("margin", 0))
    free_margin = float(account_info.get("freeMargin", equity - margin))
    margin_level = float(account_info.get("marginLevel", 0))

    # Count active positions
    try:
        resp = (
            sb.table("trading_signals")
            .select("status, execution_source, broker_position_id, closed_at, exit_price, pnl")
            .in_("status", ["OPEN", "open", "active", "executed", "PENDING", "pending"])
            .execute()
        )
        active_count = sum(1 for r in (resp.data or []) if _is_signal_open_strict(r))
    except Exception as exc:
        logger.error("Failed to fetch count of active positions: %s", exc)
        active_count = 0

    return AccountStatusResponse(
        balance=round(balance, 2),
        equity=round(equity, 2),
        free_margin=round(free_margin, 2),
        margin_used=round(margin, 2),
        margin_level_pct=round(margin_level, 2),
        active_positions_count=active_count,
    )
