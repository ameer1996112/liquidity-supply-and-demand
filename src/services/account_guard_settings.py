from __future__ import annotations

import logging
from typing import Any

from src.adapters.supabase_api import get_api_supabase as get_supabase

logger = logging.getLogger(__name__)


def get_effective_account_guard_value(
    *,
    account_id: str,
    setting_key: str,
    global_default: Any,
    account_overrides: dict[str, Any] | None = None,
) -> tuple[Any, str]:
    """Return effective account-scoped value with source metadata."""
    del account_id  # reserved for future validation/auditing
    overrides = account_overrides or {}
    if setting_key in overrides:
        return overrides[setting_key], "account"
    return global_default, "global_default"


def load_account_guard_overrides(account_id: str) -> dict[str, Any]:
    """Load sparse per-account guard overrides."""
    try:
        sb = get_supabase()
        row = (
            sb.table("account_guard_settings")
            .select("settings")
            .eq("account_id", account_id)
            .limit(1)
            .execute()
        )
        data = row.data[0] if row.data else {}
        return data.get("settings") or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Account guard overrides unavailable for %s, falling back to global defaults: %s",
            account_id,
            exc,
        )
        return {}


def update_account_guard_override(account_id: str, setting_key: str, value: Any) -> dict[str, Any]:
    """Upsert a single account guard override and return the updated settings map."""
    sb = get_supabase()
    current = load_account_guard_overrides(account_id)
    current[setting_key] = value
    sb.table("account_guard_settings").upsert(
        {"account_id": account_id, "settings": current},
        on_conflict="account_id",
    ).execute()
    return current
