"""
System Config API - Operator-controlled global settings.

Endpoints:
- GET  /api/v1/config/trading-mode  - Get current system trading mode
- POST /api/v1/config/trading-mode  - Set system trading mode (PAPER/LIVE/DRY_RUN)
- GET  /api/v1/config/pine-filters  - Get HTF candle filter settings
- PATCH /api/v1/config/pine-filters - Update HTF candle filter settings
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.adapters.supabase_api import get_api_supabase as _get_supabase

logger = logging.getLogger(__name__)


def _invalidate_mode_cache() -> None:
    """Force the api.py in-memory cache to reload on next signal."""
    try:
        import src.api as _api
        _api._system_mode_cache["loaded_at"] = 0.0
    except Exception:
        pass  # api module may not be loaded in test context

router = APIRouter(prefix="/api/v1/config", tags=["Config"])

VALID_MODES = ("PAPER", "LIVE", "DRY_RUN")


# ── Models ────────────────────────────────────────────────


class TradingModeResponse(BaseModel):
    trading_mode: str


class SetTradingModeRequest(BaseModel):
    mode: Literal["PAPER", "LIVE", "DRY_RUN"]


class HtfFilterResponse(BaseModel):
    htf_candle_filter_enabled: bool
    htf_candle_block_minutes: int
    block_one_candle_liq: bool
    one_candle_liq_min_departure: float


class PatchHtfFilterRequest(BaseModel):
    htf_candle_filter_enabled: bool | None = None
    htf_candle_block_minutes: int | None = Field(default=None, ge=1, le=14)
    block_one_candle_liq: bool | None = None
    one_candle_liq_min_departure: float | None = Field(default=None, ge=0.0, le=100.0)


# ── Endpoints ─────────────────────────────────────────────


@router.get("/trading-mode", response_model=TradingModeResponse)
def get_trading_mode():
    """Return the current system-level trading mode."""
    try:
        sb = _get_supabase()
        result = (
            sb.table("system_config")
            .select("value")
            .eq("key", "trading_mode")
            .single()
            .execute()
        )
        mode = result.data["value"] if result.data else "PAPER"
        return {"trading_mode": mode}
    except Exception as e:
        logger.error(f"Failed to fetch trading mode: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch trading mode")


@router.post("/trading-mode", response_model=TradingModeResponse)
def set_trading_mode(body: SetTradingModeRequest):
    """Set the system-level trading mode. Affects all incoming signals immediately."""
    try:
        sb = _get_supabase()
        sb.table("system_config").upsert(
            {"key": "trading_mode", "value": body.mode},
            on_conflict="key",
        ).execute()
        _invalidate_mode_cache()
        logger.info(f"System trading mode set to: {body.mode}")
        return {"trading_mode": body.mode}
    except Exception as e:
        logger.error(f"Failed to set trading mode: {e}")
        raise HTTPException(status_code=500, detail="Could not update trading mode")


# ── HTF Candle Filter ──────────────────────────────────────

_HTF_ENABLED_KEY = "pine_htf_candle_filter_enabled"
_HTF_MINUTES_KEY = "pine_htf_candle_block_minutes"
_OCL_ENABLED_KEY = "pine_block_one_candle_liq"
_OCL_MIN_DEP_KEY = "pine_one_candle_liq_min_departure"


def _invalidate_htf_cache() -> None:
    try:
        import src.worker as _worker
        _worker._htf_filter_cache["loaded_at"] = 0.0
        _worker._one_candle_liq_cache["loaded_at"] = 0.0
    except Exception:
        pass


@router.get("/pine-filters", response_model=HtfFilterResponse)
def get_pine_filters():
    """Return current pine filter settings (HTF candle block + 1-candle liquidity filter)."""
    try:
        sb = _get_supabase()
        rows = (
            sb.table("system_config")
            .select("key,value")
            .in_("key", [_HTF_ENABLED_KEY, _HTF_MINUTES_KEY, _OCL_ENABLED_KEY, _OCL_MIN_DEP_KEY])
            .execute()
        )
        kv = {r["key"]: r["value"] for r in (rows.data or [])}
        htf_enabled = kv.get(_HTF_ENABLED_KEY, "true").lower() != "false"
        htf_minutes = int(kv.get(_HTF_MINUTES_KEY, "10"))
        ocl_enabled = kv.get(_OCL_ENABLED_KEY, "true").lower() != "false"
        ocl_min_dep = float(kv.get(_OCL_MIN_DEP_KEY, "60.0"))
        return {
            "htf_candle_filter_enabled": htf_enabled,
            "htf_candle_block_minutes": htf_minutes,
            "block_one_candle_liq": ocl_enabled,
            "one_candle_liq_min_departure": ocl_min_dep,
        }
    except Exception as e:
        logger.error(f"Failed to fetch pine filter settings: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch pine filter settings")


@router.patch("/pine-filters", response_model=HtfFilterResponse)
def patch_pine_filters(body: PatchHtfFilterRequest):
    """Update pine filter settings. Only provided fields are updated."""
    try:
        sb = _get_supabase()
        if body.htf_candle_filter_enabled is not None:
            sb.table("system_config").upsert(
                {"key": _HTF_ENABLED_KEY, "value": str(body.htf_candle_filter_enabled).lower()},
                on_conflict="key",
            ).execute()
        if body.htf_candle_block_minutes is not None:
            sb.table("system_config").upsert(
                {"key": _HTF_MINUTES_KEY, "value": str(body.htf_candle_block_minutes)},
                on_conflict="key",
            ).execute()
        if body.block_one_candle_liq is not None:
            sb.table("system_config").upsert(
                {"key": _OCL_ENABLED_KEY, "value": str(body.block_one_candle_liq).lower()},
                on_conflict="key",
            ).execute()
        if body.one_candle_liq_min_departure is not None:
            sb.table("system_config").upsert(
                {"key": _OCL_MIN_DEP_KEY, "value": str(body.one_candle_liq_min_departure)},
                on_conflict="key",
            ).execute()
        _invalidate_htf_cache()
        return get_pine_filters()
    except Exception as e:
        logger.error(f"Failed to update pine filter settings: {e}")
        raise HTTPException(status_code=500, detail="Could not update pine filter settings")
