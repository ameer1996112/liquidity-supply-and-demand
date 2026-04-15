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
from src.core.account_profiles import coerce_profiles

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
        raw_key = s.supabase_service_role_key or s.supabase_key or ""
        key = raw_key.strip().strip('"\'').strip()
        if key.upper().startswith("SUPA") and "=" in key[:50]:
            key = key.split("=", 1)[-1].strip().strip('"\'').strip()
            
        if s.supabase_url and key:
            client = create_client(s.supabase_url, key)
            r = (
                client.table("broker_profiles")
                .select(
                    "id, name, venue, meta_api_account_id, token, token_env_key, "
                    "api_key, api_secret, "
                    "risk_pct, max_positions, run_mode, "
                    "evaluation_mode, evaluation_phase, consistency_enabled"
                )
                .eq("is_active", True)
                .execute()
            )
            if r.data and len(r.data) > 0:
                out = []
                for row in r.data:
                    venue = (row.get("venue") or "metaapi_mt5").strip().lower()
                    token = ""
                    api_key = ""
                    api_secret = ""

                    if venue in {"binance", "bybit"}:
                        api_key = (row.get("api_key") or "").strip()
                        api_secret = (row.get("api_secret") or "").strip()
                        if not api_key or not api_secret:
                            logger.warning("Broker profile %s: missing %s API keys in DB", row.get("name"), venue)
                            continue
                    else:
                        # Prefer token stored directly in DB; fall back to env var
                        token = (row.get("token") or "").strip()
                        if not token:
                            env_key = (row.get("token_env_key") or "META_API_TOKEN").strip()
                            token = (os.environ.get(env_key) or getattr(s, "meta_api_token", "") or "").strip()
                        if not token:
                            env_key = (row.get("token_env_key") or "META_API_TOKEN").strip()
                            logger.warning("Broker profile %s: no token in DB or env %s", row.get("name"), env_key)
                            continue
                    out.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "profile",
                        "venue": venue,
                        "meta_api_account_id": str(row.get("meta_api_account_id", "")).strip(),
                        "token": token,
                        "api_key": api_key,
                        "api_secret": api_secret,
                        "risk_pct": float(row.get("risk_pct", 1.0)),
                        "max_positions": int(row.get("max_positions", 3)),
                        "run_mode": (row.get("run_mode") or "LIVE").upper(),
                        # Prop firm guard flags — used by _run_account_guards()
                        "evaluation_mode": row.get("evaluation_mode", False),
                        "evaluation_phase": row.get("evaluation_phase", "phase1"),
                        "consistency_enabled": row.get("consistency_enabled"),  # None | True | False
                    })
                if out:
                    logger.info("Loaded %s broker profile(s) from DB", len(out))
                    return coerce_profiles(out)
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
                    venue = (row.get("venue") or "").strip().lower() or "metaapi_mt5"

                    token = ""
                    if venue in {"metaapi", "metaapi_mt5", "mt5"}:
                        env_key = (row.get("token_env_key") or "META_API_TOKEN").strip()
                        token = (os.environ.get(env_key) or getattr(s, "meta_api_token", "") or "").strip()
                        if not token:
                            logger.warning("Profile %s: no token in env %s", row.get("name"), env_key)
                            continue

                    api_key = ""
                    api_secret = ""
                    if venue in {"binance", "bybit"}:
                        api_key_env = (row.get("api_key_env_key") or "").strip()
                        api_secret_env = (row.get("api_secret_env_key") or "").strip()
                        api_key = (os.environ.get(api_key_env) if api_key_env else (row.get("api_key") or "")).strip()
                        api_secret = (os.environ.get(api_secret_env) if api_secret_env else (row.get("api_secret") or "")).strip()
                        if not api_key or not api_secret:
                            logger.warning("Profile %s: missing crypto API keys (venue=%s)", row.get("name"), venue)
                            continue

                    out.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "profile",
                        "meta_api_account_id": str(row.get("meta_api_account_id") or row.get("account_id") or "").strip(),
                        "token": token,
                        "venue": venue,
                        "mode": (row.get("mode") or "personal").strip().lower(),
                        "asset_class": (row.get("asset_class") or ("crypto" if venue in {"binance", "bybit"} else "forex_cfd")).strip().lower(),
                        "api_key": api_key,
                        "api_secret": api_secret,
                        "risk_pct": float(row.get("risk_pct", 1.0)),
                        "max_positions": int(row.get("max_positions", 3)),
                        "run_mode": (row.get("run_mode") or "LIVE").upper(),
                    })
                if out:
                    logger.info("Loaded %s broker profile(s) from BROKER_PROFILES_JSON", len(out))
                    return coerce_profiles(out)
        except json.JSONDecodeError as e:
            logger.warning("Invalid BROKER_PROFILES_JSON: %s", e)

    # 3) Default: accounts from settings.get_accounts (handles both single and multi config strings)
    accounts = getattr(s, "get_accounts", [])
    if not accounts:
        return []
        
    try:
        from src.core.dynamic_config import get_dynamic_setting
        risk_pct = float(get_dynamic_setting("risk_percent", s.risk_percent))
    except Exception:
        risk_pct = s.risk_percent
        
    out = []
    for i, acc in enumerate(accounts):
        out.append({
            "id": None,
            "name": f"Account-{i+1}" if len(accounts) > 1 else "default",
            "meta_api_account_id": acc["account_id"],
            "token": acc["token"],
            "risk_pct": risk_pct,
            "max_positions": getattr(s, "trinity_max_positions", 3),
            "run_mode": (s.run_mode or "LIVE").upper() if s.run_mode != "DRY_RUN" else "LIVE",
        })
    
    if len(out) > 1:
        logger.info("Loaded %s broker profile(s) from META_API_ACCOUNTS configuration", len(out))
    return coerce_profiles(out)
