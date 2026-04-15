"""
Broker Profiles API — CRUD + connection management.

Routes
------
GET    /api/broker-profiles              List all profiles
POST   /api/broker-profiles              Create new profile
PUT    /api/broker-profiles/{id}         Update profile
DELETE /api/broker-profiles/{id}         Delete profile
POST   /api/broker-profiles/{id}/activate   Set as active trading account
POST   /api/broker-profiles/{id}/test    Test MetaAPI connection
"""

from __future__ import annotations

import logging
import os
import time
import hashlib
import hmac
import re
from urllib.parse import urlencode
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/broker-profiles", tags=["broker-profiles"])

from src.adapters.supabase_api import get_api_supabase as _get_supabase


_UNKNOWN_COLUMN_RE = re.compile(r"Could not find the '([^']+)' column", re.IGNORECASE)


def _insert_with_unknown_column_retry(
    sb: Any,
    table: str,
    payload: Dict[str, Any],
):
    """
    Backwards-compatible insert helper.

    Some deployments have older broker_profiles schemas (PostgREST schema cache)
    which may be missing newer columns like `prop_firm_name`.
    When PostgREST returns PGRST204 unknown-column errors, retry the insert after
    stripping that column from the payload.
    """
    try:
        return sb.table(table).insert(payload).execute()
    except Exception as exc:
        msg = str(exc)
        m = _UNKNOWN_COLUMN_RE.search(msg)
        if not m:
            raise
        col = m.group(1)
        if col not in payload:
            raise
        patched = dict(payload)
        patched.pop(col, None)
        logger.warning("Insert retry: stripping unknown column %s from %s payload", col, table)
        return sb.table(table).insert(patched).execute()


# ── Request / Response Models ──────────────────────────────────────────────────

class BrokerProfileCreate(BaseModel):
    venue: str = Field(
        default="metaapi_mt5",
        description="Execution venue: metaapi_mt5 | ctrader | binance | bybit",
    )
    name: str = Field(..., min_length=1, max_length=255)
    # MetaApi/MT5
    meta_api_account_id: Optional[str] = Field(default=None, min_length=10)
    token: Optional[str] = Field(default=None, min_length=20, description="MetaAPI JWT token")
    # Crypto exchanges
    api_key: Optional[str] = Field(default=None, min_length=5, description="Exchange API key (Binance/Bybit)")
    api_secret: Optional[str] = Field(default=None, min_length=5, description="Exchange API secret (Binance/Bybit)")
    risk_pct: float = Field(default=1.0, ge=0.1, le=10.0)
    max_positions: int = Field(default=3, ge=1, le=20)
    run_mode: str = Field(default="LIVE")
    # Account type and prop firm fields
    account_type: str = Field(default="personal")  # personal | evaluation | funded
    prop_firm_name: Optional[str] = Field(default=None)
    evaluation_phase: Optional[str] = Field(default=None)  # phase1 | phase2 | funded
    max_daily_loss_pct: Optional[float] = Field(default=None, ge=0, le=100)
    max_drawdown_pct: Optional[float] = Field(default=None, ge=0, le=100)
    profit_target_usd: Optional[float] = Field(default=None, ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "venue": "metaapi_mt5",
                "name": "FTMO $50K Phase 1",
                "meta_api_account_id": "a09b89c3-cf09-45e7-9125-d95ebc9afe96",
                "token": "eyJ0eXAiOiJKV1Q...",
                "risk_pct": 1.0,
                "max_positions": 3,
                "run_mode": "LIVE",
                "account_type": "evaluation",
                "prop_firm_name": "FTMO",
                "evaluation_phase": "phase1",
                "max_daily_loss_pct": 5.0,
                "max_drawdown_pct": 10.0,
                "profit_target_usd": 5000,
            }
        }
    }

    @model_validator(mode="after")
    def _validate_by_venue(self) -> "BrokerProfileCreate":
        venue = (self.venue or "").strip().lower() or "metaapi_mt5"
        if venue in {"metaapi", "metaapi_mt5", "mt5"}:
            if not (self.meta_api_account_id or "").strip():
                raise ValueError("meta_api_account_id is required for venue=metaapi_mt5")
            if not (self.token or "").strip():
                raise ValueError("token is required for venue=metaapi_mt5")
        elif venue == "ctrader":
            # cTrader uses OAuth connect flow; allow saving profile without credentials.
            # Tokens are stored later via /api/ctrader/oauth/callback.
            pass
        elif venue in {"binance", "bybit"}:
            if not (self.api_key or "").strip() or not (self.api_secret or "").strip():
                raise ValueError("api_key and api_secret are required for venue=binance/bybit")
        else:
            raise ValueError(f"Unsupported venue: {venue}")
        self.venue = venue
        return self

class BrokerProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    # MetaApi/MT5
    meta_api_account_id: Optional[str] = Field(None, min_length=10)
    token: Optional[str] = Field(None, min_length=20)
    # Crypto exchanges
    api_key: Optional[str] = Field(default=None, min_length=5)
    api_secret: Optional[str] = Field(default=None, min_length=5)
    risk_pct: Optional[float] = Field(None, ge=0.1, le=10.0)
    max_positions: Optional[int] = Field(None, ge=1, le=20)
    run_mode: Optional[str] = None
    is_active: Optional[bool] = None          # Deactivate / reactivate account


class BrokerProfileResponse(BaseModel):
    id: int
    name: str
    venue: str
    meta_api_account_id: Optional[str] = None
    token_masked: Optional[str] = None          # Only last chars shown for security
    api_key_masked: Optional[str] = None
    api_secret_masked: Optional[str] = None
    risk_pct: float
    max_positions: int
    run_mode: str
    is_active: bool
    selected_for_trading: bool
    connection_status: str              # unknown | connected | error
    connection_error: Optional[str]
    last_tested_at: Optional[str]
    created_at: Optional[str]
    # Account type metadata
    account_type: str = "personal"
    prop_firm_name: Optional[str] = None
    evaluation_phase: Optional[str] = None
    max_daily_loss_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    profit_target_usd: Optional[float] = None
    consistency_enabled: Optional[bool] = None  # None = use global setting


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    account_name: Optional[str] = None
    server: Optional[str] = None
    balance: Optional[float] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

_SELECT = (
    "id,name,venue,meta_api_account_id,token,api_key,api_secret,risk_pct,max_positions,"
    "run_mode,is_active,selected_for_trading,connection_status,"
    "connection_error,last_tested_at,created_at,"
    # DB column is 'profit_target'; code calls it 'profit_target_usd' — mapped in _to_response
    "evaluation_mode,evaluation_phase,max_daily_loss_pct,max_drawdown_pct,profit_target,"
    "consistency_enabled"
)


def _mask_secret(secret: Optional[str], last: int = 8) -> str:
    """Show only last N chars of a secret for display."""
    if not secret:
        return "***"
    s = str(secret).strip()
    return f"***{s[-last:]}" if len(s) > last else "***"


def _infer_account_type(row: Dict[str, Any]) -> str:
    """Derive account_type string from evaluation_mode + evaluation_phase."""
    if not row.get("evaluation_mode"):
        return "personal"
    phase = row.get("evaluation_phase", "phase1")
    if phase == "funded":
        return "funded"
    return "evaluation"


def _to_response(row: Dict[str, Any]) -> BrokerProfileResponse:
    venue = (row.get("venue") or "metaapi_mt5").strip().lower()
    token_val = (row.get("token") or "").strip()
    return BrokerProfileResponse(
        id=row["id"],
        name=row["name"],
        venue=venue,
        meta_api_account_id=row.get("meta_api_account_id"),
        token_masked=_mask_secret(token_val, last=8) if token_val and venue in {"metaapi", "metaapi_mt5", "mt5", "ctrader"} else None,
        api_key_masked=_mask_secret(row.get("api_key"), last=6) if venue in {"binance", "bybit"} else None,
        api_secret_masked=_mask_secret(row.get("api_secret"), last=4) if venue in {"binance", "bybit"} else None,
        risk_pct=float(row.get("risk_pct") or 1.0),
        max_positions=int(row.get("max_positions") or 3),
        run_mode=(row.get("run_mode") or "LIVE").upper(),
        is_active=bool(row.get("is_active", True)),
        selected_for_trading=bool(row.get("selected_for_trading", False)),
        connection_status=row.get("connection_status") or "unknown",
        connection_error=row.get("connection_error"),
        last_tested_at=row.get("last_tested_at"),
        created_at=row.get("created_at"),
        account_type=_infer_account_type(row),
        prop_firm_name=row.get("prop_firm_name"),
        evaluation_phase=row.get("evaluation_phase"),
        max_daily_loss_pct=row.get("max_daily_loss_pct"),
        max_drawdown_pct=row.get("max_drawdown_pct"),
        profit_target_usd=row.get("profit_target_usd") or row.get("profit_target"),
        consistency_enabled=row.get("consistency_enabled"),  # None | True | False
    )


