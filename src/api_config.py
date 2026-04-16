"""
System Config API - Operator-controlled global settings.

Endpoints:
- GET  /api/v1/config/trading-mode        - Get current system trading mode
- POST /api/v1/config/trading-mode        - Set system trading mode (PAPER/LIVE/DRY_RUN)
- GET  /api/v1/config/pine-filters        - Get HTF candle filter settings
- PATCH /api/v1/config/pine-filters       - Update HTF candle filter settings
- GET  /api/v1/config/ai-operating-layer  - Get AI operating layer global config
- PATCH /api/v1/config/ai-operating-layer - Update AI operating layer global config
"""

import logging
from typing import Dict, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.adapters.supabase_api import get_api_supabase as _get_supabase
from src.services.ai_control_plane import ModuleState

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
    htf_candle_period: int  # HTF cycle length in minutes (15, 30, 60)
    block_before_hourly_close: bool
    block_one_candle_liq: bool
    one_candle_liq_min_departure: float
    trading_start_hour: int
    trading_end_hour: int


class PatchHtfFilterRequest(BaseModel):
    htf_candle_filter_enabled: bool | None = None
    htf_candle_block_minutes: int | None = Field(default=None, ge=1, le=59)
    htf_candle_period: int | None = Field(default=None)
    block_before_hourly_close: bool | None = None
    block_one_candle_liq: bool | None = None
    one_candle_liq_min_departure: float | None = Field(default=None, ge=0.0, le=100.0)
    trading_start_hour: int | None = Field(default=None, ge=0, le=23)
    trading_end_hour: int | None = Field(default=None, ge=0, le=23)

class CTraderIntegrationResponse(BaseModel):
    public_api_base_url: str
    ctrader_client_id: str
    has_ctrader_client_secret: bool
    has_ctrader_oauth_state_secret: bool


class PatchCTraderIntegrationRequest(BaseModel):
    public_api_base_url: str | None = None
    ctrader_client_id: str | None = None
    ctrader_client_secret: str | None = Field(default=None, description="Optional: set/rotate secret; omit or empty to keep current")
    ctrader_oauth_state_secret: str | None = Field(default=None, description="Optional: set/rotate state secret; omit or empty to keep current")


class AiOperatingLayerConfigResponse(BaseModel):
    panic_mode: bool
    modules: Dict[str, str]
    provider: "AiOperatingLayerProviderConfig"


class AiOperatingLayerProviderConfig(BaseModel):
    enabled: bool
    base_url: str
    timeout_seconds: float
    retry_count: int


class PatchAiOperatingLayerConfigRequest(BaseModel):
    panic_mode: bool | None = None
    modules: Dict[str, Literal["inherit", "enabled", "disabled"]] | None = None
    provider: AiOperatingLayerProviderConfig | None = None


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
_HTF_PERIOD_KEY = "pine_htf_candle_period"
_OCL_ENABLED_KEY = "pine_block_one_candle_liq"
_OCL_MIN_DEP_KEY = "pine_one_candle_liq_min_departure"
_HOURLY_CLOSE_KEY = "pine_block_before_hourly_close"
_TRADING_START_KEY = "pine_trading_start_hour_local"
_TRADING_END_KEY = "pine_trading_end_hour_local"

_VALID_HTF_PERIODS = (30, 60)


def _invalidate_htf_cache() -> None:
    try:
        import src.worker as _worker
        _worker._htf_filter_cache["loaded_at"] = 0.0
        _worker._one_candle_liq_cache["loaded_at"] = 0.0
        _worker._trading_hours_cache["loaded_at"] = 0.0
    except Exception:
        pass


