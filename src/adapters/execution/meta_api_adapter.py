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

    def _get_symbol_price(self, symbol: str) -> tuple[float | None, float | None]:
        """
        Fetch current bid/ask from MetaApi for the given symbol.

        Returns (bid, ask); any failures are logged and return (None, None).
        """
        url = (
            f"{self.BASE_URL}/users/current/accounts/"
            f"{self.account_id}/symbols/{symbol}/current-price"
        )
        try:
            resp = requests.get(url, headers=self._headers(), timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.error("MetaApi _get_symbol_price network error for %s: %s", symbol, exc)
            return None, None

        if resp.status_code != 200:
            logger.error(
                "MetaApi _get_symbol_price failed for %s: HTTP %s %s",
                symbol,
                resp.status_code,
                resp.text[:200],
            )
            return None, None

        try:
            data = resp.json()
        except ValueError:
            logger.error(
                "MetaApi _get_symbol_price invalid JSON for %s: %s",
                symbol,
                resp.text[:200],
            )
            return None, None

        bid = data.get("bid")
        ask = data.get("ask")
        return bid, ask

    @staticmethod
    def _infer_digits(price: float | None, symbol: str) -> int:
        """
        Heuristic to pick decimal digits for rounding SL/TP.
        """
        if price is None:
            # Sensible defaults: 2 for metals/indices, 5 for FX
            sym = symbol.upper()
            if "XAU" in sym or "NAS" in sym or "US30" in sym or "DE40" in sym:
                return 2
            return 5

        txt = f"{price:.10f}".rstrip("0").rstrip(".")
        if "." in txt:
            decs = len(txt.split(".")[1])
            return max(1, min(decs, 5))
        return 2

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

        # ------------------------------------------------------------------
        # Cross-broker relative SL/TP: recompute stops from current bid/ask.
        # ------------------------------------------------------------------
        bid, ask = self._get_symbol_price(request.symbol)
        sl_value: float | None = None
        tp_value: float | None = None

        # Only attempt recalculation when both SL and TP and a reference entry exist
        if request.sl is not None and request.tp is not None and request.entry is not None:
            try:
                sl_dist = abs(float(request.entry) - float(request.sl))
                tp_dist = abs(float(request.entry) - float(request.tp))

                entry_price: float | None = None
                if side == "buy" and ask is not None:
                    entry_price = float(ask)
                    raw_sl = entry_price - sl_dist
                    raw_tp = entry_price + tp_dist
                elif side == "sell" and bid is not None:
                    entry_price = float(bid)
                    raw_sl = entry_price + sl_dist
                    raw_tp = entry_price - tp_dist
                else:
                    entry_price = None

                digits = self._infer_digits(entry_price, request.symbol)
                if entry_price is not None:
                    sl_value = round(raw_sl, digits)
                    tp_value = round(raw_tp, digits)
                    logger.info(
                        "MetaApi recalculated stops for %s %s: entry=%.5f SL=%.5f TP=%.5f "
                        "(dist=%.5f / %.5f, digits=%s)",
                        request.symbol,
                        side,
                        entry_price,
                        sl_value,
                        tp_value,
                        sl_dist,
                        tp_dist,
                        digits,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "MetaApi stop recalculation failed for %s: %s", request.symbol, exc
                )
                sl_value = None
                tp_value = None

        # Fallback: if we couldn't recompute, use raw SL/TP (may still error on broker)
        if sl_value is None and request.sl is not None:
            sl_value = float(request.sl)
        if tp_value is None and request.tp is not None:
            tp_value = float(request.tp)

        payload: Dict[str, Any] = {
            "actionType": action_type,
            "symbol": request.symbol,
            "volume": float(request.size or 0.0),
            "comment": f"AI-Trade-{request.signal_id or request.alert_id}",
        }
        if sl_value is not None:
            payload["stopLoss"] = sl_value
        if tp_value is not None:
            payload["takeProfit"] = tp_value

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
        Close an existing MT5 position via MetaApi.

        For hedging accounts (e.g. FTMO), positionId is required.
        """
        if not request.broker_order_id:
            msg = "MetaApi close_order requires broker_order_id (positionId)"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        side = (request.side or "").lower()
        if side not in {"buy", "sell"}:
            msg = f"Invalid side '{request.side}' for MetaApi close_order"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        # To close a BUY, send a SELL; to close a SELL, send a BUY
        action_type = "ORDER_TYPE_SELL" if side == "buy" else "ORDER_TYPE_BUY"

        payload: Dict[str, Any] = {
            "actionType": action_type,
            "positionId": str(request.broker_order_id),
            "symbol": request.symbol,
            "volume": float(request.size or 0.0),
            "comment": f"AI-Exit-{request.signal_id or request.alert_id}",
        }

        logger.info(
            "MetaApi close_order: client_order_id=%s positionId=%s symbol=%s side=%s size=%s",
            request.client_order_id,
            request.broker_order_id,
            request.symbol,
            request.side,
            request.size,
        )

        try:
            resp = requests.post(
                self._trade_url(),
                json=payload,
                headers=self._headers(),
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("MetaApi close_order network error: %s", exc)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=str(exc),
            )

        if resp.status_code != 200:
            msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("MetaApi close_order failed: %s", msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        try:
            data = resp.json()
        except ValueError:
            msg = f"Invalid JSON response from MetaApi (close): {resp.text[:200]}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        logger.info("MetaApi close_order response: %s", data)
        return ExecutionResult(
            status="filled",
            client_order_id=request.client_order_id,
            broker_order_id=str(request.broker_order_id),
            message="MetaApi position close sent",
        )

