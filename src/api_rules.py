"""Rules Management API — Symbol Risk Rules + RAG Strategy Rules."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["rules"])

# ── Shared Supabase client with auto-reconnect ──────────────────

from src.adapters.supabase_api import get_api_supabase as _get_supabase


# ── Pydantic models ──────────────────────────────────────

DEFAULT_MIN_LOT_SIZE = 0.01
DEFAULT_LOT_STEP = 0.01
DEFAULT_STOP_LOSS_BUFFER_PIPS = 1.0
MAX_SAFE_RISK_PERCENT = 2.0
MAX_SAFE_POSITIONS = 10


class SymbolRiskRuleBase(BaseModel):
    max_lot_size: float = Field(default=1.0, gt=0)
    min_lot_size: float = Field(default=DEFAULT_MIN_LOT_SIZE, gt=0)
    lot_step: float = Field(default=DEFAULT_LOT_STEP, gt=0)
    risk_percent: float = Field(default=1.0, gt=0, le=MAX_SAFE_RISK_PERCENT)
    pip_size: float = Field(default=0.0001, gt=0)
    pip_value_per_lot: float = Field(default=10.0, gt=0)
    stop_loss_buffer_pips: float = Field(default=DEFAULT_STOP_LOSS_BUFFER_PIPS, ge=0)
    max_positions: int = Field(default=3, ge=1, le=MAX_SAFE_POSITIONS)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_lot_bounds(self) -> "SymbolRiskRuleBase":
        if self.min_lot_size > self.max_lot_size:
            raise ValueError("min_lot_size cannot exceed max_lot_size")
        return self


class SymbolRiskRuleCreate(SymbolRiskRuleBase):
    symbol: str = Field(..., min_length=1)


class SymbolRiskRuleUpdate(BaseModel):
    max_lot_size: Optional[float] = Field(default=None, gt=0)
    min_lot_size: Optional[float] = Field(default=None, gt=0)
    lot_step: Optional[float] = Field(default=None, gt=0)
    risk_percent: Optional[float] = Field(default=None, gt=0, le=MAX_SAFE_RISK_PERCENT)
    pip_size: Optional[float] = Field(default=None, gt=0)
    pip_value_per_lot: Optional[float] = Field(default=None, gt=0)
    stop_loss_buffer_pips: Optional[float] = Field(default=None, ge=0)
    max_positions: Optional[int] = Field(default=None, ge=1, le=MAX_SAFE_POSITIONS)
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def validate_lot_bounds(self) -> "SymbolRiskRuleUpdate":
        if (
            self.min_lot_size is not None
            and self.max_lot_size is not None
            and self.min_lot_size > self.max_lot_size
        ):
            raise ValueError("min_lot_size cannot exceed max_lot_size")
        return self


class StrategyRuleCreate(BaseModel):
    content: str = Field(..., min_length=5)
    metadata: Dict[str, Any] = Field(default_factory=lambda: {"timeframe": "5m"})


def _normalize_symbol_rule(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    normalized["symbol"] = str(row.get("symbol", "")).upper().strip()
    normalized["min_lot_size"] = float(row.get("min_lot_size") or DEFAULT_MIN_LOT_SIZE)
    normalized["lot_step"] = float(row.get("lot_step") or DEFAULT_LOT_STEP)
    normalized["stop_loss_buffer_pips"] = float(
        row.get("stop_loss_buffer_pips") or DEFAULT_STOP_LOSS_BUFFER_PIPS
    )
    return normalized


def _validate_symbol_rule_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    min_lot_size = float(payload.get("min_lot_size") or DEFAULT_MIN_LOT_SIZE)
    max_lot_size = float(payload.get("max_lot_size") or 0)
    if min_lot_size > max_lot_size:
        raise HTTPException(status_code=422, detail="min_lot_size cannot exceed max_lot_size")
    return payload


# ── Symbol Risk Rules ────────────────────────────────────


@router.get("/symbols")
def list_symbol_rules():
    sb = _get_supabase()
    result = sb.table("symbol_risk_rules").select("*").order("symbol").execute()
    rules = [_normalize_symbol_rule(rule) for rule in (result.data or [])]
    return {"rules": rules, "count": len(rules)}


@router.post("/symbols", status_code=201)
def create_symbol_rule(body: SymbolRiskRuleCreate):
    sb = _get_supabase()
    data = _validate_symbol_rule_payload(body.model_dump())
    data["symbol"] = data["symbol"].upper().strip()
    try:
        result = sb.table("symbol_risk_rules").insert(data).execute()
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Symbol {data['symbol']} already exists")
        raise HTTPException(status_code=500, detail=str(e))
    # Invalidate cache so worker picks up new rule immediately
    try:
        from src.services.redis_cache import invalidate_symbol_rules_cache
        invalidate_symbol_rules_cache()
    except Exception:
        pass
    return {"rule": _normalize_symbol_rule(result.data[0] if result.data else data)}


@router.put("/symbols/{symbol}")
def update_symbol_rule(symbol: str, body: SymbolRiskRuleUpdate):
    sb = _get_supabase()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    existing = (
        sb.table("symbol_risk_rules")
        .select("*")
        .eq("symbol", symbol.upper().strip())
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    merged = {**_normalize_symbol_rule(existing.data[0]), **updates}
    _validate_symbol_rule_payload(merged)
    result = (
        sb.table("symbol_risk_rules")
        .update(updates)
        .eq("symbol", symbol.upper().strip())
        .execute()
    )
    # Invalidate cache
    try:
        from src.services.redis_cache import invalidate_symbol_rules_cache
        invalidate_symbol_rules_cache()
    except Exception:
        pass
    return {"rule": _normalize_symbol_rule(result.data[0])}


@router.delete("/symbols/{symbol}")
def delete_symbol_rule(symbol: str):
    sb = _get_supabase()
    result = (
        sb.table("symbol_risk_rules")
        .delete()
        .eq("symbol", symbol.upper().strip())
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    # Invalidate cache
    try:
        from src.services.redis_cache import invalidate_symbol_rules_cache
        invalidate_symbol_rules_cache()
    except Exception:
        pass
    return {"status": "deleted", "symbol": symbol.upper().strip()}


# ── RAG Strategy Rules ───────────────────────────────────


@router.get("/strategy")
def list_strategy_rules():
    sb = _get_supabase()
    result = sb.table("documents").select("id, content, metadata").execute()
    return {"rules": result.data or [], "count": len(result.data or [])}


@router.post("/strategy", status_code=201)
def create_strategy_rule(body: StrategyRuleCreate):
    try:
        from src.ai.rag_engine import RagEngine

        engine = RagEngine.from_settings()
        engine.ingest_rule(body.content, metadata=body.metadata)
    except Exception as e:
        logger.error("Failed to ingest strategy rule: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)[:200]}")
    return {"status": "ingested"}


@router.delete("/strategy/{rule_id}")
def delete_strategy_rule(rule_id: str):
    sb = _get_supabase()
    result = sb.table("documents").delete().eq("id", rule_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted", "id": rule_id}
