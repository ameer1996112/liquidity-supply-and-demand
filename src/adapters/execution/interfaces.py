"""Execution adapter protocol and request/result types."""

from typing import Literal, Optional, Protocol

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    client_order_id: str = Field(..., description="Idempotency key")
    signal_id: Optional[int] = None
    symbol: str = ""
    side: str = ""
    size: float = 0.0
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    alert_id: Optional[int] = None
    rr_ratio: float = 0.0


class CloseRequest(BaseModel):
    client_order_id: str = Field(..., description="Idempotency key")
    signal_id: Optional[int] = None
    symbol: str = ""
    close_price: Optional[float] = None
    outcome: Optional[str] = None
    alert_id: Optional[int] = None
    broker_order_id: Optional[str] = None
    notes: str = ""
    # Additional fields used by some adapters (e.g. MetaApi)
    side: str = ""   # original entry side: "buy" or "sell"
    size: float = 0.0  # volume to close


class ExecutionResult(BaseModel):
    status: Literal["submitted", "rejected", "failed", "filled"] = "submitted"
    broker_order_id: Optional[str] = None
    message: Optional[str] = None
    client_order_id: str = ""
    actual_fill_price: Optional[float] = None  # TCA: Actual fill price from broker


class ExecutionAdapter(Protocol):
    def submit_order(self, request: OrderRequest) -> ExecutionResult: ...
    def close_order(self, request: CloseRequest) -> ExecutionResult: ...
