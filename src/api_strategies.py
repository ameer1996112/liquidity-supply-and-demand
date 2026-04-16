"""Strategy Config API (Sprint 4.4).

CRUD + validation for strategy_configs (strategy-as-data).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from src.adapters.supabase_api import get_api_supabase as _get_supabase
from src.services.strategy_config import (
    format_validation_errors,
    validate_strategy_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyCreateBody(BaseModel):
    name: str = Field(..., min_length=1)
    slug: Optional[str] = Field(
        default=None,
        description="URL-friendly identifier; if omitted, derived from name.",
    )
    description: Optional[str] = None
    config: Dict[str, Any]


class StrategyUpdateBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class StrategyValidateBody(BaseModel):
    config: Dict[str, Any]


@router.post("/validate")
def validate_strategy(body: StrategyValidateBody):
    """
    Validate a strategy config without saving.

    Returns 200 with parsed config on success, 400 with error list on failure.
    """
    try:
        cfg = validate_strategy_config(body.config)
        return {"valid": True, "config": cfg.model_dump()}
    except ValidationError as ve:
        return {
            "valid": False,
            "errors": format_validation_errors(ve),
        }


@router.get("")
def list_strategies():
    """List all strategy configs (lightweight listing)."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = (
            sb.table("strategy_configs")
            .select("id, name, slug, is_active, version, created_at, updated_at")
            .order("created_at", desc=True)
            .execute()
        )
        return {"strategies": resp.data or []}
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to list strategies: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_id}")
def get_strategy(strategy_id: int):
    """Get full strategy record including config."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = (
            sb.table("strategy_configs")
            .select("*")
            .eq("id", strategy_id)
            .single()
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return resp.data
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to get strategy %s: %s", strategy_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", status_code=201)
def create_strategy(body: StrategyCreateBody):
    """Create a new strategy after validating its config."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Validate config first
    try:
        cfg = validate_strategy_config(body.config)
    except ValidationError as ve:
        raise HTTPException(
            status_code=400,
            detail={"errors": format_validation_errors(ve)},
        ) from ve

    slug = (body.slug or body.name).strip().lower().replace(" ", "-")
    data = {
        "name": body.name.strip(),
        "slug": slug,
        "description": body.description or "",
        "config": cfg.model_dump(),
        "is_active": False,
        "version": 1,
    }

    try:
        resp = sb.table("strategy_configs").insert(data).execute()
        if not resp.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Slug already exists") from e
        logger.error("Failed to create strategy: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{strategy_id}")
def update_strategy(strategy_id: int, body: StrategyUpdateBody):
    """Update an existing strategy. Config updates are versioned."""
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        current = (
            sb.table("strategy_configs")
            .select("id, name, description, config, version")
            .eq("id", strategy_id)
            .single()
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load strategy %s for update: %s", strategy_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    if not current.data:
        raise HTTPException(status_code=404, detail="Strategy not found")

    row = current.data
    updated: Dict[str, Any] = {}

    if body.name is not None:
        updated["name"] = body.name.strip()
    if body.description is not None:
        updated["description"] = body.description

    if body.config is not None:
        # Validate new config and bump version
        try:
            cfg = validate_strategy_config(body.config)
        except ValidationError as ve:
            raise HTTPException(
                status_code=400,
                detail={"errors": format_validation_errors(ve)},
            ) from ve
        updated["config"] = cfg.model_dump()
        current_version = int(row.get("version") or 1)
        updated["version"] = current_version + 1

    if not updated:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        resp = (
            sb.table("strategy_configs")
            .update(updated)
            .eq("id", strategy_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Strategy not found after update")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to update strategy %s: %s", strategy_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{strategy_id}/activate")
def activate_strategy(strategy_id: int, active: bool = True):
    """
    Activate or deactivate a strategy.
    """
    sb = _get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = (
            sb.table("strategy_configs")
            .update({"is_active": active})
            .eq("id", strategy_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"status": "ok", "id": strategy_id, "is_active": active}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to toggle strategy %s active=%s: %s", strategy_id, active, e)
        raise HTTPException(status_code=500, detail=str(e))
