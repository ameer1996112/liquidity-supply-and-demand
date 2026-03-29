"""
System Config API - Operator-controlled global settings.

Endpoints:
- GET  /api/v1/config/trading-mode  - Get current system trading mode
- POST /api/v1/config/trading-mode  - Set system trading mode (PAPER/LIVE/DRY_RUN)
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
