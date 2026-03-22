"""Alerts API -- list, acknowledge, and manage alert rules."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

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

from src.adapters.supabase_api import get_api_supabase as _get_supabase, reset_api_supabase, is_supabase_connection_error


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
    snoozed_until: Optional[str] = None
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
    cooldown_minutes: int = 60
    created_at: str


class CreateAlertRuleRequest(BaseModel):
    rule_type: str
    condition: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"
    enabled: bool = True
    cooldown_minutes: int = 60


class SnoozeAlertRequest(BaseModel):
    hours: int = Field(1, ge=1, le=168)  # 1h to 7 days


class PatchAlertRuleRequest(BaseModel):
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    cooldown_minutes: Optional[int] = None


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
            if is_supabase_connection_error(exc):
                reset_api_supabase()
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
    """Active (unacknowledged, not snoozed) alerts."""
    sb = _get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    query = (
        sb.table("trading_alerts")
        .select("*")
        .is_("acknowledged_at", "null")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if severity:
        query = query.eq("severity", severity)

    try:
        resp = query.execute()
        alerts = resp.data or []
    except Exception as exc:
        if _is_table_missing(exc):
            return AlertsListResponse(alerts=[], count=0)
        if is_supabase_connection_error(exc):
            reset_api_supabase()
        logger.error("Failed to fetch active alerts: %s", exc)
        return AlertsListResponse(alerts=[], count=0)

    # Filter out snoozed alerts in Python (avoids complex PostgREST OR query)
    active = [
        a for a in alerts
        if not a.get("snoozed_until") or a["snoozed_until"] < now_iso
    ]

    return AlertsListResponse(
        alerts=[AlertResponse(**a) for a in active],
        count=len(active),
    )

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


@router.post("/{alert_id}/snooze")
def snooze_alert(alert_id: int, body: SnoozeAlertRequest):
    """Suppress an alert for N hours without acknowledging it."""
    sb = _get_supabase()
    from datetime import timedelta
    until = (datetime.now(timezone.utc) + timedelta(hours=body.hours)).isoformat()
    try:
        resp = (
            sb.table("trading_alerts")
            .update({"snoozed_until": until})
            .eq("id", alert_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Alert not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to snooze: {exc}")
    return {"status": "ok", "alert_id": alert_id, "snoozed_until": until}


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
            if is_supabase_connection_error(exc):
                reset_api_supabase()
            logger.error("Failed to fetch alert rules: %s", exc)
            rules = []

    return {"rules": rules}


@router.patch("/rules/{rule_id}")
def patch_alert_rule(rule_id: int, body: PatchAlertRuleRequest):
    """Toggle enabled, change severity or cooldown_minutes for a rule."""
    sb = _get_supabase()
    updates: Dict[str, Any] = {}
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    if body.severity is not None:
        updates["severity"] = body.severity
    if body.cooldown_minutes is not None:
        updates["cooldown_minutes"] = body.cooldown_minutes
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        resp = (
            sb.table("alert_rules")
            .update(updates)
            .eq("id", rule_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"status": "ok", "rule": resp.data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_table_missing(exc):
            raise HTTPException(status_code=503, detail="Alert rules table not available.")
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {exc}")


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
                    "cooldown_minutes": body.cooldown_minutes,
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
