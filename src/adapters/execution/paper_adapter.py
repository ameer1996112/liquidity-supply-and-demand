"""Paper execution: delegates to PaperTrader."""

import logging
from typing import Any

from src.adapters.execution.interfaces import CloseRequest, ExecutionResult, OrderRequest

logger = logging.getLogger(__name__)


class PaperAdapter:
    def __init__(self, paper_trader: Any) -> None:
        self._pt = paper_trader

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        alert_id = request.alert_id or request.signal_id or 0
        entry = request.entry or 0.0
        sl = request.sl or 0.0
        tp = request.tp or 0.0
        size = request.size or 0.01
        rr_ratio = request.rr_ratio or 0.0
        side = (request.side or "").lower()
        symbol = (request.symbol or "").upper()
        try:
            ok = self._pt.open_position(int(alert_id), symbol, side, float(entry), float(sl), float(tp), float(size), float(rr_ratio))
            if ok:
                return ExecutionResult(status="submitted", broker_order_id=str(alert_id), client_order_id=request.client_order_id)
            return ExecutionResult(status="failed", message="PaperTrader.open_position returned False", client_order_id=request.client_order_id)
        except Exception as e:
            logger.exception("PaperAdapter submit_order failed: %s", e)
            return ExecutionResult(status="failed", message=str(e), client_order_id=request.client_order_id)

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        alert_id = request.alert_id or request.signal_id or 0
        close_price = request.close_price or 0.0
        outcome = request.outcome or "breakeven"
        notes = request.notes or ""
        try:
            pnl = self._pt.close_position(int(alert_id), float(close_price), outcome, notes)
            if pnl is not None:
                return ExecutionResult(status="submitted", client_order_id=request.client_order_id)
            return ExecutionResult(status="failed", message="Position not found", client_order_id=request.client_order_id)
        except Exception as e:
            logger.exception("PaperAdapter close_order failed: %s", e)
            return ExecutionResult(status="failed", message=str(e), client_order_id=request.client_order_id)
