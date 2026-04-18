from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.services.optimizer_run_service import get_optimizer_run_service
from src.services.optimizer_defaults import DEFAULT_PAIRS

router = APIRouter(prefix="/api/optimizer", tags=["optimizer-runs"])

# ── Agent heartbeat (in-memory) ──────────────────────────────────────────────

_agent_state: dict[str, Any] = {
    "chrome_ready": False,
    "agent_version": None,
    "last_heartbeat": 0.0,
}


class AgentHeartbeatRequest(BaseModel):
    chrome_ready: bool = False
    agent_version: str | None = None


@router.post("/agent/heartbeat")
def agent_heartbeat(payload: AgentHeartbeatRequest) -> dict[str, str]:
    _agent_state["chrome_ready"] = payload.chrome_ready
    _agent_state["agent_version"] = payload.agent_version
    _agent_state["last_heartbeat"] = time.time()
    return {"status": "ok"}


@router.get("/agent/status")
def agent_status() -> dict[str, Any]:
    last = _agent_state["last_heartbeat"]
    agent_online = (time.time() - last) < 60 if last else False
    return {
        "agent_online": agent_online,
        "chrome_ready": _agent_state["chrome_ready"] if agent_online else False,
        "agent_version": _agent_state["agent_version"],
        "last_heartbeat": last if last else None,
    }

@router.get("/pairs")
def list_default_pairs() -> dict[str, Any]:
    return {"pairs": list(DEFAULT_PAIRS)}


class OptimizerRunCreateRequest(BaseModel):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    workers: int = Field(ge=1, le=12)
    pairs: list[str]
    n_trials: int = Field(ge=1, le=1000)
    dd_limit: float = Field(gt=0)
    dry_run: bool = False
    broker: str = Field(min_length=1)

    @field_validator("pairs")
    @classmethod
    def _validate_pairs(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value if item.strip()]
        if not normalized:
            raise ValueError("pairs must not be empty")
        if normalized == ["ALL"]:
            return normalized
        if "ALL" in normalized:
            raise ValueError("pairs cannot include ALL with other symbols")
        for symbol in normalized:
            # Prevent typos like "AUDNZD.GBPNZD" and other separators.
            if "." in symbol or " " in symbol or "/" in symbol:
                raise ValueError(f"invalid symbol: {symbol}")
            if not symbol.isalnum():
                raise ValueError(f"invalid symbol: {symbol}")
        return normalized

    @field_validator("broker")
    @classmethod
    def _validate_broker(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"vantage", "oanda", "fxcm"}:
            raise ValueError("invalid broker")
        return normalized


# ── Run CRUD ─────────────────────────────────────────────────────────────────


@router.get("/runs", response_model=dict[str, Any])
def list_optimizer_runs(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    strategy_id: str | None = Query(None),
    strategy_version: str | None = Query(None),
) -> dict[str, Any]:
    runs = get_optimizer_run_service().list_runs(
        limit=limit,
        status=status,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
    )
    return {"runs": runs}


@router.post("/runs", response_model=dict[str, Any])
def create_optimizer_run(payload: OptimizerRunCreateRequest) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().start_run(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Admin-only route. Return concrete error so operators can fix env/migrations quickly.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=dict[str, Any])
def get_optimizer_run(run_id: str) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc


@router.get("/runs/{run_id}/results", response_model=dict[str, Any])
def get_optimizer_run_results(run_id: str) -> dict[str, Any]:
    service = get_optimizer_run_service()
    try:
        service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc
    return {"results": service.list_results(run_id)}


@router.get("/runs/{run_id}/events", response_model=dict[str, Any])
def get_optimizer_run_events(
    run_id: str,
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    service = get_optimizer_run_service()
    try:
        service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc
    return {"events": service.list_events(run_id, limit=limit)}


@router.post("/runs/{run_id}/cancel", response_model=dict[str, Any])
def cancel_optimizer_run(run_id: str) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().cancel_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Agent write endpoints ────────────────────────────────────────────────────


class AgentRunUpdateRequest(BaseModel):
    status: str | None = None
    summary: dict[str, Any] | None = None


class AgentEventRequest(BaseModel):
    event_type: str
    worker_id: int | None = None
    symbol: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentResultUpdateRequest(BaseModel):
    status: str | None = None
    params: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    error_message: str | None = None


@router.patch("/runs/{run_id}", response_model=dict[str, Any])
def update_optimizer_run(run_id: str, payload: AgentRunUpdateRequest) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().update_run_from_agent(
            run_id, status=payload.status, summary=payload.summary
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc


@router.post("/runs/{run_id}/events", response_model=dict[str, Any])
def push_optimizer_event(run_id: str, payload: AgentEventRequest) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().push_event(run_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc


@router.patch("/runs/{run_id}/results/{symbol}", response_model=dict[str, Any])
def update_optimizer_result(run_id: str, symbol: str, payload: AgentResultUpdateRequest) -> dict[str, Any]:
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        return get_optimizer_run_service().update_result_from_agent(run_id, symbol, updates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc
