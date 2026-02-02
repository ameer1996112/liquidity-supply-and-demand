"""Dry-run execution: log only, no orders."""

import logging

from src.adapters.execution.interfaces import CloseRequest, ExecutionResult, OrderRequest

logger = logging.getLogger(__name__)

DRY_RUN_MESSAGE = "DRY_RUN"


class DryRunAdapter:
    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        logger.info(
            "DRY_RUN submit_order: client_order_id=%s symbol=%s side=%s size=%s",
            request.client_order_id, request.symbol, request.side, request.size,
        )
        return ExecutionResult(status="submitted", message=DRY_RUN_MESSAGE, client_order_id=request.client_order_id)

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        logger.info("DRY_RUN close_order: client_order_id=%s symbol=%s outcome=%s", request.client_order_id, request.symbol, request.outcome)
        return ExecutionResult(status="submitted", message=DRY_RUN_MESSAGE, client_order_id=request.client_order_id)
