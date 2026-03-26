"""
MetaAPI credentials resolver.

Priority:
  1. broker_profiles.token + meta_api_account_id where selected_for_trading = True
  2. Any active broker_profiles row that has a non-empty token + meta_api_account_id
  3. Empty strings → callers interpret as "not configured"

This removes the need for META_API_TOKEN / META_API_ACCOUNT_ID env vars.
META_API_REGION is still read from env (set in Railway → shared across all accounts).
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from config import get_settings

logger = logging.getLogger(__name__)


def get_primary_credentials(supabase_client=None) -> Tuple[str, str, str]:
    """
    Return (token, account_id, region) from the primary broker profile.

    Primary = selected_for_trading=True row, falling back to any active row
    with a non-empty token and meta_api_account_id.

    Returns empty strings if nothing is configured.
    """
    region = (getattr(get_settings(), "meta_api_region", "") or "new-york").strip()

    if supabase_client is None:
        try:
            from src.adapters.supabase_api import get_api_supabase
            supabase_client = get_api_supabase()
        except Exception as exc:
            logger.warning("get_primary_credentials: cannot get supabase client: %s", exc)
            return "", "", region

    try:
        # 1. Prefer the account marked selected_for_trading=True
        resp = (
            supabase_client
            .table("broker_profiles")
            .select("token,meta_api_account_id")
            .eq("is_active", True)
            .eq("selected_for_trading", True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []

        # 2. Fallback: any active row with credentials
        if not rows:
            resp = (
                supabase_client
                .table("broker_profiles")
                .select("token,meta_api_account_id")
                .eq("is_active", True)
                .neq("token", "")
                .neq("meta_api_account_id", "")
                .limit(1)
                .execute()
            )
            rows = resp.data or []

        if rows:
            token = (rows[0].get("token") or "").strip()
            account_id = (rows[0].get("meta_api_account_id") or "").strip()
            if token and account_id:
                logger.debug(
                    "get_primary_credentials: loaded from DB (account_id prefix: %s)",
                    account_id[:8],
                )
                return token, account_id, region

    except Exception as exc:
        logger.warning("get_primary_credentials: DB lookup failed: %s", exc)

    return "", "", region


def get_all_active_credentials(supabase_client=None) -> list[dict]:
    """
    Return list of {token, account_id, account_name, broker_profile_id} for
    all active broker profiles that have both token and meta_api_account_id set.
    """
    if supabase_client is None:
        try:
            from src.adapters.supabase_api import get_api_supabase
            supabase_client = get_api_supabase()
        except Exception as exc:
            logger.warning("get_all_active_credentials: cannot get supabase: %s", exc)
            return []

    try:
        resp = (
            supabase_client
            .table("broker_profiles")
            .select("id,name,token,meta_api_account_id")
            .eq("is_active", True)
            .execute()
        )
        rows = resp.data or []
        result = []
        for row in rows:
            t = (row.get("token") or "").strip()
            aid = (row.get("meta_api_account_id") or "").strip()
            if t and aid:
                result.append({
                    "broker_profile_id": row.get("id"),
                    "account_name": row.get("name") or "",
                    "token": t,
                    "account_id": aid,
                })
        return result
    except Exception as exc:
        logger.warning("get_all_active_credentials: DB lookup failed: %s", exc)
        return []
