"""
Accounts API — Sprint 2.3 multi-account routing foundation.

Routes
------
GET /api/accounts                    List all accounts
GET /api/accounts/{account_id}       Single account detail
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

from src.adapters.supabase_api import get_api_supabase as _get_supabase

# ── Response models ────────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    account_id:          str
    name:                str
    broker_type:         str
    status:              str
    risk_limits:         Dict[str, Any]
    metaapi_account_id:  Optional[str] = None
    tags:                List[str]
    queue_key:           Optional[str] = None
    created_at:          Optional[str] = None
    updated_at:          Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

_SELECT = (
    "account_id,name,broker_type,status,risk_limits,"
    "metaapi_account_id,tags,queue_key,created_at,updated_at"
)


def _to_response(row: Dict[str, Any]) -> AccountResponse:
    return AccountResponse(
        account_id=row["account_id"],
        name=row["name"],
        broker_type=row.get("broker_type", "paper"),
        status=row.get("status", "active"),
        risk_limits=row.get("risk_limits") or {},
        metaapi_account_id=row.get("metaapi_account_id"),
        tags=row.get("tags") or [],
        queue_key=row.get("queue_key"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AccountResponse])
def list_accounts(
    status:       Optional[str] = Query(None, description="Filter by status: active | paused | disabled"),
    broker_type:  Optional[str] = Query(None, description="Filter by broker_type"),
):
    """List all configured trading accounts."""
    try:
        sb = _get_supabase()
        q = (
            sb.table("accounts")
            .select(_SELECT)
            .order("created_at", desc=False)
        )
        if status:
            q = q.eq("status", status)
        if broker_type:
            q = q.eq("broker_type", broker_type)
        resp = q.execute()
        return [_to_response(r) for r in (resp.data or [])]
    except Exception as exc:
        logger.error("list_accounts error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: str):
    """Fetch a single account by account_id."""
    try:
        sb = _get_supabase()
        resp = (
            sb.table("accounts")
            .select(_SELECT)
            .eq("account_id", account_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Account {account_id!r} not found")
        return _to_response(rows[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_account error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
