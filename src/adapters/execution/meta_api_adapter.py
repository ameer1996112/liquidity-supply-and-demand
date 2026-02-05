"""MetaApi execution adapter: sends orders to MetaApi REST MT5 bridge."""

from __future__ import annotations

import logging
from typing import Any, Dict

import requests

from src.adapters.execution.interfaces import (
    CloseRequest,
    ExecutionAdapter,
    ExecutionResult,
    OrderRequest,
)

logger = logging.getLogger(__name__)


class MetaApiAdapter:
    """
    Execution adapter that routes orders to a MetaApi MT5 account via HTTP.

    Docs: https://metaapi.cloud/docs/client/restApi/
    """

    BASE_URL = "https://mt-client-api-v1.new-york.agiliumtrade.ai"

    def __init__(self, token: str, account_id: str) -> None:
        self.token = token.strip()
        self.account_id = account_id.strip()

        if not self.token or not self.account_id:
            raise ValueError("MetaApiAdapter requires non-empty token and account_id")

    def _headers(self) -> Dict[str, str]:
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _trade_url(self) -> str:
        return f"{self.BASE_URL}/users/current/accounts/{self.account_id}/trade"

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        """Submit a market order to MetaApi."""
        side = (request.side or "").lower()
        if side not in {"buy", "sell"}:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=f"Invalid side '{request.side}' for MetaApiAdapter",
            )

        action_type = "ORDER_TYPE_BUY" if side == "buy" else "ORDER_TYPE_SELL"

        payload: Dict[str, Any] = {
            "actionType": action_type,
            "symbol": request.symbol,
            "volume": float(request.size or 0.0),
            "stopLoss": request.sl,
            "takeProfit": request.tp,
            "comment": f"AI-Trade-{request.signal_id or request.alert_id}",
        }

        try:
            resp = requests.post(
                self._trade_url(),
                json=payload,
                headers=self._headers(),
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("MetaApi submit_order network error: %s", exc)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=str(exc),
            )

        if resp.status_code != 200:
            msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("MetaApi submit_order failed: %s", msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        try:
            data = resp.json()
        except ValueError:
            msg = f"Invalid JSON response from MetaApi: {resp.text[:200]}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        order_id = data.get("orderId") or data.get("id")
        if not order_id:
            msg = f"MetaApi response missing orderId: {data}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        logger.info(
            "MetaApi order submitted: client_order_id=%s broker_order_id=%s symbol=%s side=%s size=%s",
            request.client_order_id,
            order_id,
            request.symbol,
            request.side,
            request.size,
        )

        return ExecutionResult(
            status="filled",
            broker_order_id=str(order_id),
            client_order_id=request.client_order_id,
            message="MetaApi order filled",
        )

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        """
        Close order is not yet implemented for MetaApi in this adapter.

        You can extend this method to call the appropriate MetaApi close/position
        modification endpoint once your exit workflow is defined.
        """
        logger.warning(
            "MetaApiAdapter.close_order called but not implemented. "
            "client_order_id=%s symbol=%s outcome=%s",
            request.client_order_id,
            request.symbol,
            request.outcome,
        )
        return ExecutionResult(
            status="failed",
            client_order_id=request.client_order_id,
            message="MetaApi close_order not implemented",
        )

