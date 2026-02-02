"""Live execution: shadow stub (log only, no broker API)."""

import logging

from src.adapters.execution.interfaces import CloseRequest, ExecutionResult, OrderRequest

logger = logging.getLogger(__name__)

LIVE_SHADOW_MESSAGE = "LIVE_SHADOW"


class LiveAdapter:
    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        logger.info("LIVE_SHADOW submit_order: client_order_id=%s symbol=%s side=%s size=%s (no network)", request.client_order_id, request.symbol, request.side, request.size)
        return ExecutionResult(status="submitted", message=LIVE_SHADOW_MESSAGE, client_order_id=request.client_order_id)

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        logger.info("LIVE_SHADOW close_order: client_order_id=%s symbol=%s outcome=%s (no network)", request.client_order_id, request.symbol, request.outcome)
        return ExecutionResult(status="submitted", message=LIVE_SHADOW_MESSAGE, client_order_id=request.client_order_id)
