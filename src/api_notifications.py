"""
Notification settings API — DEV-73.

Endpoints:
  GET  /api/notifications/routing          — list routing rules
  PATCH /api/notifications/routing/{type}  — update a routing rule
  GET  /api/notifications/whitelist        — list whitelisted users
  POST /api/notifications/whitelist        — add a user
  DELETE /api/notifications/whitelist/{id} — remove a user
  GET  /api/notifications/commands         — command audit log
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.adapters.supabase_api import get_api_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ─── Routing ─────────────────────────────────────────────────────────────────

@router.get("/routing")
def get_routing():
    sb = get_api_supabase()
    resp = sb.table("notification_routing").select("*").order("alert_type").execute()
    return resp.data or []


class RoutingUpdate(BaseModel):
    discord_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    discord_channel: Optional[str] = None  # 'signals' | 'alerts'


@router.patch("/routing/{alert_type}")
def update_routing(alert_type: str, body: RoutingUpdate):
    sb = get_api_supabase()
    update: dict = {}
    if body.discord_enabled is not None:
        update["discord_enabled"] = body.discord_enabled
    if body.telegram_enabled is not None:
        update["telegram_enabled"] = body.telegram_enabled
    if body.discord_channel is not None:
        if body.discord_channel not in ("signals", "alerts"):
            raise HTTPException(status_code=400, detail="discord_channel must be 'signals' or 'alerts'")
        update["discord_channel"] = body.discord_channel
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    update["updated_at"] = "now()"
    resp = (
        sb.table("notification_routing")
        .update(update)
        .eq("alert_type", alert_type)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"Routing rule '{alert_type}' not found")
    return resp.data[0]


