"""Position Command Center API -- manage open positions + account status."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)

# ── Server-side TTL cache (prevents MetaAPI from being called on every poll) ──
# The dashboard polls /positions/active every 5s and /positions/account every 10s.
# Without caching this floods MetaAPI with HTTP calls. We cache per account_id.

_POSITIONS_TTL = 15  # seconds — fresh enough for live display
_ACCOUNT_TTL = 30    # seconds — balance changes slowly

_cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_timestamp)


def _cached_get_open_positions(adapter) -> list:
    """Return cached open positions; refresh from broker after TTL expires."""
    key = f"{getattr(adapter, 'account_id', 'default')}:positions"
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    result = adapter.get_open_positions()
    _cache[key] = (result, time.monotonic() + _POSITIONS_TTL)
    return result


def _cached_get_account_information(adapter) -> Dict[str, Any]:
    """Return cached account info; refresh from broker after TTL expires."""
    key = f"{getattr(adapter, 'account_id', 'default')}:account"
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    result = adapter.get_account_information()
    _cache[key] = (result, time.monotonic() + _ACCOUNT_TTL)
    return result

router = APIRouter(prefix="/positions", tags=["positions"])

# ── Lazy Supabase client (same pattern as api_risk.py) ──────

from src.adapters.supabase_api import get_api_supabase as _get_supabase, reset_api_supabase, is_supabase_connection_error


def _get_adapter():
    """Get the execution adapter using DB-stored credentials (primary account)."""
    from fastapi import HTTPException
    from src.adapters.execution.meta_api_adapter import MetaApiAdapter
    from src.core.metaapi_credentials import get_primary_credentials
    from config import get_settings

    s = get_settings()
    # get_primary_credentials returns (token, account_id, region) tuple
    token, account_id, region = get_primary_credentials()

    if token and account_id:
        return MetaApiAdapter(token=token, account_id=account_id)

    # Last-resort: try env vars (legacy config)
    env_token = (getattr(s, "meta_api_token", "") or "").strip()
    env_account = (getattr(s, "meta_api_account_id", "") or "").strip()
    if env_token and env_account:
        return MetaApiAdapter(token=env_token, account_id=env_account)

    raise HTTPException(
        status_code=503,
        detail="No active broker account configured. Please add and activate a broker profile.",
    )



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
    # Check for broker_position_id OR broker_order_id (fallback for older records)
    has_broker_link = r.get("broker_position_id") is not None or r.get("broker_order_id") is not None

    if status == "open" and r.get("execution_source") == "metaapi" and has_broker_link:
        return True
    # PENDING / SPIN: signal is queued/awaiting execution — show even without broker_order_id yet
    if status in ("pending", "spin") and not _is_signal_closed(r):
        return True
    # active/executed: already placed on broker, require broker link to confirm live
    if status in ("active", "executed") and not _is_signal_closed(r):
        return has_broker_link
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
    zone_id: Optional[int] = None
    current_price: Optional[float] = None
    live_pnl: Optional[float] = None
    live_pnl_pct: Optional[float] = None  # PnL as % of account
    hold_duration_seconds: int = 0
    created_at: str
    zone_type: Optional[str] = None
    entry_model: Optional[str] = None
    rr_ratio: Optional[float] = None
    is_stale: bool = False  # True if position closed on broker but open in DB
    broker_exists: bool = True  # False if DB position doesn't exist on broker


class ReconciliationInfo(BaseModel):
    db_position_count: int
    broker_position_count: int
    matched_count: int
    stale_in_db: int  # Positions in DB but not on broker
    missing_in_db: int  # Positions on broker but not in DB
    has_mismatches: bool


class ActivePositionsResponse(BaseModel):
    positions: List[ActivePosition]
    count: int
    reconciliation: ReconciliationInfo


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
    """List active positions enriched with live prices, PnL, and broker reconciliation."""
    sb = _get_supabase()
    now = datetime.now(timezone.utc)
    adapter = _get_adapter()

    # Fetch broker positions for reconciliation (cached to reduce MetaAPI calls)
    broker_positions = {}
    try:
        if hasattr(adapter, "get_open_positions"):
            broker_pos_list = _cached_get_open_positions(adapter)
            broker_positions = {pos.get("id"): pos for pos in broker_pos_list}
        elif hasattr(adapter, "get_account_information"):
            account_info = _cached_get_account_information(adapter)
            broker_pos_list = account_info.get("positions", [])
            broker_positions = {pos.get("id"): pos for pos in broker_pos_list}
    except Exception as exc:
        logger.warning("Failed to fetch broker positions for reconciliation: %s", exc)

    # Fetch database positions
    try:
        q = (
            sb.table("trading_signals")
            .select(
                "id, symbol, side, entry, sl, tp, size, broker_order_id, zone_id, "
                "created_at, zone_type, entry_model, rr_ratio, "
                "status, execution_source, broker_position_id, broker_order_id, closed_at, exit_price, pnl"
            )
            .in_("status", ["OPEN", "open", "active", "executed", "PENDING", "pending", "spin", "SPIN"])
        )
        if account_id:
            q = q.eq("account_id", account_id)
        resp = q.execute()
        raw_rows = resp.data or []
        rows = [r for r in raw_rows if _is_signal_open_strict(r)]
    except Exception as exc:
        if is_supabase_connection_error(exc):
            reset_api_supabase()
        logger.error("Failed to fetch active positions: %s", exc)
        rows = []

    # Batch-fetch live prices per unique symbol
    price_cache: Dict[str, tuple] = {}
    if hasattr(adapter, "_get_symbol_price"):
        symbols = {r.get("symbol") for r in rows if r.get("symbol")}
        for sym in symbols:
            try:
                bid, ask = adapter._get_symbol_price(sym)
                price_cache[sym] = (bid, ask)
            except Exception:
                price_cache[sym] = (None, None)

    # Get account balance for PnL % calculation (cached)
    account_balance = 50000.0  # Default
    try:
        if hasattr(adapter, "get_account_information"):
            account_info = _cached_get_account_information(adapter)
            account_balance = float(account_info.get("balance", 50000.0))
    except Exception:
        pass

    # Build positions with reconciliation data
    positions = []
    matched_count = 0
    stale_count = 0

    for r in rows:
        symbol = r.get("symbol", "")
        side = (r.get("side") or "").lower()
        entry = r.get("entry")
        size = float(r.get("size") or 0)
        broker_order_id = r.get("broker_order_id")

        # Check if position exists on broker
        broker_exists = broker_order_id in broker_positions if broker_order_id else False
        is_stale = not broker_exists and broker_order_id is not None

        if broker_exists:
            matched_count += 1
        elif is_stale:
            stale_count += 1

        # Current price from cache
        bid, ask = price_cache.get(symbol, (None, None))
        current_price = bid if side == "buy" else ask if side == "sell" else None

        # Live PnL — SOURCE PRIORITY:
        # 1. Use broker's reported profit directly (exact MetaTrader value, avoids need for contract size math)
        # 2. Fall back to approximate formula for PENDING signals with no broker link yet
        live_pnl = None
        live_pnl_pct = None

        if broker_exists and broker_order_id in broker_positions:
            # ── BEST: use the broker's reported unrealized profit ────────────
            broker_pos = broker_positions[broker_order_id]
            raw_profit = broker_pos.get("profit")
            if raw_profit is not None:
                try:
                    live_pnl = round(float(raw_profit), 2)
                except (TypeError, ValueError):
                    live_pnl = None
        
        if live_pnl is None and current_price is not None and entry is not None and size > 0:
            # ── FALLBACK: estimate with correct forex contract-size math ─────
            # Standard forex lot = 100,000 units. For JPY-quoted pairs price
            # difference is in JPY; divide by current price to convert to USD.
            direction = 1 if side == "buy" else -1
            contract_size = 100_000  # standard lot
            sym_upper = symbol.upper()
            price_diff = (current_price - entry) * direction
            if "JPY" in sym_upper:
                # JPY pairs: P&L in JPY → convert to USD
                live_pnl = round(price_diff * size * contract_size / current_price, 2)
            elif any(x in sym_upper for x in ("XAU", "GOLD")):
                # Gold: 1 lot = 100 oz, price in USD — no conversion needed
                live_pnl = round(price_diff * size * 100, 2)
            elif any(x in sym_upper for x in ("NAS", "US30", "SPX", "DE40", "UK100")):
                # Indices: 1 lot = 1 contract, point value ~$1 per point
                live_pnl = round(price_diff * size, 2)
            else:
                # Standard FX (e.g. EURUSD, GBPUSD): P&L already in USD
                live_pnl = round(price_diff * size * contract_size, 2)

        if live_pnl is not None and account_balance > 0:
            live_pnl_pct = round((live_pnl / account_balance) * 100, 2)

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
                broker_order_id=broker_order_id,
                zone_id=r.get("zone_id"),
                current_price=current_price,
                live_pnl=live_pnl,
                live_pnl_pct=live_pnl_pct,
                hold_duration_seconds=hold_seconds,
                created_at=created_str,
                zone_type=r.get("zone_type"),
                entry_model=r.get("entry_model"),
                rr_ratio=r.get("rr_ratio"),
                is_stale=is_stale,
                broker_exists=broker_exists,
            )
        )

    # Calculate reconciliation info
    db_count = len(positions)
    broker_count = len(broker_positions)
    missing_in_db = max(0, broker_count - matched_count)
    has_mismatches = stale_count > 0 or missing_in_db > 0

    reconciliation = ReconciliationInfo(
        db_position_count=db_count,
        broker_position_count=broker_count,
        matched_count=matched_count,
        stale_in_db=stale_count,
        missing_in_db=missing_in_db,
        has_mismatches=has_mismatches,
    )

    return ActivePositionsResponse(
        positions=positions,
        count=len(positions),
        reconciliation=reconciliation,
    )


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
        update_data = {
            "status": "CLOSED",
            "closed_at": now_iso,
            "exit_type": "MANUAL",
        }
        sb.table("trading_signals").update(update_data).eq("id", signal_id).execute()
        try:
            from src.services.reflection_service import create_reflection_on_close_safe
            merged = {**signal, **update_data}
            create_reflection_on_close_safe(sb, signal_id, merged)
        except Exception:
            pass
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


@router.post("/cleanup-stale")
def cleanup_stale_positions():
    """Automatically close stale positions (closed on broker but not in DB)."""
    sb = _get_supabase()
    adapter = _get_adapter()

    # Fetch broker positions (bypass cache for cleanup — needs fresh data)
    broker_positions = {}
    try:
        if hasattr(adapter, "get_open_positions"):
            broker_pos_list = adapter.get_open_positions()
            broker_positions = {pos.get("id"): pos for pos in broker_pos_list}
            # Refresh cache so subsequent reads benefit
            key = f"{getattr(adapter, 'account_id', 'default')}:positions"
            _cache[key] = (broker_pos_list, time.monotonic() + _POSITIONS_TTL)
        elif hasattr(adapter, "get_account_information"):
            account_info = adapter.get_account_information()
            broker_pos_list = account_info.get("positions", [])
            broker_positions = {pos.get("id"): pos for pos in broker_pos_list}
    except Exception as exc:
        logger.error("Failed to fetch broker positions: %s", exc)
        return {
            "status": "error",
            "message": f"Failed to fetch broker positions: {exc}",
            "closed_count": 0,
        }

    # Find stale positions
    try:
        resp = (
            sb.table("trading_signals")
            .select("id, broker_order_id, symbol, side, status")
            .in_("status", ["OPEN", "open", "active", "executed"])
            .execute()
        )
        db_positions = resp.data or []
    except Exception as exc:
        logger.error("Failed to fetch database positions: %s", exc)
        return {
            "status": "error",
            "message": f"Failed to fetch database positions: {exc}",
            "closed_count": 0,
        }

    # Close stale positions
    closed_ids = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for pos in db_positions:
        broker_order_id = pos.get("broker_order_id")
        if broker_order_id and broker_order_id not in broker_positions:
            # Position exists in DB but not on broker - close it
            signal_id = pos.get("id")
            try:
                sb.table("trading_signals").update({
                    "status": "CLOSED",
                    "closed_at": now_iso,
                    "exit_type": "STALE_CLEANUP",
                }).eq("id", signal_id).execute()

                closed_ids.append(signal_id)
                logger.info(
                    f"Auto-closed stale position: ID {signal_id} "
                    f"({pos.get('symbol')} {pos.get('side')})"
                )
            except Exception as exc:
                logger.error(f"Failed to close stale position {signal_id}: {exc}")

    return {
        "status": "ok",
        "message": f"Closed {len(closed_ids)} stale positions",
        "closed_count": len(closed_ids),
        "closed_ids": closed_ids,
    }


@router.post("/backfill-pnl")
def backfill_missing_pnl(days: int = Query(default=90, ge=1, le=365)):
    """
    Backfill actual broker PnL for CLOSED trades that have pnl_usd=null.

    Iterates through recently closed signals with no PnL, fetches their
    deal history from MetaAPI by broker_order_id, and writes the real P&L.
    """
    sb = _get_supabase()
    adapter = _get_adapter()

    if not hasattr(adapter, "get_deals_by_position"):
        return {"status": "error", "message": "Adapter does not support get_deals_by_position"}

    # Find closed signals with no PnL
    cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)).isoformat()
    try:
        resp = sb.table("trading_signals").select(
            "id, broker_order_id, symbol"
        ).in_(
            "status", ["CLOSED", "closed", "executed", "EXECUTED"]
        ).is_("pnl_usd", "null").not_.is_("broker_order_id", "null").gte(
            "created_at", cutoff
        ).execute()
        candidates = resp.data or []
    except Exception as exc:
        return {"status": "error", "message": f"DB query failed: {exc}"}

    updated = 0
    skipped = 0
    errors = 0

    _EXIT_TYPES = {"DEAL_ENTRY_OUT", "DEAL_ENTRY_OUT_BY", "DEAL_ENTRY_INOUT"}

    for sig in candidates:
        broker_order_id = sig.get("broker_order_id")
        signal_id = sig.get("id")
        symbol = str(sig.get("symbol") or "").upper()
        if not broker_order_id:
            skipped += 1
            continue
        try:
            deals = adapter.get_deals_by_position(str(broker_order_id))
            total_pnl = 0.0
            total_commission = 0.0
            total_swap = 0.0
            exit_deals = []
            for deal in deals:
                if str(deal.get("positionId", "")) == str(broker_order_id):
                    total_pnl += float(deal.get("profit", 0) or 0)
                    total_commission += float(deal.get("commission", 0) or 0)
                    total_swap += float(deal.get("swap", 0) or 0)
                    if deal.get("entryType") in _EXIT_TYPES:
                        exit_deals.append(deal)

            if not exit_deals:
                skipped += 1
                logger.debug("backfill-pnl: no exit deals for signal %s (broker_order_id=%s)", signal_id, broker_order_id)
                continue

            net_pnl = total_pnl + total_commission + total_swap
            outcome = "win" if net_pnl > 0 else "loss" if net_pnl < 0 else "breakeven"
            now_iso = datetime.now(timezone.utc).isoformat()

            sb.table("trading_signals").update({
                "pnl_usd": net_pnl,
                "pnl": net_pnl,
                "commission": total_commission,
                "swap": total_swap,
                "outcome": outcome,
                "updated_at": now_iso,
            }).eq("id", signal_id).execute()

            updated += 1
            logger.info("backfill-pnl: signal %s (broker=%s %s) → pnl=%.2f", signal_id, broker_order_id, symbol, net_pnl)
        except Exception as exc:
            errors += 1
            logger.error("backfill-pnl: error for signal %s: %s", signal_id, exc)

    return {
        "status": "ok",
        "candidates": len(candidates),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


# ── Account Status (separate prefix for cleaner API) ────────


@router.get("/account", response_model=AccountStatusResponse)
def get_account_status():
    """Fetch live account information from broker."""
    sb = _get_supabase()
    adapter = _get_adapter()

    # Get account info from broker (cached to reduce MetaAPI calls)
    account_info = {"balance": 0.0, "equity": 0.0}
    if hasattr(adapter, "get_account_information"):
        try:
            account_info = _cached_get_account_information(adapter)
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
        if is_supabase_connection_error(exc):
            reset_api_supabase()
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
