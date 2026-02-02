"""Execution layer: adapters and router for DRY_RUN, PAPER, LIVE."""

from src.adapters.execution.interfaces import (
    CloseRequest,
    ExecutionAdapter,
    ExecutionResult,
    OrderRequest,
)
from src.adapters.execution.router import get_adapter

__all__ = [
    "CloseRequest",
    "ExecutionAdapter",
    "ExecutionResult",
    "OrderRequest",
    "get_adapter",
]
