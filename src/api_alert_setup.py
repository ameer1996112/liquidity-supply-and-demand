from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.services.alert_setup_service import get_alert_setup_service

router = APIRouter(prefix="/api/alert-setup", tags=["alert-setup"])

_ALLOWED_CONFIG_STATUSES = {"candidate", "approved", "archived"}
_ALLOWED_BATCH_STATUSES = {"queued", "running", "completed", "failed", "cancelled", "interrupted"}
_ALLOWED_SOURCE_MODES = {"top3", "top5", "approved", "custom"}


class AlertApprovedConfigUpsertRequest(BaseModel):
    pair: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    risk_weight: float = Field(default=1.0, ge=0)
    status: str = "approved"
    source_run_id: str | None = None
    source_score: float | None = None
    source_metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_by: str | None = None

    @field_validator("pair")
    @classmethod
    def _normalize_pair(cls, value: str) -> str:
        pair = value.strip().upper()
        if not pair:
            raise ValueError("pair must not be empty")
        return pair

    @field_validator("timeframe")
    @classmethod
    def _normalize_timeframe(cls, value: str) -> str:
        timeframe = value.strip()
        if not timeframe:
            raise ValueError("timeframe must not be empty")
        return timeframe

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in _ALLOWED_CONFIG_STATUSES:
            raise ValueError(f"invalid config status: {status}")
        return status


class AlertBatchCreateRequest(BaseModel):
    source_mode: Literal["top3", "top5", "approved", "custom"]
    timeframe: str = Field(min_length=1)
    pairs: list[str] = Field(default_factory=list)
    alert_name_prefix: str | None = None
    webhook_url: str | None = None
    use_approved_weights: bool = True
    pair_risk_weights: dict[str, float] = Field(default_factory=dict)
    created_by: str | None = None
    notes: str | None = None

    @field_validator("pairs")
    @classmethod
    def _normalize_pairs(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value if item.strip()]
        if not normalized:
            raise ValueError("pairs must not be empty")
        return normalized

    @field_validator("pair_risk_weights")
    @classmethod
    def _normalize_pair_risk_weights(cls, value: dict[str, float]) -> dict[str, float]:
        return {
            key.strip().upper(): float(weight)
            for key, weight in value.items()
            if key.strip()
        }

    @field_validator("timeframe")
    @classmethod
    def _normalize_timeframe(cls, value: str) -> str:
        timeframe = value.strip()
        if not timeframe:
            raise ValueError("timeframe must not be empty")
        return timeframe


class AlertBatchUpdateRequest(BaseModel):
    status: str | None = None
    summary: dict[str, Any] | None = None

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in _ALLOWED_BATCH_STATUSES:
            raise ValueError(f"invalid batch status: {status}")
        return status


class AlertBatchResultUpdateRequest(BaseModel):
    status: str | None = None
    params: dict[str, Any] | None = None
    config_snapshot: dict[str, Any] | None = None
    alert_name: str | None = None
    alert_id: str | None = None
    error_message: str | None = None


class AlertBatchEventRequest(BaseModel):
    event_type: str
    pair: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def _normalize_event_type(cls, value: str) -> str:
        event_type = value.strip().lower()
        if not event_type:
            raise ValueError("event_type must not be empty")
        return event_type

    @field_validator("pair")
    @classmethod
    def _normalize_pair(cls, value: str | None) -> str | None:
        if value is None:
            return None
        pair = value.strip().upper()
        if not pair:
            raise ValueError("pair must not be empty")
        return pair


@router.get("/approved-configs", response_model=dict[str, Any])
def list_approved_configs(
    limit: int = Query(100, ge=1, le=500),
    status: str | None = Query("approved"),
    pair: str | None = Query(None),
    timeframe: str | None = Query(None),
) -> dict[str, Any]:
    service = get_alert_setup_service()
    try:
        configs = service.list_approved_configs(limit=limit, status=status, pair=pair, timeframe=timeframe)
        return {"configs": configs}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approved-configs", response_model=dict[str, Any])
def upsert_approved_config(payload: AlertApprovedConfigUpsertRequest) -> dict[str, Any]:
    try:
        return get_alert_setup_service().upsert_approved_config(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/batches", response_model=dict[str, Any])
def list_alert_batches(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> dict[str, Any]:
    try:
        batches = get_alert_setup_service().list_batches(limit=limit, status=status)
        return {"batches": batches}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/batches", response_model=dict[str, Any])
def create_alert_batch(payload: AlertBatchCreateRequest) -> dict[str, Any]:
    try:
        return get_alert_setup_service().start_batch(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/batches/{batch_id}", response_model=dict[str, Any])
def get_alert_batch(batch_id: str) -> dict[str, Any]:
    try:
        return get_alert_setup_service().get_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc


@router.get("/batches/{batch_id}/results", response_model=dict[str, Any])
def get_alert_batch_results(batch_id: str) -> dict[str, Any]:
    service = get_alert_setup_service()
    try:
        service.get_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc
    return {"results": service.list_results(batch_id)}


@router.get("/batches/{batch_id}/events", response_model=dict[str, Any])
def get_alert_batch_events(batch_id: str, limit: int = Query(200, ge=1, le=1000)) -> dict[str, Any]:
    service = get_alert_setup_service()
    try:
        service.get_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc
    return {"events": service.list_events(batch_id, limit=limit)}


@router.post("/batches/{batch_id}/cancel", response_model=dict[str, Any])
def cancel_alert_batch(batch_id: str) -> dict[str, Any]:
    try:
        return get_alert_setup_service().cancel_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/batches/{batch_id}", response_model=dict[str, Any])
def update_alert_batch(batch_id: str, payload: AlertBatchUpdateRequest) -> dict[str, Any]:
    try:
        return get_alert_setup_service().update_batch_from_agent(
            batch_id,
            status=payload.status,
            summary=payload.summary,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc


@router.patch("/batches/{batch_id}/results/{pair}", response_model=dict[str, Any])
def update_alert_batch_result(batch_id: str, pair: str, payload: AlertBatchResultUpdateRequest) -> dict[str, Any]:
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        return get_alert_setup_service().update_result_from_agent(batch_id, pair, updates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc


@router.post("/batches/{batch_id}/events", response_model=dict[str, Any])
def push_alert_batch_event(batch_id: str, payload: AlertBatchEventRequest) -> dict[str, Any]:
    try:
        return get_alert_setup_service().push_event(batch_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown alert batch: {batch_id}") from exc
