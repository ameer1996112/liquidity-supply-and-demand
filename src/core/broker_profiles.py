"""
Broker profiles for multi-account execution (Package A).
Loads active profiles from DB (broker_profiles table) or from env (BROKER_PROFILES_JSON).
When none configured, returns a single default profile from settings.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from config import get_settings

logger = logging.getLogger(__name__)


def get_active_profiles() -> List[Dict[str, Any]]:
    """
    Return list of broker profiles to execute for each signal.
    Each profile dict has: id (optional), name, meta_api_account_id, token, risk_pct, max_positions, run_mode.

    - If broker_profiles table exists and has active rows, use those (token from env via token_env_key).
    - Else if BROKER_PROFILES_JSON is set, parse and resolve tokens from env.
    - Else return one "default" profile from settings (current single-account behavior).
    """
    s = get_settings()

    # 1) Try DB table broker_profiles
    try:
        from supabase import create_client
        key = (s.supabase_service_role_key or s.supabase_key or "").strip()
        if s.supabase_url and key:
            client = create_client(s.supabase_url, key)
            r = (
                client.table("broker_profiles")
                .select("id, name, meta_api_account_id, token_env_key, risk_pct, max_positions, run_mode")
                .eq("is_active", True)
                .execute()
            )
            if r.data and len(r.data) > 0:
                out = []
                for row in r.data:
                    env_key = (row.get("token_env_key") or "META_API_TOKEN").strip()
                    token = (os.environ.get(env_key) or getattr(s, "meta_api_token", "") or "").strip()
                    if not token:
                        logger.warning("Broker profile %s: no token in env %s", row.get("name"), env_key)
                        continue
                    out.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "profile",
                        "meta_api_account_id": str(row.get("meta_api_account_id", "")).strip(),
                        "token": token,
                        "risk_pct": float(row.get("risk_pct", 1.0)),
                        "max_positions": int(row.get("max_positions", 3)),
                        "run_mode": (row.get("run_mode") or "LIVE").upper(),
                    })
                if out:
                    logger.info("Loaded %s broker profile(s) from DB", len(out))
                    return out
    except Exception as exc:
        logger.debug("broker_profiles table not available: %s", exc)

    # 2) Try BROKER_PROFILES_JSON
    raw = (getattr(s, "broker_profiles_json", None) or os.environ.get("BROKER_PROFILES_JSON") or "").strip()
    if raw:
        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) > 0:
                out = []
                for row in arr:
                    if not isinstance(row, dict):
                        continue
                    env_key = (row.get("token_env_key") or "META_API_TOKEN").strip()
                    token = (os.environ.get(env_key) or getattr(s, "meta_api_token", "") or "").strip()
                    if not token:
                        logger.warning("Profile %s: no token in env %s", row.get("name"), env_key)
                        continue
                    out.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "profile",
                        "meta_api_account_id": str(row.get("meta_api_account_id") or row.get("account_id") or "").strip(),
                        "token": token,
                        "risk_pct": float(row.get("risk_pct", 1.0)),
                        "max_positions": int(row.get("max_positions", 3)),
                        "run_mode": (row.get("run_mode") or "LIVE").upper(),
                    })
                if out:
                    logger.info("Loaded %s broker profile(s) from BROKER_PROFILES_JSON", len(out))
                    return out
        except json.JSONDecodeError as e:
            logger.warning("Invalid BROKER_PROFILES_JSON: %s", e)

    # 3) Default: single account from settings
    token = (s.meta_api_token or "").strip()
    account_id = (s.meta_api_account_id or "").strip()
    if not token or not account_id:
        return []
    return [
        {
            "id": None,
            "name": "default",
            "meta_api_account_id": account_id,
            "token": token,
            "risk_pct": s.risk_percent,
            "max_positions": getattr(s, "trinity_max_positions", 3),
            "run_mode": (s.run_mode or "LIVE").upper() if s.run_mode != "DRY_RUN" else "LIVE",
        }
    ]
