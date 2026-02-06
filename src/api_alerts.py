"""Alerts API -- list, acknowledge, and manage alert rules."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Tables trading_alerts and alert_rules require migrations/004_trading_alerts.sql and 005_alert_rules.sql
_ALERTS_TABLE_MISSING_MSG = "Could not find the table"
_PGRST205 = "PGRST205"


def _is_table_missing(exc: BaseException) -> bool:
    """True if the exception indicates trading_alerts or alert_rules table is missing (migrations not run)."""
    # Supabase/PostgREST can raise with body as dict or message in str(exc)
    msg = str(exc)
    if _ALERTS_TABLE_MISSING_MSG in msg or _PGRST205 in msg:
        return True
    if getattr(exc, "args", None) and len(exc.args) > 0:
        first = exc.args[0]
        if isinstance(first, dict) and (first.get("code") == _PGRST205 or _ALERTS_TABLE_MISSING_MSG in str(first.get("message", ""))):
            return True
        if _ALERTS_TABLE_MISSING_MSG in str(first) or _PGRST205 in str(first):
            return True
    return False

# ── Lazy Supabase client ─────────────────────────────────────

_client = None


def _get_supabase():
    global _client
    if _client is not None:
        return _client
    s = get_settings()
    key = (s.supabase_service_role_key or s.supabase_key or "").strip()
    if not s.supabase_url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    from supabase import create_client

    _client = create_client(s.supabase_url, key)
    return _client


# ── Request / Response Models ────────────────────────────────


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: str
    metadata: Dict[str, Any] = {}
    signal_id: Optional[int] = None
    acknowledged_at: Optional[str] = None
    created_at: str


class AlertsListResponse(BaseModel):
    alerts: List[AlertResponse]
    count: int


class AlertRuleResponse(BaseModel):
    id: int
    rule_type: str
    condition: Dict[str, Any] = {}
    severity: str
    enabled: bool
    created_at: str


class CreateAlertRuleRequest(BaseModel):
    rule_type: str
    condition: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"
    enabled: bool = True


# ── Endpoints ────────────────────────────────────────────────


@router.get("", response_model=AlertsListResponse)
def list_alerts(
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List alerts, optionally filtered by severity and acknowledgment status."""
    sb = _get_supabase()

    query = (
        sb.table("trading_alerts")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )

    if severity:
        query = query.eq("severity", severity)

    if acknowledged is True:
        query = query.not_.is_("acknowledged_at", "null")
    elif acknowledged is False:
        query = query.is_("acknowledged_at", "null")

    try:
        resp = query.execute()
        alerts = resp.data or []
    except Exception as exc:
        if _is_table_missing(exc):
            logger.debug("trading_alerts table not found (run migrations/004_trading_alerts.sql): %s", exc)
            alerts = []
        else:
            logger.error("Failed to fetch alerts: %s", exc)
            alerts = []

    return AlertsListResponse(
        alerts=[AlertResponse(**a) for a in alerts],
        count=len(alerts),
    )


@router.get("/active", response_model=AlertsListResponse)
def list_active_alerts(
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> AlertsListResponse:
    """
    Convenience endpoint for "active" alerts, i.e. not yet acknowledged.

    Mirrors `list_alerts` with `acknowledged=False` and optional severity
    filter so the frontend can simply poll `/alerts/active`.
    """
    return list_alerts(severity=severity, acknowledged=False, limit=limit)

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int):
    """Mark an alert as acknowledged."""
    sb = _get_supabase()

    try:
        resp = (
            sb.table("trading_alerts")
            .update({"acknowledged_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", alert_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Alert not found")
    except HTTPException:
        raise
    except Exception as exc:
        if _is_table_missing(exc):
            raise HTTPException(
                status_code=503,
                detail="Alerts table not available. Run migrations/004_trading_alerts.sql in Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge: {exc}")

    return {"status": "ok", "alert_id": alert_id}


@router.post("/acknowledge_all")
def acknowledge_all_alerts():
    """
    Mark all unacknowledged alerts as acknowledged.

    Used by the frontend `clearAll()` action in the alert bell.
    """
    sb = _get_supabase()

    try:
        sb.table("trading_alerts").update(
            {"acknowledged_at": datetime.now(timezone.utc).isoformat()},
        ).is_("acknowledged_at", "null").execute()
    except Exception as exc:  # pragma: no cover - defensive
        if _is_table_missing(exc):
            raise HTTPException(
                status_code=503,
                detail="Alerts table not available. Run migrations/004_trading_alerts.sql in Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge all: {exc}")

    return {"status": "ok"}


@router.get("/rules")
def list_alert_rules():
    """List all alert rules."""
    sb = _get_supabase()

    try:
        resp = (
            sb.table("alert_rules")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        rules = resp.data or []
    except Exception as exc:
        if _is_table_missing(exc):
            logger.debug("alert_rules table not found (run migrations/005_alert_rules.sql): %s", exc)
            rules = []
        else:
            logger.error("Failed to fetch alert rules: %s", exc)
            rules = []

    return {"rules": rules}


@router.post("/rules")
def create_alert_rule(body: CreateAlertRuleRequest):
    """Create a new alert rule."""
    sb = _get_supabase()

    try:
        resp = (
            sb.table("alert_rules")
            .insert(
                {
                    "rule_type": body.rule_type,
                    "condition": body.condition,
                    "severity": body.severity,
                    "enabled": body.enabled,
                }
            )
            .execute()
        )
        return {"status": "ok", "rule": resp.data[0] if resp.data else None}
    except Exception as exc:
        if _is_table_missing(exc):
            raise HTTPException(
                status_code=503,
                detail="Alert rules table not available. Run migrations/005_alert_rules.sql in Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {exc}")


@router.delete("/rules/{rule_id}")
def delete_alert_rule(rule_id: int):
    """Delete an alert rule."""
    sb = _get_supabase()

    try:
        sb.table("alert_rules").delete().eq("id", rule_id).execute()
    except Exception as exc:
        if _is_table_missing(exc):
            raise HTTPException(
                status_code=503,
                detail="Alert rules table not available. Run migrations/005_alert_rules.sql in Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {exc}")

    return {"status": "ok", "deleted_id": rule_id}
