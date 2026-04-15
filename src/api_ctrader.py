"""
cTrader Open API integration (Spotware).

Implements:
- OAuth start + callback to store refresh token per broker_profile (venue=ctrader)
- Connection test (Open API JSON over WebSocket) to validate app+account auth

Notes:
- broker_profiles router is admin-protected, but OAuth callbacks cannot carry headers.
  Therefore this router validates security via signed OAuth state.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import os

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config import get_settings
from src.adapters.supabase_api import get_api_supabase as _get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ctrader", tags=["ctrader"])

_OAUTH_GRANT_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
_OAUTH_TOKEN_URL = "https://openapi.ctrader.com/apps/token"

_PUBLIC_API_BASE_URL_KEY = "public_api_base_url"
_CTRADER_CLIENT_ID_KEY = "ctrader_client_id"
_CTRADER_CLIENT_SECRET_KEY = "ctrader_client_secret"
_CTRADER_STATE_SECRET_KEY = "ctrader_oauth_state_secret"


def _get_system_config_value(key: str) -> str:
    try:
        sb = _get_supabase()
        r = sb.table("system_config").select("value").eq("key", key).single().execute()
        if r.data and r.data.get("value") is not None:
            return str(r.data["value"] or "").strip()
    except Exception:
        pass
    return ""


def _require_admin_key(
    x_admin_api_key: str | None,
    authorization: str | None,
) -> None:
    """Local copy of the admin-key gate used by src/api.py."""
    settings = get_settings()
    expected = (settings.admin_api_key or "").strip()
    if not expected:
        return
    provided = (x_admin_api_key or "").strip()
    if not provided and authorization:
        provided = authorization.replace("Bearer ", "").strip()
    if not provided or provided != expected:
        raise HTTPException(status_code=403, detail="Forbidden: invalid admin API key")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _state_secret_bytes() -> bytes:
    s = get_settings()
    # Prefer dedicated secret; fall back to WEBHOOK_SECRET.
    secret = (s.ctrader_oauth_state_secret.get_secret_value() if s.ctrader_oauth_state_secret else "").strip()
    if not secret:
        secret = _get_system_config_value(_CTRADER_STATE_SECRET_KEY)
    if not secret:
        secret = (s.webhook_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="Missing CTRADER_OAUTH_STATE_SECRET (or WEBHOOK_SECRET fallback) for OAuth state signing",
        )
    return secret.encode("utf-8")


def _sign_state(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_state_secret_bytes(), body, hashlib.sha256).digest()
    return f"{_b64url_encode(body)}.{_b64url_encode(sig)}"


def _verify_state(state: str, max_age_seconds: int = 10 * 60) -> Dict[str, Any]:
    try:
        body_b64, sig_b64 = state.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid state format") from exc

    body = _b64url_decode(body_b64)
    sig = _b64url_decode(sig_b64)
    expected = hmac.new(_state_secret_bytes(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="Invalid state signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid state payload") from exc

    ts = int(payload.get("ts") or 0)
    now = int(time.time())
    if ts <= 0 or now - ts > max_age_seconds:
        raise HTTPException(status_code=400, detail="State expired; please retry connect flow")

    return payload


def _infer_public_base_url(request: Request) -> str:
    """
    Infer the public base URL from common reverse-proxy headers.
    Works on Railway (X-Forwarded-*).
    """
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname or "").strip()
    if not host:
        return ""
    return f"{proto}://{host}".rstrip("/")


def _public_callback_url(request: Request | None = None) -> str:
    s = get_settings()
    base = (s.public_api_base_url or "").strip().rstrip("/")
    if not base:
        base = _get_system_config_value(_PUBLIC_API_BASE_URL_KEY).rstrip("/")
    if not base and request is not None:
        base = _infer_public_base_url(request)
    if not base:
        raise HTTPException(
            status_code=500,
            detail="Missing public API base URL. Set it in Accounts → cTrader Integration (or PUBLIC_API_BASE_URL env var).",
        )
    return f"{base}/api/ctrader/oauth/callback"


def _exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    s = get_settings()
    client_id = (s.ctrader_client_id or "").strip() or _get_system_config_value(_CTRADER_CLIENT_ID_KEY)
    client_secret = (s.ctrader_client_secret.get_secret_value() if s.ctrader_client_secret else "").strip() or _get_system_config_value(_CTRADER_CLIENT_SECRET_KEY)
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Missing CTRADER_CLIENT_ID/CTRADER_CLIENT_SECRET")

    params = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _public_callback_url(),
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        r = requests.get(_OAUTH_TOKEN_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.error("cTrader token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="cTrader token exchange failed") from exc

    if data.get("errorCode") or not data.get("refreshToken"):
        raise HTTPException(status_code=400, detail=f"cTrader token exchange error: {data.get('description') or data.get('errorCode')}")
    return data


def _refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    s = get_settings()
    client_id = (s.ctrader_client_id or "").strip() or _get_system_config_value(_CTRADER_CLIENT_ID_KEY)
    client_secret = (s.ctrader_client_secret.get_secret_value() if s.ctrader_client_secret else "").strip() or _get_system_config_value(_CTRADER_CLIENT_SECRET_KEY)
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Missing CTRADER_CLIENT_ID/CTRADER_CLIENT_SECRET")

    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        r = requests.get(_OAUTH_TOKEN_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.error("cTrader token refresh failed: %s", exc)
        raise HTTPException(status_code=502, detail="cTrader token refresh failed") from exc

    if data.get("errorCode") or not data.get("accessToken"):
        raise HTTPException(status_code=400, detail=f"cTrader token refresh error: {data.get('description') or data.get('errorCode')}")
    return data


@router.post("/oauth/start")
def ctrader_oauth_start(body: Dict[str, Any], request: Request) -> JSONResponse:  # noqa: ARG001
    """Return the OAuth grant URL to open in a browser."""
    _require_admin_key(
        x_admin_api_key=request.headers.get("X-Admin-API-Key"),
        authorization=request.headers.get("Authorization"),
    )
    profile_id = int(body.get("profile_id") or 0)
    scope = (body.get("scope") or "trading").strip().lower()
    if scope not in {"accounts", "trading"}:
        raise HTTPException(status_code=422, detail="scope must be accounts|trading")
    if profile_id <= 0:
        raise HTTPException(status_code=422, detail="profile_id is required")

    s = get_settings()
    client_id = (s.ctrader_client_id or "").strip() or _get_system_config_value(_CTRADER_CLIENT_ID_KEY)
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="Missing cTrader client id (set in Accounts → cTrader Integration).",
        )

    # Verify profile exists and is ctrader
    sb = _get_supabase()
    check = sb.table("broker_profiles").select("id, venue").eq("id", profile_id).limit(1).execute()
    rows = check.data or []
    if not rows:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    venue = (rows[0].get("venue") or "metaapi_mt5").strip().lower()
    if venue != "ctrader":
        raise HTTPException(status_code=409, detail="Profile venue must be ctrader")

    payload = {
        "v": 1,
        "profile_id": profile_id,
        "scope": scope,
        "nonce": uuid.uuid4().hex,
        "ts": int(time.time()),
    }
    state = _sign_state(payload)

    params = {
        "client_id": client_id,
        "redirect_uri": _public_callback_url(request),
        "scope": scope,
        "product": "web",
        "state": state,
    }
    # Build manually to avoid leaking secrets; this URL is safe to share with the browser.
    authorize_url = requests.Request("GET", _OAUTH_GRANT_URL, params=params).prepare().url  # type: ignore[assignment]
    if not authorize_url:
        raise HTTPException(status_code=500, detail="Failed to build authorize URL")
    return JSONResponse({"authorize_url": authorize_url})


@router.get("/oauth/callback")
def ctrader_oauth_callback(request: Request, code: str | None = None, state: str | None = None) -> HTMLResponse:
    """OAuth redirect URI: exchanges auth code for tokens and stores refreshToken in broker_profiles.token."""
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code/state")

    st = _verify_state(state)
    profile_id = int(st.get("profile_id") or 0)
    if profile_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid profile_id in state")

    tokens = _exchange_code_for_tokens(code)
    refresh_token = (tokens.get("refreshToken") or "").strip()
    _expires_in = int(tokens.get("expiresIn") or 0)
    _access_token = (tokens.get("accessToken") or "").strip()

    sb = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    patch: Dict[str, Any] = {
        "token": refresh_token,
        "connection_status": "connected",
        "connection_error": None,
        "last_tested_at": now,
    }
    try:
        sb.table("broker_profiles").update(patch).eq("id", profile_id).execute()
    except Exception as exc:
        logger.error("Failed to persist cTrader tokens to broker_profiles: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save cTrader tokens") from exc

    # Simple success page + redirect back to frontend if configured.
    frontend_url = (os.getenv("FRONTEND_URL") or "").strip().rstrip("/")
    if not frontend_url:
        origin = (request.headers.get("origin") or "").strip().rstrip("/")
        frontend_url = origin
    refresh_meta = f'<meta http-equiv="refresh" content="2;url={frontend_url}/accounts" />' if frontend_url else ""
    return HTMLResponse(
        f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>cTrader Connected</title>
    {refresh_meta}
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system; padding: 24px; }}
      .ok {{ color: #16a34a; font-weight: 700; }}
      code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }}
    </style>
  </head>
  <body>
    <div class="ok">Connected to cTrader.</div>
    <p>You can close this window and return to the dashboard.</p>
    <p>Profile: <code>{profile_id}</code></p>
  </body>
</html>""",
    )


