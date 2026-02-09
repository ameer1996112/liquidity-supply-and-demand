"""Rules Management API — Symbol Risk Rules + RAG Strategy Rules."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])

# ── Shared Supabase client with auto-reconnect ──────────────────

from src.adapters.supabase_api import get_api_supabase as _get_supabase


# ── Pydantic models ──────────────────────────────────────


class SymbolRiskRuleCreate(BaseModel):
    symbol: str = Field(..., min_length=1)
    max_lot_size: float = 1.0
    risk_percent: float = 1.0
    pip_size: float = 0.0001
    pip_value_per_lot: float = 10.0
    max_positions: int = 3
    enabled: bool = True


class SymbolRiskRuleUpdate(BaseModel):
    max_lot_size: Optional[float] = None
    risk_percent: Optional[float] = None
    pip_size: Optional[float] = None
    pip_value_per_lot: Optional[float] = None
    max_positions: Optional[int] = None
    enabled: Optional[bool] = None


class StrategyRuleCreate(BaseModel):
    content: str = Field(..., min_length=5)
    metadata: Dict[str, Any] = Field(default_factory=lambda: {"timeframe": "5m"})


# ── Symbol Risk Rules ────────────────────────────────────


@router.get("/symbols")
def list_symbol_rules():
    sb = _get_supabase()
    result = sb.table("symbol_risk_rules").select("*").order("symbol").execute()
    return {"rules": result.data or [], "count": len(result.data or [])}


@router.post("/symbols", status_code=201)
def create_symbol_rule(body: SymbolRiskRuleCreate):
    sb = _get_supabase()
    data = body.model_dump()
    data["symbol"] = data["symbol"].upper().strip()
    try:
        result = sb.table("symbol_risk_rules").insert(data).execute()
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Symbol {data['symbol']} already exists")
        raise HTTPException(status_code=500, detail=str(e))
    return {"rule": result.data[0] if result.data else data}


@router.put("/symbols/{symbol}")
def update_symbol_rule(symbol: str, body: SymbolRiskRuleUpdate):
    sb = _get_supabase()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = (
        sb.table("symbol_risk_rules")
        .update(updates)
        .eq("symbol", symbol.upper().strip())
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    return {"rule": result.data[0]}


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
