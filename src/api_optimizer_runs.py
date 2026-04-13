from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.services.optimizer_run_service import get_optimizer_run_service

router = APIRouter(prefix="/api/optimizer/runs", tags=["optimizer-runs"])


class OptimizerRunCreateRequest(BaseModel):
    mode: str = Field(min_length=1)
    workers: int = Field(ge=1, le=12)
    pairs: list[str]
    n_trials: int = Field(ge=1, le=1000)
    dd_limit: float = Field(gt=0)
    dry_run: bool = False

    @field_validator("pairs")
    @classmethod
    def _validate_pairs(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value if item.strip()]
        if not normalized:
            raise ValueError("pairs must not be empty")
        return normalized


@router.get("", response_model=dict[str, Any])
def list_optimizer_runs(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> dict[str, Any]:
    runs = get_optimizer_run_service().list_runs(limit=limit, status=status)
    return {"runs": runs}


@router.post("", response_model=dict[str, Any])
def create_optimizer_run(payload: OptimizerRunCreateRequest) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().start_run(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=dict[str, Any])
def get_optimizer_run(run_id: str) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc


@router.get("/{run_id}/results", response_model=dict[str, Any])
def get_optimizer_run_results(run_id: str) -> dict[str, Any]:
    service = get_optimizer_run_service()
    try:
        service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc
    return {"results": service.list_results(run_id)}


@router.get("/{run_id}/events", response_model=dict[str, Any])
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


@router.post("/{run_id}/cancel", response_model=dict[str, Any])
def cancel_optimizer_run(run_id: str) -> dict[str, Any]:
    try:
        return get_optimizer_run_service().cancel_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown optimizer run: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