def _test_metaapi_connection(token: str, account_id: str) -> TestConnectionResponse:
    """
    Call MetaAPI REST to validate token + account_id.
    Returns connection info on success, error details on failure.
    """
    from config import get_settings
    get_settings()  # ensure settings loaded
    # Use the global provisioning endpoint (no region prefix) — same URL the MetaAPI SDK uses.
    # Regional subdomains (e.g. london.agiliumtrade.ai) have SSL cert issues in some environments.
    base_url = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"
    url = f"{base_url}/users/current/accounts/{account_id}"
    try:
        import ssl
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Create an SSL context that skips ALL cert verification.
        # verify=False alone can fail on some Railway Python builds where
        # the system CA bundle enforcement happens below the requests layer.
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        resp = requests.get(
            url,
            headers={"auth-token": token.strip(), "Content-Type": "application/json"},
            timeout=15,
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            return TestConnectionResponse(
                success=True,
                message="Connected successfully",
                account_name=data.get("name"),
                server=data.get("server"),
            )
        elif resp.status_code == 404:
            return TestConnectionResponse(
                success=False,
                message=f"Account ID not found: {account_id}. Check the account ID in MetaAPI cloud.",
            )
        elif resp.status_code == 403:
            return TestConnectionResponse(
                success=False,
                message="Access denied. The token does not have permission for this account.",
            )
        elif resp.status_code == 401:
            return TestConnectionResponse(
                success=False,
                message="Invalid token. Check that you pasted the full MetaAPI JWT token.",
            )
        else:
            try:
                detail = resp.json().get("message", resp.text)
            except Exception:
                detail = resp.text
            return TestConnectionResponse(
                success=False,
                message=f"MetaAPI returned HTTP {resp.status_code}: {detail}",
            )
    except requests.Timeout:
        return TestConnectionResponse(
            success=False,
            message="Connection timed out. MetaAPI may be unreachable from the server.",
        )
    except Exception as exc:
        return TestConnectionResponse(
            success=False,
            message=f"Connection error: {exc}",
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[BrokerProfileResponse])
def list_broker_profiles():
    """List all broker profiles."""
    try:
        sb = _get_supabase()
        resp = (
            sb.table("broker_profiles")
            .select(_SELECT)
            .order("id", desc=False)
            .execute()
        )
        return [_to_response(r) for r in (resp.data or [])]
    except Exception as exc:
        logger.error("list_broker_profiles error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


def _test_binance_connection(api_key: str, api_secret: str) -> TestConnectionResponse:
    """
    Validate Binance API credentials by calling a signed futures endpoint.

    Uses: GET /fapi/v2/account
    """
    ts = int(time.time() * 1000)
    query = urlencode({"timestamp": ts})
    sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"https://fapi.binance.com/fapi/v2/account?{query}&signature={sig}"
    try:
        resp = requests.get(url, headers={"X-MBX-APIKEY": api_key}, timeout=15)
        if resp.status_code == 200:
            data = resp.json() or {}
            bal = None
            try:
                bal = float(data.get("totalWalletBalance")) if data.get("totalWalletBalance") is not None else None
            except (TypeError, ValueError):
                bal = None
            return TestConnectionResponse(
                success=True,
                message="Connected successfully",
                balance=bal,
            )
        return TestConnectionResponse(success=False, message=f"Binance error {resp.status_code}: {resp.text[:120]}")
    except Exception as exc:  # noqa: BLE001
        return TestConnectionResponse(success=False, message=f"Binance connection test failed: {str(exc)[:120]}")


@router.post("", response_model=BrokerProfileResponse, status_code=201)
def create_broker_profile(body: BrokerProfileCreate):
    """Create a new broker profile. Credentials are stored in DB (masked in API responses)."""
    try:
        sb = _get_supabase()
        venue = (body.venue or "metaapi_mt5").strip().lower()
        payload = {
            "name": body.name,
            "venue": venue,
            "meta_api_account_id": (body.meta_api_account_id or "").strip() or None,
            "token": (body.token or "").strip() or None,
            "api_key": (body.api_key or "").strip() or None,
            "api_secret": (body.api_secret or "").strip() or None,
            "token_env_key": "META_API_TOKEN",   # legacy fallback key
            "risk_pct": body.risk_pct,
            "max_positions": body.max_positions,
            "run_mode": body.run_mode.upper(),
            "is_active": True,
            "selected_for_trading": False,
            "connection_status": "unknown",
            # Account type fields
            "evaluation_mode": body.account_type in ("evaluation", "funded"),
            "evaluation_phase": (
                "funded" if body.account_type == "funded"
                else (body.evaluation_phase or "phase1")
            ),
            # These columns are NOT NULL in some DB versions; never send NULL.
            "max_daily_loss_pct": body.max_daily_loss_pct if body.max_daily_loss_pct is not None else 5.0,
            "max_drawdown_pct": body.max_drawdown_pct if body.max_drawdown_pct is not None else 10.0,
            "profit_target": body.profit_target_usd if body.profit_target_usd is not None else 0.0,
        }
        # prop_firm_name is only in some DB versions — add if column exists
        if body.prop_firm_name:
            payload["prop_firm_name"] = body.prop_firm_name

        # Enforce per-venue required fields (defense-in-depth; validator also checks)
        if venue in {"metaapi", "metaapi_mt5", "mt5"}:
            if not payload["meta_api_account_id"] or not payload["token"]:
                raise HTTPException(status_code=422, detail="meta_api_account_id and token are required for metaapi_mt5")
            payload["api_key"] = None
            payload["api_secret"] = None
        elif venue == "ctrader":
            # Persist for later, but disable trading selection until adapter exists.
            payload["meta_api_account_id"] = None
            payload["token"] = None
            payload["api_key"] = None
            payload["api_secret"] = None
            payload["is_active"] = False
            payload["selected_for_trading"] = False
        elif venue in {"binance", "bybit"}:
            if not payload["api_key"] or not payload["api_secret"]:
                raise HTTPException(status_code=422, detail="api_key and api_secret are required for binance/bybit")
            payload["meta_api_account_id"] = None
            payload["token"] = None
        else:
            raise HTTPException(status_code=422, detail=f"Unsupported venue: {venue}")

        resp = _insert_with_unknown_column_retry(sb, "broker_profiles", payload)
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        # Fetch full row (insert might not return all columns)
        full = (
            sb.table("broker_profiles")
            .select(_SELECT)
            .eq("id", rows[0]["id"])
            .limit(1)
            .execute()
        )
        return _to_response((full.data or [rows[0]])[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_broker_profile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{profile_id}", response_model=BrokerProfileResponse)
def update_broker_profile(profile_id: int, body: BrokerProfileUpdate):
    """Update broker profile fields. Only provided fields are updated."""
    try:
        sb = _get_supabase()
        current = (
            sb.table("broker_profiles")
            .select("id, venue")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        cur_rows = current.data or []
        if not cur_rows:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        venue = (cur_rows[0].get("venue") or "metaapi_mt5").strip().lower()

        # Build patch dict from non-None fields only
        patch: Dict[str, Any] = {}
        if body.name is not None:
            patch["name"] = body.name
        if body.meta_api_account_id is not None:
            patch["meta_api_account_id"] = body.meta_api_account_id.strip()
        if body.token is not None:
            patch["token"] = body.token.strip()
            patch["connection_status"] = "unknown"   # reset status on credential change
            patch["connection_error"] = None
            patch["last_tested_at"] = None
        if body.api_key is not None:
            patch["api_key"] = body.api_key.strip()
            patch["connection_status"] = "unknown"
            patch["connection_error"] = None
            patch["last_tested_at"] = None
        if body.api_secret is not None:
            patch["api_secret"] = body.api_secret.strip()
            patch["connection_status"] = "unknown"
            patch["connection_error"] = None
            patch["last_tested_at"] = None
        if body.risk_pct is not None:
            patch["risk_pct"] = body.risk_pct
        if body.max_positions is not None:
            patch["max_positions"] = body.max_positions
        if body.run_mode is not None:
            patch["run_mode"] = body.run_mode.upper()
        if body.is_active is not None:
            patch["is_active"] = body.is_active
            # When deactivating, also unset selected_for_trading to avoid
            # an inactive account being returned as primary credential
            if not body.is_active:
                patch["selected_for_trading"] = False

        # Venue-specific guardrails
        if venue in {"metaapi", "metaapi_mt5", "mt5"}:
            if "api_key" in patch or "api_secret" in patch:
                raise HTTPException(status_code=422, detail="api_key/api_secret updates are not valid for metaapi_mt5 profiles")
        if venue == "ctrader":
            if any(k in patch for k in ("token", "meta_api_account_id", "api_key", "api_secret")):
                raise HTTPException(status_code=422, detail="Credential updates are not supported for ctrader profiles yet")
            if patch.get("selected_for_trading") is True:
                raise HTTPException(status_code=422, detail="ctrader profiles cannot be activated yet")
        if venue in {"binance", "bybit"}:
            if "meta_api_account_id" in patch or "token" in patch:
                raise HTTPException(status_code=422, detail="meta_api_account_id/token updates are not valid for crypto profiles")

        if not patch:
            raise HTTPException(status_code=422, detail="No fields to update")

        sb.table("broker_profiles").update(patch).eq("id", profile_id).execute()
        resp = (
            sb.table("broker_profiles")
            .select(_SELECT)
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        return _to_response(rows[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_broker_profile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{profile_id}", status_code=204)
def delete_broker_profile(profile_id: int):
    """Delete a broker profile permanently."""
    try:
        sb = _get_supabase()
        # Verify it exists first
        check = (
            sb.table("broker_profiles")
            .select("id, selected_for_trading")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = check.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        if rows[0].get("selected_for_trading"):
            raise HTTPException(
                status_code=409,
                detail="Cannot delete the active trading account. Activate another account first.",
            )
        sb.table("broker_profiles").delete().eq("id", profile_id).execute()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_broker_profile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{profile_id}/activate", response_model=BrokerProfileResponse)
def activate_broker_profile(profile_id: int):
    """
    Set this profile as the active trading account.
    Deactivates all other profiles (selected_for_trading = false).
    """
    try:
        sb = _get_supabase()
        # Verify exists
        check = (
            sb.table("broker_profiles")
            .select("id, is_active, venue")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = check.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        if not rows[0].get("is_active", True):
            raise HTTPException(status_code=409, detail="Cannot activate a disabled profile")
        venue = (rows[0].get("venue") or "metaapi_mt5").strip().lower()
        if venue == "ctrader":
            raise HTTPException(
                status_code=409,
                detail="cTrader activation is disabled until execution adapter is implemented.",
            )

        # Deselect all profiles first (bypass unique constraint)
        sb.table("broker_profiles").update({"selected_for_trading": False}).neq("id", 0).execute()
        # Then select only this one
        sb.table("broker_profiles").update({"selected_for_trading": True}).eq("id", profile_id).execute()

        resp = (
            sb.table("broker_profiles")
            .select(_SELECT)
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        return _to_response((resp.data or [])[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("activate_broker_profile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{profile_id}/test", response_model=TestConnectionResponse)
def test_broker_profile_connection(profile_id: int):
    """
    Test broker connectivity for a broker profile.
    Updates connection_status and last_tested_at in DB.
    """
    try:
        sb = _get_supabase()
        # Fetch creds from DB
        resp = (
            sb.table("broker_profiles")
            .select("id, venue, token, meta_api_account_id, token_env_key, api_key, api_secret")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

        row = rows[0]
        venue = (row.get("venue") or "metaapi_mt5").strip().lower()
        if venue in {"metaapi", "metaapi_mt5", "mt5"}:
            token = (row.get("token") or "").strip()
            if not token:
                # Fall back to env var
                env_key = (row.get("token_env_key") or "META_API_TOKEN").strip()
                token = os.environ.get(env_key, "").strip()
            if not token:
                raise HTTPException(
                    status_code=422,
                    detail="No token set for this profile. Add a token before testing.",
                )

            account_id = str(row.get("meta_api_account_id") or "").strip()
            if not account_id:
                raise HTTPException(status_code=422, detail="No MetaAPI account ID set for this profile.")

            result = _test_metaapi_connection(token, account_id)
        elif venue == "binance":
            api_key = (row.get("api_key") or "").strip()
            api_secret = (row.get("api_secret") or "").strip()
            if not api_key or not api_secret:
                raise HTTPException(status_code=422, detail="No Binance api_key/api_secret set for this profile.")
            result = _test_binance_connection(api_key, api_secret)
        elif venue == "bybit":
            # Bybit auth-validation differs by endpoint; implement later.
            result = TestConnectionResponse(success=False, message="Bybit test not implemented yet")
        elif venue == "ctrader":
            result = TestConnectionResponse(success=False, message="cTrader test not implemented yet")
        else:
            raise HTTPException(status_code=422, detail=f"Unsupported venue: {venue}")

        # Persist result to DB
        now = datetime.now(timezone.utc).isoformat()
        update_patch: Dict[str, Any] = {
            "connection_status": "connected" if result.success else "error",
            "last_tested_at": now,
            "connection_error": None if result.success else result.message,
        }
        sb.table("broker_profiles").update(update_patch).eq("id", profile_id).execute()

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("test_broker_profile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