@router.get("/pine-filters", response_model=HtfFilterResponse)
def get_pine_filters():
    """Return current pine filter settings (HTF candle block + 1-candle liquidity filter)."""
    try:
        sb = _get_supabase()
        from config import get_settings as _get_settings
        _s = _get_settings()
        rows = (
            sb.table("system_config")
            .select("key,value")
            .in_("key", [_HTF_ENABLED_KEY, _HTF_MINUTES_KEY, _HTF_PERIOD_KEY, _HOURLY_CLOSE_KEY, _OCL_ENABLED_KEY, _OCL_MIN_DEP_KEY, _TRADING_START_KEY, _TRADING_END_KEY])
            .execute()
        )
        kv = {r["key"]: r["value"] for r in (rows.data or [])}
        htf_enabled = kv.get(_HTF_ENABLED_KEY, "true").lower() != "false"
        htf_minutes = int(kv.get(_HTF_MINUTES_KEY, "10"))
        htf_period = int(kv.get(_HTF_PERIOD_KEY, "30"))
        if htf_period not in _VALID_HTF_PERIODS:
            htf_period = 30
        hourly_close = kv.get(_HOURLY_CLOSE_KEY, "true").lower() != "false"
        ocl_enabled = kv.get(_OCL_ENABLED_KEY, "true").lower() != "false"
        ocl_min_dep = float(kv.get(_OCL_MIN_DEP_KEY, "60.0"))
        trading_start = int(kv.get(_TRADING_START_KEY, str(getattr(_s, "pine_trading_start_hour_local", 6))))
        trading_end = int(kv.get(_TRADING_END_KEY, str(getattr(_s, "pine_trading_end_hour_local", 22))))
        return {
            "htf_candle_filter_enabled": htf_enabled,
            "htf_candle_block_minutes": htf_minutes,
            "htf_candle_period": htf_period,
            "block_before_hourly_close": hourly_close,
            "block_one_candle_liq": ocl_enabled,
            "one_candle_liq_min_departure": ocl_min_dep,
            "trading_start_hour": trading_start,
            "trading_end_hour": trading_end,
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
        if body.htf_candle_period is not None:
            period = body.htf_candle_period if body.htf_candle_period in _VALID_HTF_PERIODS else 30
            sb.table("system_config").upsert(
                {"key": _HTF_PERIOD_KEY, "value": str(period)},
                on_conflict="key",
            ).execute()
        if body.block_before_hourly_close is not None:
            sb.table("system_config").upsert(
                {"key": _HOURLY_CLOSE_KEY, "value": str(body.block_before_hourly_close).lower()},
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
        if body.trading_start_hour is not None:
            sb.table("system_config").upsert(
                {"key": _TRADING_START_KEY, "value": str(body.trading_start_hour)},
                on_conflict="key",
            ).execute()
        if body.trading_end_hour is not None:
            sb.table("system_config").upsert(
                {"key": _TRADING_END_KEY, "value": str(body.trading_end_hour)},
                on_conflict="key",
            ).execute()
        _invalidate_htf_cache()
        return get_pine_filters()
    except Exception as e:
        logger.error(f"Failed to update pine filter settings: {e}")
        raise HTTPException(status_code=500, detail="Could not update pine filter settings")


# ── Integrations: cTrader Open API ─────────────────────────

_PUBLIC_API_BASE_URL_KEY = "public_api_base_url"
_CTRADER_CLIENT_ID_KEY = "ctrader_client_id"
_CTRADER_CLIENT_SECRET_KEY = "ctrader_client_secret"

_AI_LAYER_PANIC_KEY = "ai_operating_layer_panic_mode"
_AI_LAYER_MODULE_KEYS = {
    "chart_context": "ai_operating_layer_module_chart_context",
    "pine_understanding": "ai_operating_layer_module_pine_understanding",
    "debate_review": "ai_operating_layer_module_debate_review",
    "pretrade_advisory": "ai_operating_layer_module_pretrade_advisory",
    "memory_learning": "ai_operating_layer_module_memory_learning",
    "copilot": "ai_operating_layer_module_copilot",
}
_AI_LAYER_PROVIDER_ENABLED_KEY = "ai_operating_layer_provider_enabled"
_AI_LAYER_PROVIDER_BASE_URL_KEY = "ai_operating_layer_provider_base_url"
_AI_LAYER_PROVIDER_TIMEOUT_KEY = "ai_operating_layer_provider_timeout_seconds"
_AI_LAYER_PROVIDER_RETRY_KEY = "ai_operating_layer_provider_retry_count"


def _read_system_config(keys: list[str]) -> dict[str, str]:
    sb = _get_supabase()
    rows = (
        sb.table("system_config")
        .select("key,value")
        .in_("key", keys)
        .execute()
    )
    return {row["key"]: row["value"] for row in (rows.data or [])}


@router.get("/ai-operating-layer", response_model=AiOperatingLayerConfigResponse)
def get_ai_operating_layer_config():
    try:
        kv = _read_system_config(
            [
                _AI_LAYER_PANIC_KEY,
                *_AI_LAYER_MODULE_KEYS.values(),
                _AI_LAYER_PROVIDER_ENABLED_KEY,
                _AI_LAYER_PROVIDER_BASE_URL_KEY,
                _AI_LAYER_PROVIDER_TIMEOUT_KEY,
                _AI_LAYER_PROVIDER_RETRY_KEY,
            ]
        )
        modules = {
            name: kv.get(key, ModuleState.INHERIT.value)
            for name, key in _AI_LAYER_MODULE_KEYS.items()
        }
        panic_mode = str(kv.get(_AI_LAYER_PANIC_KEY, "false")).lower() == "true"
        provider = {
            "enabled": str(kv.get(_AI_LAYER_PROVIDER_ENABLED_KEY, "false")).lower() == "true",
            "base_url": kv.get(_AI_LAYER_PROVIDER_BASE_URL_KEY, ""),
            "timeout_seconds": float(kv.get(_AI_LAYER_PROVIDER_TIMEOUT_KEY, "1.0")),
            "retry_count": int(kv.get(_AI_LAYER_PROVIDER_RETRY_KEY, "2")),
        }
        return {"panic_mode": panic_mode, "modules": modules, "provider": provider}
    except Exception as e:
        logger.error(f"Failed to fetch AI operating layer config: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch AI operating layer config")


@router.patch("/ai-operating-layer", response_model=AiOperatingLayerConfigResponse)
def patch_ai_operating_layer_config(body: PatchAiOperatingLayerConfigRequest):
    try:
        sb = _get_supabase()
        upserts: list[dict[str, str]] = []
        if body.panic_mode is not None:
            upserts.append(
                {"key": _AI_LAYER_PANIC_KEY, "value": str(body.panic_mode).lower()}
            )
        if body.modules:
            for module_name, module_state in body.modules.items():
                key = _AI_LAYER_MODULE_KEYS.get(module_name)
                if not key:
                    continue
                upserts.append({"key": key, "value": module_state})
        if body.provider:
            upserts.extend(
                [
                    {
                        "key": _AI_LAYER_PROVIDER_ENABLED_KEY,
                        "value": str(body.provider.enabled).lower(),
                    },
                    {
                        "key": _AI_LAYER_PROVIDER_BASE_URL_KEY,
                        "value": body.provider.base_url,
                    },
                    {
                        "key": _AI_LAYER_PROVIDER_TIMEOUT_KEY,
                        "value": str(body.provider.timeout_seconds),
                    },
                    {
                        "key": _AI_LAYER_PROVIDER_RETRY_KEY,
                        "value": str(body.provider.retry_count),
                    },
                ]
            )
        if upserts:
            sb.table("system_config").upsert(upserts, on_conflict="key").execute()
        return get_ai_operating_layer_config()
    except Exception as e:
        logger.error(f"Failed to update AI operating layer config: {e}")
        raise HTTPException(status_code=500, detail="Could not update AI operating layer config")
_CTRADER_STATE_SECRET_KEY = "ctrader_oauth_state_secret"


@router.get("/integrations/ctrader", response_model=CTraderIntegrationResponse)
def get_ctrader_integration():
    """Return current cTrader Open API integration settings (secret values are never returned)."""
    try:
        sb = _get_supabase()
        rows = (
            sb.table("system_config")
            .select("key,value")
            .in_("key", [_PUBLIC_API_BASE_URL_KEY, _CTRADER_CLIENT_ID_KEY, _CTRADER_CLIENT_SECRET_KEY, _CTRADER_STATE_SECRET_KEY])
            .execute()
        )
        kv = {r["key"]: (r.get("value") or "") for r in (rows.data or [])}
        return {
            "public_api_base_url": str(kv.get(_PUBLIC_API_BASE_URL_KEY, "") or ""),
            "ctrader_client_id": str(kv.get(_CTRADER_CLIENT_ID_KEY, "") or ""),
            "has_ctrader_client_secret": bool(str(kv.get(_CTRADER_CLIENT_SECRET_KEY, "") or "").strip()),
            "has_ctrader_oauth_state_secret": bool(str(kv.get(_CTRADER_STATE_SECRET_KEY, "") or "").strip()),
        }
    except Exception as e:
        logger.error(f"Failed to fetch cTrader integration settings: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch cTrader integration settings")


@router.patch("/integrations/ctrader", response_model=CTraderIntegrationResponse)
def patch_ctrader_integration(body: PatchCTraderIntegrationRequest):
    """Update cTrader Open API integration settings. Secrets are write-only."""
    try:
        sb = _get_supabase()
        if body.public_api_base_url is not None:
            sb.table("system_config").upsert(
                {"key": _PUBLIC_API_BASE_URL_KEY, "value": body.public_api_base_url.strip()},
                on_conflict="key",
            ).execute()
        if body.ctrader_client_id is not None:
            sb.table("system_config").upsert(
                {"key": _CTRADER_CLIENT_ID_KEY, "value": body.ctrader_client_id.strip()},
                on_conflict="key",
            ).execute()
        if body.ctrader_client_secret is not None and body.ctrader_client_secret.strip():
            sb.table("system_config").upsert(
                {"key": _CTRADER_CLIENT_SECRET_KEY, "value": body.ctrader_client_secret.strip()},
                on_conflict="key",
            ).execute()
        if body.ctrader_oauth_state_secret is not None and body.ctrader_oauth_state_secret.strip():
            sb.table("system_config").upsert(
                {"key": _CTRADER_STATE_SECRET_KEY, "value": body.ctrader_oauth_state_secret.strip()},
                on_conflict="key",
            ).execute()

        return get_ctrader_integration()
    except Exception as e:
        logger.error(f"Failed to update cTrader integration settings: {e}")
        raise HTTPException(status_code=500, detail="Could not update cTrader integration settings")
