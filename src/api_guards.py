"""
Guards Configuration API
Exposes guard rail toggles and thresholds for frontend management.

Endpoints:
    GET  /api/v1/guards/config        — All guards with current values & rejection stats
    PATCH /api/v1/guards/config/{id}  — Update a guard's enabled state or thresholds
    GET  /api/v1/guards/rejections    — Recent guard rejections (last 7 days)

Author: Trinity Engine v3.1
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.dynamic_config import get_dynamic_setting, update_setting
from src.core.guard_rails.guard_registry import (
    GROUP_LABELS,
    TIER_LABELS,
    get_all_guards,
    get_guard,
    GuardDefinition,
    ThresholdDef,
)
from src.services.trade_events import log_event
from src.services.liquidity_scorer import get_dynamic_threshold_info
from src.adapters.supabase_api import get_api_supabase as get_supabase
from src.core.broker_profiles import get_active_profiles
from src.services.account_guard_settings import (
    get_effective_account_guard_value,
    get_effective_account_threshold_value,
    load_account_guard_overrides,
    update_account_guard_override,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/guards", tags=["guards"])

_SYSTEM_CONFIG_KEYS = {
    "pine_htf_candle_filter_enabled",
    "pine_htf_candle_block_minutes",
    "pine_block_before_hourly_close",
    "pine_block_one_candle_liq",
    "pine_one_candle_liq_min_departure",
}


# ══════════════════════════════════════════════════════════
# RESPONSE MODELS
# ══════════════════════════════════════════════════════════


class ThresholdResponse(BaseModel):
    setting_key: str
    name: str
    value_type: str
    current_value: Any
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""


class DynamicThresholdInfo(BaseModel):
    enabled: bool = False
    base: float = 0
    min_val: float = 0
    max_val: float = 0
    description: str = ""


class GuardResponse(BaseModel):
    guard_id: str
    name: str
    description: str
    user_description: str
    tier: str
    group: str
    group_label: str
    value_type: str
    enabled: Any  # bool for toggles, numeric for threshold-type guards
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""
    thresholds: list[ThresholdResponse] = []
    rejection_count_7d: int = 0
    last_rejection_reason: Optional[str] = None
    dynamic_threshold: Optional[DynamicThresholdInfo] = None
    scope: str = "global"


class GuardsConfigResponse(BaseModel):
    groups: dict[str, list[GuardResponse]]
    group_labels: dict[str, str]
    tier_labels: dict[str, str]
    total_rejections_7d: int = 0
    total_signals_7d: int = 0


class GuardUpdateRequest(BaseModel):
    value: Any = Field(description="New value for the guard's primary setting")
    thresholds: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional threshold updates: {setting_key: new_value}",
    )
    change_reason: str = Field(
        default="",
        description="Reason for the change (required for critical guards)",
    )


class GuardUpdateResponse(BaseModel):
    guard_id: str
    setting_key: str
    old_value: Any
    new_value: Any
    confirmed_value: Any  # Read-back after write
    threshold_updates: dict[str, Any] = {}


class RejectionEntry(BaseModel):
    guard_name: str
    symbol: str
    reason: str
    timestamp: str


class GuardAccountEntry(BaseModel):
    id: str
    name: str
    run_mode: str


class GuardAccountsResponse(BaseModel):
    accounts: list[GuardAccountEntry]


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════


def _get_current_value(guard: GuardDefinition) -> Any:
    """Read the current effective value for a guard from DB/env/default."""
    if guard.setting_key in _SYSTEM_CONFIG_KEYS:
        return _get_system_config_value(guard.setting_key, guard.default)
    return get_dynamic_setting(guard.setting_key, guard.default)


def _get_account_current_value(guard: GuardDefinition, account_id: str, overrides: dict[str, Any]) -> Any:
    value, _source = get_effective_account_guard_value(
        account_id=account_id,
        setting_key=guard.setting_key,
        global_default=guard.default,
        account_overrides=overrides,
    )
    return value


def _get_threshold_value(t: ThresholdDef) -> Any:
    """Read current value for a threshold setting."""
    if t.setting_key in _SYSTEM_CONFIG_KEYS:
        return _get_system_config_value(t.setting_key, t.default)
    return get_dynamic_setting(t.setting_key, t.default)


def _coerce_system_config_value(raw: Any, default: Any) -> Any:
    """Coerce `system_config.value` string payloads to the expected type."""
    if raw is None:
        return default
    if isinstance(default, bool):
        return str(raw).lower() != "false"
    if isinstance(default, int) and not isinstance(default, bool):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


def _get_system_config_value(setting_key: str, default: Any) -> Any:
    """Read a setting from system_config, falling back to the provided default."""
    try:
        sb = get_supabase()
        result = (
            sb.table("system_config")
            .select("value")
            .eq("key", setting_key)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            return _coerce_system_config_value(rows[0].get("value"), default)
    except Exception as e:
        logger.warning("Failed to read system_config setting '%s': %s", setting_key, e)
    return default


def _write_system_config_value(setting_key: str, value: Any) -> None:
    """Persist a runtime-owned setting to system_config."""
    sb = get_supabase()
    sb.table("system_config").upsert(
        {"key": setting_key, "value": str(value).lower() if isinstance(value, bool) else str(value)},
        on_conflict="key",
    ).execute()


def _invalidate_runtime_guard_caches() -> None:
    """Force worker-side pine filter caches to refresh immediately."""
    try:
        import src.worker as _worker

        _worker._htf_filter_cache["loaded_at"] = 0.0
        _worker._one_candle_liq_cache["loaded_at"] = 0.0
        _worker._trading_hours_cache["loaded_at"] = 0.0
    except Exception:
        logger.debug("Worker cache invalidation skipped", exc_info=True)


def _get_account_threshold_value(t: ThresholdDef, account_id: str, overrides: dict[str, Any]) -> Any:
    value, _source = get_effective_account_threshold_value(
        account_id=account_id,
        setting_key=t.setting_key,
        global_default=_get_threshold_value(t),
        account_overrides=overrides,
    )
    return value


def _validate_value(guard: GuardDefinition, value: Any) -> Any:
    """Validate and coerce a guard value. Raises HTTPException on invalid."""
    if guard.value_type == "bool":
        if not isinstance(value, bool):
            raise HTTPException(400, f"Guard '{guard.guard_id}' expects a boolean value")
        return value
    elif guard.value_type == "int":
        try:
            val = int(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Guard '{guard.guard_id}' expects an integer value")
        if guard.min_value is not None and val < guard.min_value:
            raise HTTPException(400, f"Value {val} below minimum {guard.min_value}")
        if guard.max_value is not None and val > guard.max_value:
            raise HTTPException(400, f"Value {val} above maximum {guard.max_value}")
        return val
    elif guard.value_type == "float":
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Guard '{guard.guard_id}' expects a numeric value")
        if guard.min_value is not None and val < guard.min_value:
            raise HTTPException(400, f"Value {val} below minimum {guard.min_value}")
        if guard.max_value is not None and val > guard.max_value:
            raise HTTPException(400, f"Value {val} above maximum {guard.max_value}")
        return val
    return value


def _validate_threshold(t: ThresholdDef, value: Any) -> Any:
    """Validate a threshold value."""
    if t.value_type == "bool":
        if not isinstance(value, bool):
            raise HTTPException(400, f"Threshold '{t.setting_key}' expects a boolean")
        return value
    elif t.value_type == "int":
        try:
            val = int(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Threshold '{t.setting_key}' expects an integer")
        if t.min_value is not None and val < t.min_value:
            raise HTTPException(400, f"Threshold value {val} below minimum {t.min_value}")
        if t.max_value is not None and val > t.max_value:
            raise HTTPException(400, f"Threshold value {val} above maximum {t.max_value}")
        return val
    elif t.value_type == "float":
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Threshold '{t.setting_key}' expects a number")
        if t.min_value is not None and val < t.min_value:
            raise HTTPException(400, f"Threshold value {val} below minimum {t.min_value}")
        if t.max_value is not None and val > t.max_value:
            raise HTTPException(400, f"Threshold value {val} above maximum {t.max_value}")
        return val
    return value


def _get_rejection_stats(days: int = 7) -> dict:
    """Get guard rejection counts from trade_events table."""
    try:
        sb = get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Query rejection events
        result = (
            sb.table("trade_events")
            .select("event_type, metadata, created_at")
            .in_(
                "event_type",
                [
                    "filtered",
                    "staleness_rejected",
                    "holiday_rejected",
                    "guard_blocked",
                    "kill_switch_blocked",
                    "pine_filtered",
                ],
            )
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )

        # Count total signals for percentage
        total_result = (
            sb.table("trade_events")
            .select("id", count="exact")
            .eq("event_type", "signal_received")
            .gte("created_at", since)
            .execute()
        )

        rows = result.data or []
        total_signals = total_result.count or 0

        # Aggregate by guard_name
        by_guard: dict[str, dict] = {}
        for row in rows:
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    import json as _json
                    meta = _json.loads(meta)
                except Exception:
                    meta = {}
            guard_name = meta.get("guard_name", row.get("event_type", "unknown"))
            if guard_name not in by_guard:
                by_guard[guard_name] = {"count": 0, "last_reason": "", "last_time": ""}
            by_guard[guard_name]["count"] += 1
            reason = meta.get("reason", row.get("event_type", ""))
            if not by_guard[guard_name]["last_reason"]:
                by_guard[guard_name]["last_reason"] = reason
                by_guard[guard_name]["last_time"] = row.get("created_at", "")

        return {
            "by_guard": by_guard,
            "total_rejections": len(rows),
            "total_signals": total_signals,
        }
    except Exception as e:
        logger.warning("Failed to fetch rejection stats: %s", e)
        return {"by_guard": {}, "total_rejections": 0, "total_signals": 0}


def _build_guards_response(guards: list[GuardDefinition], *, account_id: str | None = None) -> GuardsConfigResponse:
    stats = _get_rejection_stats(7)
    by_guard_stats = stats.get("by_guard", {})
    groups: dict[str, list[GuardResponse]] = {}
    overrides = load_account_guard_overrides(account_id) if account_id else {}

    for guard in guards:
        current_value = (
            _get_account_current_value(guard, account_id, overrides)
            if account_id
            else _get_current_value(guard)
        )

        threshold_responses = []
        for t in guard.thresholds:
            if isinstance(t, ThresholdDef):
                threshold_responses.append(
                    ThresholdResponse(
                        setting_key=t.setting_key,
                        name=t.name,
                        value_type=t.value_type,
                        current_value=_get_account_threshold_value(t, account_id, overrides) if account_id else _get_threshold_value(t),
                        default=t.default,
                        min_value=t.min_value,
                        max_value=t.max_value,
                        unit=t.unit,
                    )
                )

        guard_stats = by_guard_stats.get(guard.guard_id, {})
        event_type = _GUARD_EVENT_MAP.get(guard.guard_id, guard.guard_id)
        if not guard_stats:
            guard_stats = by_guard_stats.get(event_type, {})

        dyn_info = None
        if guard.guard_id == "one_candle_liq_filter":
            dt = get_dynamic_threshold_info()
            dep_info = dt["departure"]
            dyn_info = DynamicThresholdInfo(
                enabled=True,
                base=dep_info["base"],
                min_val=dep_info["min"],
                max_val=dep_info["max"],
                description=dep_info["description"],
            )

        resp = GuardResponse(
            guard_id=guard.guard_id,
            name=guard.name,
            description=guard.description,
            user_description=guard.user_description,
            tier=guard.tier,
            group=guard.group,
            group_label=GROUP_LABELS.get(guard.group, guard.group),
            value_type=guard.value_type,
            enabled=current_value,
            default=guard.default,
            min_value=guard.min_value,
            max_value=guard.max_value,
            unit=guard.unit,
            thresholds=threshold_responses,
            rejection_count_7d=guard_stats.get("count", 0),
            last_rejection_reason=guard_stats.get("last_reason"),
            dynamic_threshold=dyn_info,
            scope=guard.scope,
        )
        groups.setdefault(guard.group, []).append(resp)

    return GuardsConfigResponse(
        groups=groups,
        group_labels=GROUP_LABELS,
        tier_labels=TIER_LABELS,
        total_rejections_7d=stats.get("total_rejections", 0),
        total_signals_7d=stats.get("total_signals", 0),
    )


# Guard name -> event_type mapping for rejection stats
_GUARD_EVENT_MAP = {
    "kill_switch": "kill_switch_blocked",
    "staleness_guard": "staleness_rejected",
    "holiday_guard": "holiday_rejected",
    "ai_filter": "ai_rejected",
}


# ══════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════


@router.get("/config", response_model=GuardsConfigResponse)
def get_guards_config():
    """Return all guards with current values, grouped by category."""
    return _build_guards_response([guard for guard in get_all_guards() if guard.scope == "global"])


@router.get("/accounts", response_model=GuardAccountsResponse)
def list_guard_accounts():
    profiles = get_active_profiles()
    accounts = []
    for profile in profiles:
        profile_id = profile.get("id") or profile.get("name")
        if not profile_id:
            continue
        accounts.append(
            GuardAccountEntry(
                id=str(profile_id),
                name=str(profile.get("name") or profile_id),
                run_mode=str(profile.get("run_mode") or "LIVE"),
            )
        )
    return GuardAccountsResponse(accounts=accounts)


@router.get("/config/account/{account_id}", response_model=GuardsConfigResponse)
def get_account_guards_config(account_id: str):
    guards = [guard for guard in get_all_guards() if guard.scope == "account"]
    return _build_guards_response(guards, account_id=account_id)


@router.patch("/config/{guard_id}", response_model=GuardUpdateResponse)
def update_guard_config(guard_id: str, body: GuardUpdateRequest):
    """Update a guard's enabled state or thresholds.

    Critical guards require a non-empty change_reason.
    All changes are audit-logged to trade_events.
    """
    guard = get_guard(guard_id)
    if not guard:
        raise HTTPException(404, f"Guard '{guard_id}' not found")

    # Critical guards require a reason
    if guard.tier == "critical" and not body.change_reason.strip():
        raise HTTPException(
            400,
            f"Guard '{guard_id}' is critical — change_reason is required",
        )

    # Validate primary value
    validated_value = _validate_value(guard, body.value)
    old_value = _get_current_value(guard)

    # Write primary value
    update_setting(
        guard.setting_key,
        validated_value,
        updated_by="UI",
        change_reason=body.change_reason or f"Guard {guard_id} updated via UI",
    )
    if guard.setting_key in _SYSTEM_CONFIG_KEYS:
        _write_system_config_value(guard.setting_key, validated_value)

    # Handle threshold updates
    threshold_updates = {}
    if body.thresholds:
        threshold_map = {t.setting_key: t for t in guard.thresholds if isinstance(t, ThresholdDef)}
        for key, val in body.thresholds.items():
            t_def = threshold_map.get(key)
            if not t_def:
                raise HTTPException(400, f"Unknown threshold '{key}' for guard '{guard_id}'")
            validated_t = _validate_threshold(t_def, val)
            old_t = _get_threshold_value(t_def)
            update_setting(
                key,
                validated_t,
                updated_by="UI",
                change_reason=body.change_reason or f"Threshold {key} updated via UI",
            )
            if key in _SYSTEM_CONFIG_KEYS:
                _write_system_config_value(key, validated_t)
            threshold_updates[key] = {"old": old_t, "new": validated_t}

    if guard.setting_key in _SYSTEM_CONFIG_KEYS or any(key in _SYSTEM_CONFIG_KEYS for key in threshold_updates):
        _invalidate_runtime_guard_caches()

    # Read back confirmed value
    confirmed = _get_current_value(guard)

    # Audit log
    log_event(
        signal_id=None,
        event_type="guard_config_updated",
        stage="api.guards",
        metadata={
            "guard_id": guard_id,
            "setting_key": guard.setting_key,
            "tier": guard.tier,
            "old_value": old_value,
            "new_value": validated_value,
            "confirmed_value": confirmed,
            "threshold_updates": threshold_updates,
            "change_reason": body.change_reason,
        },
    )

    logger.info(
        "Guard config updated: %s (%s) %s -> %s [reason: %s]",
        guard_id,
        guard.tier,
        old_value,
        validated_value,
        body.change_reason,
    )

    return GuardUpdateResponse(
        guard_id=guard_id,
        setting_key=guard.setting_key,
        old_value=old_value,
        new_value=validated_value,
        confirmed_value=confirmed,
        threshold_updates={k: v["new"] for k, v in threshold_updates.items()},
    )


@router.patch("/config/account/{account_id}/{guard_id}", response_model=GuardUpdateResponse)
def update_account_guard_config(account_id: str, guard_id: str, body: GuardUpdateRequest):
    guard = get_guard(guard_id)
    if not guard or guard.scope != "account":
        raise HTTPException(404, f"Account-scoped guard '{guard_id}' not found")

    if guard.tier == "critical" and not body.change_reason.strip():
        raise HTTPException(400, f"Guard '{guard_id}' is critical — change_reason is required")

    validated_value = _validate_value(guard, body.value)
    old_value = _get_account_current_value(guard, account_id, load_account_guard_overrides(account_id))
    updated_overrides = update_account_guard_override(account_id, guard.setting_key, validated_value)
    confirmed_value = updated_overrides.get(guard.setting_key, validated_value)
    threshold_updates = {}

    if body.thresholds:
        threshold_map = {t.setting_key: t for t in guard.thresholds if isinstance(t, ThresholdDef)}
        for key, val in body.thresholds.items():
            t_def = threshold_map.get(key)
            if not t_def:
                raise HTTPException(400, f"Unknown threshold '{key}' for guard '{guard_id}'")
            validated_t = _validate_threshold(t_def, val)
            old_t = _get_account_threshold_value(t_def, account_id, load_account_guard_overrides(account_id))
            updated_overrides = update_account_guard_override(account_id, key, validated_t)
            threshold_updates[key] = {"old": old_t, "new": updated_overrides.get(key, validated_t)}

    log_event(
        signal_id=None,
        event_type="guard_config_updated",
        stage="api.guards.account",
        metadata={
            "guard_id": guard_id,
            "account_id": account_id,
            "setting_key": guard.setting_key,
            "scope": "account",
            "old_value": old_value,
            "new_value": validated_value,
            "confirmed_value": confirmed_value,
            "threshold_updates": threshold_updates,
            "change_reason": body.change_reason,
        },
    )

    return GuardUpdateResponse(
        guard_id=guard.guard_id,
        setting_key=guard.setting_key,
        old_value=old_value,
        new_value=validated_value,
        confirmed_value=confirmed_value,
        threshold_updates={k: v["new"] for k, v in threshold_updates.items()},
    )


@router.get("/rejections", response_model=list[RejectionEntry])
def get_recent_rejections(days: int = 7, limit: int = 50):
    """Return recent guard rejections for display in the UI."""
    try:
        sb = get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        result = (
            sb.table("trade_events")
            .select("event_type, metadata, created_at")
            .in_(
                "event_type",
                [
                    "filtered",
                    "staleness_rejected",
                    "holiday_rejected",
                    "guard_blocked",
                    "kill_switch_blocked",
                    "pine_filtered",
                ],
            )
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        entries = []
        for row in result.data or []:
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    import json as _json
                    meta = _json.loads(meta)
                except Exception:
                    meta = {}
            entries.append(
                RejectionEntry(
                    guard_name=meta.get("guard_name", row.get("event_type", "unknown")),
                    symbol=meta.get("symbol", ""),
                    reason=meta.get("reason", row.get("event_type", "")),
                    timestamp=row.get("created_at", ""),
                )
            )
        return entries
    except Exception as e:
        logger.warning("Failed to fetch rejections: %s", e)
        return []
