from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from src.adapters.execution.interfaces import CloseRequest, ExecutionResult, OrderRequest


def _ms() -> int:
    return int(time.time() * 1000)


def _sign_query(api_secret: str, query: str) -> str:
    return hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()


@dataclass
class BinanceAdapter:
    api_key: str
    api_secret: str
    account_name: Optional[str] = None
    base_url_spot: str = "https://api.binance.com"
    base_url_futures: str = "https://fapi.binance.com"
    timeout_seconds: int = 10

    def _headers(self) -> Dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    def _request(self, method: str, base_url: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(params)
        params["timestamp"] = _ms()
        query = urlencode(params)
        sig = _sign_query(self.api_secret, query)
        url = f"{base_url}{path}?{query}&signature={sig}"
        r = requests.request(method, url, headers=self._headers(), timeout=self.timeout_seconds)
        r.raise_for_status()
        return r.json()

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        if not self.api_key or not self.api_secret:
            return ExecutionResult(
                status="failed",
                message="BINANCE_MISSING_KEYS",
                client_order_id=request.client_order_id,
            )

        symbol = request.symbol.replace("/", "").upper()
        side = request.side.upper()

        is_futures = bool(request.sl or request.tp)
        base_url = self.base_url_futures if is_futures else self.base_url_spot
        path = "/fapi/v1/order" if is_futures else "/api/v3/order"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "newClientOrderId": request.client_order_id,
            "quantity": str(request.size),
        }

        try:
            data = self._request("POST", base_url, path, params)
            order_id = str(data.get("orderId") or "").strip()
            return ExecutionResult(
                status="submitted",
                broker_order_id=order_id or None,
                message="BINANCE_OK",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                status="failed",
                message=f"BINANCE_ERROR:{str(exc)[:120]}",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        if not self.api_key or not self.api_secret:
            return ExecutionResult(
                status="failed",
                message="BINANCE_MISSING_KEYS",
                client_order_id=request.client_order_id,
            )

        symbol = request.symbol.replace("/", "").upper()
        qty = float(request.size or 0.0)
        if qty <= 0:
            return ExecutionResult(
                status="failed",
                message="BINANCE_CLOSE_MISSING_SIZE",
                client_order_id=request.client_order_id,
            )

        entry_side = (request.side or "").lower()
        if entry_side not in {"buy", "sell"}:
            return ExecutionResult(
                status="failed",
                message="BINANCE_CLOSE_MISSING_SIDE",
                client_order_id=request.client_order_id,
            )

        close_side = "SELL" if entry_side == "buy" else "BUY"

        base_url = self.base_url_futures
        path = "/fapi/v1/order"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": str(qty),
            "newClientOrderId": request.client_order_id,
            "reduceOnly": "true",
        }

        try:
            data = self._request("POST", base_url, path, params)
            order_id = str(data.get("orderId") or "").strip()
            return ExecutionResult(
                status="submitted",
                broker_order_id=order_id or None,
                message="BINANCE_CLOSE_OK",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                status="failed",
                message=f"BINANCE_CLOSE_ERROR:{str(exc)[:120]}",
                client_order_id=request.client_order_id,
                account_name=self.account_name,
            )

