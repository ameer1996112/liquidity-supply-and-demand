from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from src.adapters.execution.interfaces import CloseRequest, ExecutionResult, OrderRequest


def _ms() -> int:
    return int(time.time() * 1000)


def _bybit_sign(api_secret: str, payload: str) -> str:
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


@dataclass
class BybitAdapter:
    api_key: str
    api_secret: str
    account_name: Optional[str] = None
    base_url: str = "https://api.bybit.com"
    recv_window: int = 5000
    timeout_seconds: int = 10

    def _headers(self, ts_ms: int, body: str) -> Dict[str, str]:
        payload = f"{ts_ms}{self.api_key}{self.recv_window}{body}"
        sig = _bybit_sign(self.api_secret, payload)
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": str(ts_ms),
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "X-BAPI-SIGN": sig,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        ts = _ms()
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        url = f"{self.base_url}{path}"
        r = requests.post(
            url,
            headers=self._headers(ts, body_str),
            data=body_str,
            timeout=self.timeout_seconds,
        )
        r.raise_for_status()
        return r.json()

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        if not self.api_key or not self.api_secret:
            return ExecutionResult(
                status="failed",
                message="BYBIT_MISSING_KEYS",
                client_order_id=request.client_order_id,
            )

        symbol = request.symbol.replace("/", "").upper()
        side = "Buy" if request.side.lower() == "buy" else "Sell"

        category = "linear" if (request.sl or request.tp) else "spot"

        body: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(request.size),
            "timeInForce": "IOC",
            "orderLinkId": request.client_order_id,
        }

        if category == "linear":
            if request.tp:
                body["takeProfit"] = str(request.tp)
            if request.sl:
                body["stopLoss"] = str(request.sl)

        try:
            data = self._post("/v5/order/create", body)
            result = data.get("result") or {}
            order_id = str(result.get("orderId") or "").strip()
            return ExecutionResult(
                status="submitted",
                broker_order_id=order_id or None,
                message="BYBIT_OK",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                status="failed",
                message=f"BYBIT_ERROR:{str(exc)[:120]}",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        if not self.api_key or not self.api_secret:
            return ExecutionResult(
                status="failed",
                message="BYBIT_MISSING_KEYS",
                client_order_id=request.client_order_id,
            )

        symbol = request.symbol.replace("/", "").upper()
        qty = float(request.size or 0.0)
        if qty <= 0:
            return ExecutionResult(
                status="failed",
                message="BYBIT_CLOSE_MISSING_SIZE",
                client_order_id=request.client_order_id,
            )

        entry_side = (request.side or "").lower()
        if entry_side not in {"buy", "sell"}:
            return ExecutionResult(
                status="failed",
                message="BYBIT_CLOSE_MISSING_SIDE",
                client_order_id=request.client_order_id,
            )

        close_side = "Sell" if entry_side == "buy" else "Buy"

        body: Dict[str, Any] = {
            "category": "linear",
            "symbol": symbol,
            "side": close_side,
            "orderType": "Market",
            "qty": str(qty),
            "timeInForce": "IOC",
            "reduceOnly": True,
            "orderLinkId": request.client_order_id,
        }

        try:
            data = self._post("/v5/order/create", body)
            result = data.get("result") or {}
            order_id = str(result.get("orderId") or "").strip()
            return ExecutionResult(
                status="submitted",
                broker_order_id=order_id or None,
                message="BYBIT_CLOSE_OK",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                status="failed",
                message=f"BYBIT_CLOSE_ERROR:{str(exc)[:120]}",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )

