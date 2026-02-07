"""
Dynamic Configuration System

Allows live risk settings updates without restart.
Priority: risk_config_overrides table > .env settings

Usage:
    from src.core.dynamic_config import get_dynamic_setting

    # Get risk_percent (checks DB first, falls back to settings.py)
    risk_percent = get_dynamic_setting("risk_percent", default=0.5)
"""

import logging
from typing import Any, Optional, Union
from functools import lru_cache

logger = logging.getLogger(__name__)

# Singleton Supabase client
_supabase = None


def _get_supabase():
    """Lazy Supabase client initialization."""
    global _supabase
    if _supabase is not None:
        return _supabase

    try:
        from config import get_settings
        from supabase import create_client

        s = get_settings()
        key = (s.supabase_service_role_key or s.supabase_key or "").strip()
        if s.supabase_url and key:
            _supabase = create_client(s.supabase_url, key)
            return _supabase
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase for dynamic config: {e}")

    return None


def get_dynamic_setting(
    setting_key: str,
    default: Any = None,
    use_cache: bool = True
) -> Any:
    """
    Get a setting with priority: DB override > .env settings.

    Args:
        setting_key: Setting name (e.g., 'risk_percent', 'max_lot_size')
        default: Default value if not found in DB or settings
        use_cache: Whether to use cached settings (default True)

    Returns:
        Setting value (float, bool, int, dict, or default)

    Example:
        >>> risk_pct = get_dynamic_setting("risk_percent", default=0.5)
        >>> # If DB has override: returns DB value
        >>> # Else: returns settings.risk_percent
        >>> # Else: returns 0.5
    """
    if use_cache:
        return _get_dynamic_setting_cached(setting_key, default)
    else:
        return _get_dynamic_setting_impl(setting_key, default)


@lru_cache(maxsize=128)
def _get_dynamic_setting_cached(setting_key: str, default: Any) -> Any:
    """Cached version of get_dynamic_setting (clears every minute in worker)."""
    return _get_dynamic_setting_impl(setting_key, default)


def _get_dynamic_setting_impl(setting_key: str, default: Any) -> Any:
    """Internal implementation of dynamic setting retrieval."""

    # 1. Try DB override first
    sb = _get_supabase()
    if sb:
        try:
            result = (
                sb.table("risk_config_overrides")
                .select("value_float, value_bool, value_int, value_json")
                .eq("setting_key", setting_key)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )

            if result.data:
                row = result.data[0]

                # Return first non-null value
                if row.get("value_float") is not None:
                    return float(row["value_float"])
                if row.get("value_bool") is not None:
                    return bool(row["value_bool"])
                if row.get("value_int") is not None:
                    return int(row["value_int"])
                if row.get("value_json") is not None:
                    return row["value_json"]

        except Exception as e:
            logger.warning(f"Failed to fetch dynamic setting '{setting_key}': {e}")

    # 2. Fall back to settings.py
    try:
        from config import get_settings
        s = get_settings()

        if hasattr(s, setting_key):
            value = getattr(s, setting_key)
            logger.debug(f"Using .env setting for '{setting_key}': {value}")
            return value

    except Exception as e:
        logger.warning(f"Failed to fetch setting from config: {e}")

    # 3. Fall back to default
    logger.debug(f"Using default for '{setting_key}': {default}")
    return default


def clear_settings_cache():
    """Clear the LRU cache (call this periodically in worker to pick up DB changes)."""
    _get_dynamic_setting_cached.cache_clear()
    logger.info("Dynamic settings cache cleared")


def update_setting(
    setting_key: str,
    value: Union[float, bool, int, dict],
    updated_by: str = "SYSTEM",
    change_reason: Optional[str] = None
) -> bool:
    """
    Update a risk setting in the database.

    Args:
        setting_key: Setting name
        value: New value
        updated_by: Who made the change (default "SYSTEM")
        change_reason: Optional reason for the change

    Returns:
        True if successful, False otherwise

    Example:
        >>> update_setting("risk_percent", 0.75, updated_by="UI", change_reason="Market volatility low")
    """
    sb = _get_supabase()
    if not sb:
        logger.error("Cannot update setting: Supabase not available")
        return False

    try:
        # Get current value for audit trail
        old_result = (
            sb.table("risk_config_overrides")
            .select("value_float, value_bool, value_int, value_json")
            .eq("setting_key", setting_key)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        previous_value = None
        if old_result.data:
            old_row = old_result.data[0]
            # Convert to string for audit trail
            for key in ["value_float", "value_bool", "value_int", "value_json"]:
                if old_row.get(key) is not None:
                    previous_value = str(old_row[key])
                    break

        # Prepare data
        data = {
            "setting_key": setting_key,
            "updated_by": updated_by,
            "is_active": True,
        }

        # Set appropriate value column
        if isinstance(value, float):
            data["value_float"] = value
        elif isinstance(value, bool):
            data["value_bool"] = value
        elif isinstance(value, int):
            data["value_int"] = value
        elif isinstance(value, dict):
            data["value_json"] = value
        else:
            logger.error(f"Unsupported value type for setting '{setting_key}': {type(value)}")
            return False

        # Add audit fields
        if previous_value:
            data["previous_value"] = previous_value
        if change_reason:
            data["change_reason"] = change_reason

        # Upsert on setting_key (UNIQUE) - update existing row or insert new
        sb.table("risk_config_overrides").upsert(data, on_conflict="setting_key").execute()

        # Clear cache so new value takes effect immediately
        clear_settings_cache()

        logger.info(
            f"Updated setting '{setting_key}' to {value} (was: {previous_value}, by: {updated_by})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to update setting '{setting_key}': {e}")
        return False


def get_all_active_overrides() -> dict:
    """
    Get all active risk config overrides.

    Returns:
        Dictionary of {setting_key: value}
    """
    sb = _get_supabase()
    if not sb:
        return {}

    try:
        result = (
            sb.table("risk_config_overrides")
            .select("setting_key, value_float, value_bool, value_int, value_json")
            .eq("is_active", True)
            .execute()
        )

        overrides = {}
        for row in result.data:
            key = row["setting_key"]

            # Get value from first non-null column
            if row.get("value_float") is not None:
                overrides[key] = row["value_float"]
            elif row.get("value_bool") is not None:
                overrides[key] = row["value_bool"]
            elif row.get("value_int") is not None:
                overrides[key] = row["value_int"]
            elif row.get("value_json") is not None:
                overrides[key] = row["value_json"]

        return overrides

    except Exception as e:
        logger.error(f"Failed to fetch active overrides: {e}")
        return {}


def reset_setting(setting_key: str) -> bool:
    """
    Reset a setting to .env default by deactivating the override.

    Args:
        setting_key: Setting to reset

    Returns:
        True if successful
    """
    sb = _get_supabase()
    if not sb:
        logger.error("Cannot reset setting: Supabase not available")
        return False

    try:
        sb.table("risk_config_overrides").update(
            {"is_active": False}
        ).eq("setting_key", setting_key).execute()

        clear_settings_cache()

        logger.info(f"Reset setting '{setting_key}' to .env default")
        return True

    except Exception as e:
        logger.error(f"Failed to reset setting '{setting_key}': {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# Time-Based Risk Rules Engine
# ═══════════════════════════════════════════════════════════════

def get_active_time_rules() -> list:
    """Get all enabled time-based risk rules."""
    sb = _get_supabase()
    if not sb:
        return []

    try:
        result = (
            sb.table("time_based_risk_rules")
            .select("*")
            .eq("enabled", True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch time-based rules: {e}")
        return []


def check_time_rule_trigger(rule: dict) -> tuple[bool, Optional[float]]:
    """
    Check if a time-based rule should trigger now.

    Args:
        rule: Rule dict from time_based_risk_rules table

    Returns:
        (should_trigger, risk_multiplier)
    """
    from datetime import datetime, time as dt_time
    import pytz

    trigger_type = rule.get("trigger_type", "")
    timezone = pytz.timezone(rule.get("trigger_timezone", "UTC"))
    now = datetime.now(timezone)

    # Check TIME_OF_DAY trigger
    if trigger_type == "TIME_OF_DAY":
        start_time = rule.get("trigger_time_start")
        end_time = rule.get("trigger_time_end")

        if start_time and end_time:
            # Parse time strings
            start = datetime.strptime(str(start_time), "%H:%M:%S").time()
            end = datetime.strptime(str(end_time), "%H:%M:%S").time()

            current_time = now.time()

            # Check if current time is within range
            if start <= current_time <= end:
                return True, rule.get("risk_multiplier", 1.0)

    # Check DAY_OF_WEEK trigger
    elif trigger_type == "DAY_OF_WEEK":
        trigger_days = rule.get("trigger_days", [])
        current_day = now.strftime("%A").upper()

        if current_day in [d.upper() for d in trigger_days]:
            return True, rule.get("risk_multiplier", 1.0)

    # NFP_RELEASE and other events would need external calendar integration
    # For now, return False
    return False, None


def apply_time_based_rules() -> Optional[float]:
    """
    Check all active time-based rules and return aggregate risk multiplier.

    Returns:
        Risk multiplier to apply (None if no rules active)
    """
    rules = get_active_time_rules()
    if not rules:
        return None

    multipliers = []
    for rule in rules:
        should_trigger, multiplier = check_time_rule_trigger(rule)
        if should_trigger and multiplier is not None:
            multipliers.append(multiplier)
            logger.info(f"Time-based rule triggered: {rule.get('rule_name')} (multiplier={multiplier})")

    # If multiple rules active, use the most conservative (lowest multiplier)
    if multipliers:
        return min(multipliers)

    return None