@router.post("/profiles/{profile_id}/test")
async def ctrader_test_profile(request: Request, profile_id: int) -> Dict[str, Any]:
    """
    Validate that we can:
    - refresh an access token from broker_profiles.token (refresh token)
    - perform Open API app auth + account list fetch over WebSocket (JSON)
    """
    # This endpoint is admin-gated (if ADMIN_API_KEY is set).
    # We pull headers explicitly because _require_admin_key is not used as a FastAPI dependency here.
    _require_admin_key(
        x_admin_api_key=request.headers.get("X-Admin-API-Key"),
        authorization=request.headers.get("Authorization"),
    )
    sb = _get_supabase()
    resp = (
        sb.table("broker_profiles")
        .select("id, venue, token")
        .eq("id", profile_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    row = rows[0]
    venue = (row.get("venue") or "").strip().lower()
    if venue != "ctrader":
        raise HTTPException(status_code=409, detail="Profile venue must be ctrader")
    refresh_token = (row.get("token") or "").strip()
    if not refresh_token:
        raise HTTPException(status_code=422, detail="No cTrader refresh token stored yet. Click Connect first.")

    token_data = _refresh_access_token(refresh_token)
    access_token = (token_data.get("accessToken") or "").strip()
    new_refresh_token = (token_data.get("refreshToken") or "").strip()

    # Import here to keep router import-time fast.
    from src.adapters.ctrader_openapi_ws import fetch_accounts_via_websocket

    accounts = await fetch_accounts_via_websocket(access_token=access_token)

    now = datetime.now(timezone.utc).isoformat()
    # Persist rotated refresh token if it changed
    try:
        patch: Dict[str, Any] = {
            "token": new_refresh_token or refresh_token,
            "connection_status": "connected",
            "connection_error": None,
            "last_tested_at": now,
        }
        # Store the first account id for display; user can reconnect to pick more later.
        if accounts and isinstance(accounts[0], dict) and accounts[0].get("ctidTraderAccountId"):
            patch["meta_api_account_id"] = str(accounts[0]["ctidTraderAccountId"])
        sb.table("broker_profiles").update(patch).eq("id", profile_id).execute()
    except Exception as exc:
        logger.warning("Failed to persist cTrader test results: %s", exc)

    return {
        "success": True,
        "message": "cTrader connection ok",
        "accounts": accounts,
        "account_count": len(accounts),
    }
