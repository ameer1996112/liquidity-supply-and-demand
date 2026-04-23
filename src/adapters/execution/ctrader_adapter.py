"""cTrader Open API execution adapter: sends orders via WebSocket JSON protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
import websockets

from config import get_settings
from src.adapters.execution.interfaces import (
    CloseRequest,
    ExecutionResult,
    OrderRequest,
)

logger = logging.getLogger(__name__)

# cTrader Open API payload types (JSON-over-WebSocket)
_APP_AUTH_REQ = 2100
_APP_AUTH_RES = 2101
_ACCOUNT_AUTH_REQ = 2102
_ACCOUNT_AUTH_RES = 2103
_NEW_ORDER_REQ = 2106
_CLOSE_POSITION_REQ = 2111
_TRADER_REQ = 2121
_TRADER_RES = 2122
_RECONCILE_REQ = 2124
_RECONCILE_RES = 2125
_GET_POSITION_UNREALIZED_PNL_REQ = 2187
_GET_POSITION_UNREALIZED_PNL_RES = 2188
_EXECUTION_EVENT = 2126
_ORDER_ERROR_EVENT = 2132

# Order types
_MARKET_ORDER = "MARKET"

# Trade side
_BUY = "BUY"
_SELL = "SELL"

_WS_PORT_JSON = 5036

# OAuth token endpoint
_OAUTH_TOKEN_URL = "https://openapi.ctrader.com/apps/token"


def _msg(payload_type: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "clientMsgId": str(uuid.uuid4()),
        "payloadType": payload_type,
        "payload": payload,
    }


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_iso8601(timestamp_ms: Any) -> Optional[str]:
    timestamp = _to_int(timestamp_ms)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat()


def _money_divisor(money_digits: Any) -> float:
    digits = _to_int(money_digits)
    if digits is None or digits < 0:
        return 1.0
    return float(10 ** digits)


def _scale_money(value: Any, money_digits: Any) -> Optional[float]:
    amount = _to_float(value)
    if amount is None:
        return None
    return amount / _money_divisor(money_digits)


def _refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Exchange refresh token for a fresh access token."""
    s = get_settings()
    client_id = (s.ctrader_client_id or "").strip()
    client_secret = (s.ctrader_client_secret.get_secret_value() if s.ctrader_client_secret else "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Missing CTRADER_CLIENT_ID/CTRADER_CLIENT_SECRET")

    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    r = requests.get(_OAUTH_TOKEN_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("errorCode") or not data.get("accessToken"):
        raise RuntimeError(f"cTrader token refresh error: {data.get('description') or data.get('errorCode')}")
    return data


async def _recv_until(ws, client_msg_id: str, timeout: float = 15) -> Dict[str, Any]:
    """Wait for a response matching our clientMsgId."""
    async def _loop():
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("clientMsgId") == client_msg_id:
                return data
    return await asyncio.wait_for(_loop(), timeout=timeout)


def _extract_error(data: Dict[str, Any]) -> Optional[str]:
    payload = data.get("payload") or {}
    error_code = payload.get("errorCode") or data.get("errorCode")
    description = payload.get("description") or data.get("description")
    if error_code and description:
        return f"{error_code} - {description}"
    if error_code:
        return str(error_code)
    return None


async def _send_authenticated_request(
    host: str,
    access_token: str,
    ctid_trader_account_id: int,
    request_payload: Dict[str, Any],
    *,
    expected_payload_type: int | None = None,
) -> Dict[str, Any]:
    """Connect, authenticate, and send a request on a short-lived WS session."""
    s = get_settings()
    client_id = (s.ctrader_client_id or "").strip()
    client_secret = (s.ctrader_client_secret.get_secret_value() if s.ctrader_client_secret else "").strip()

    url = f"wss://{host}:{_WS_PORT_JSON}"
    ssl_ctx = ssl.create_default_context()

    async with websockets.connect(url, ssl=ssl_ctx, ping_interval=None, close_timeout=5) as ws:
        # 1) App auth
        app_auth = _msg(_APP_AUTH_REQ, {"clientId": client_id, "clientSecret": client_secret})
        await ws.send(json.dumps(app_auth))
        app_res = await _recv_until(ws, app_auth["clientMsgId"], timeout=10)
        if app_res.get("payloadType") != _APP_AUTH_RES or _extract_error(app_res):
            raise RuntimeError(f"cTrader app auth failed: {_extract_error(app_res) or app_res}")

        # 2) Account auth
        acc_auth = _msg(_ACCOUNT_AUTH_REQ, {
            "ctidTraderAccountId": ctid_trader_account_id,
            "accessToken": access_token,
        })
        await ws.send(json.dumps(acc_auth))
        acc_res = await _recv_until(ws, acc_auth["clientMsgId"], timeout=10)
        if acc_res.get("payloadType") != _ACCOUNT_AUTH_RES or _extract_error(acc_res):
            raise RuntimeError(f"cTrader account auth failed: {_extract_error(acc_res) or acc_res}")

        # 3) Send request
        request_msg = _msg(request_payload["payloadType"], request_payload["payload"])
        await ws.send(json.dumps(request_msg))
        response = await _recv_until(ws, request_msg["clientMsgId"], timeout=20)

        if expected_payload_type is not None and response.get("payloadType") != expected_payload_type:
            logger.warning(
                "cTrader request %s returned payloadType=%s (expected %s)",
                request_payload["payloadType"],
                response.get("payloadType"),
                expected_payload_type,
            )

        return response


class CTraderAdapter:
    """
    Execution adapter for cTrader Open API (Spotware).

    Uses JSON-over-WebSocket to submit market orders and close positions.
    Each call opens a short-lived WS connection (auth → order → close).
    """

    def __init__(
        self,
        refresh_token: str,
        ctid_trader_account_id: str,
        account_name: Optional[str] = None,
        is_live: bool = False,
    ) -> None:
        self.refresh_token = refresh_token.strip()
        self.ctid_trader_account_id = int(ctid_trader_account_id)
        self.account_name = (account_name or "").strip() or None
        self.host = "live.ctraderapi.com" if is_live else "demo.ctraderapi.com"

        if not self.refresh_token or not self.ctid_trader_account_id:
            raise ValueError("CTraderAdapter requires refresh_token and ctid_trader_account_id")

    def _get_access_token(self) -> str:
        """Get a fresh access token from the refresh token."""
        data = _refresh_access_token(self.refresh_token)
        # Update stored refresh token if rotated
        new_refresh = (data.get("refreshToken") or "").strip()
        if new_refresh and new_refresh != self.refresh_token:
            self.refresh_token = new_refresh
            self._persist_rotated_token(new_refresh)
        return data["accessToken"]

    def _persist_rotated_token(self, new_token: str) -> None:
        """Best-effort: update DB if refresh token was rotated."""
        try:
            from src.adapters.supabase_api import get_api_supabase
            sb = get_api_supabase()
            sb.table("broker_profiles").update({"token": new_token}).eq(
                "meta_api_account_id", str(self.ctid_trader_account_id)
            ).execute()
        except Exception as exc:
            logger.warning("Failed to persist rotated cTrader refresh token: %s", exc)

    def _run_async(self, coro):
        """Run an async coroutine from sync context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop (e.g. FastAPI) — use a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=30)
        else:
            return asyncio.run(coro)

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        """Submit a market order via cTrader Open API."""
        side = (request.side or "").lower()
        if side not in {"buy", "sell"}:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=f"Invalid side '{request.side}'",
            )

        trade_side = _BUY if side == "buy" else _SELL

        # cTrader volume is in units (lots * 100). E.g. 0.01 lots = 1 unit of volume
        # Actually cTrader uses centiunits: volume = lots * 100 * 100 = lots * 10000?
        # No — cTrader Open API volume is in cents: 1 lot = 100 units (volume=100)
        # Correction: volume units vary. For forex, 1 lot = 100,000 units.
        # cTrader API volume is volume in lots * 100 (centilots).
        # E.g. 0.01 lots → volume = 1 (in centilots)
        volume = int(round(request.size * 100))
        if volume <= 0:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=f"Invalid volume: {request.size}",
            )

        symbol_name = request.symbol.upper()

        payload = {
            "payloadType": _NEW_ORDER_REQ,
            "payload": {
                "symbolName": symbol_name,
                "orderType": _MARKET_ORDER,
                "tradeSide": trade_side,
                "volume": volume,
                "comment": f"AI-Trade-{request.signal_id or request.alert_id or ''}",
            },
        }

        # Add SL/TP if provided (in absolute price)
        if request.sl is not None:
            payload["payload"]["stopLoss"] = round(float(request.sl), 5)
            payload["payload"]["trailingStopLoss"] = False
        if request.tp is not None:
            payload["payload"]["takeProfit"] = round(float(request.tp), 5)

        logger.info(
            "cTrader submit_order %s %s vol=%s SL=%s TP=%s account=%s",
            symbol_name, side, volume,
            request.sl, request.tp,
            self.ctid_trader_account_id,
        )

        try:
            access_token = self._get_access_token()
            result = self._run_async(_send_authenticated_request(
                host=self.host,
                access_token=access_token,
                ctid_trader_account_id=self.ctid_trader_account_id,
                request_payload=payload,
            ))
        except Exception as exc:
            msg = f"cTrader order failed: {exc}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        # Parse response
        res_payload = result.get("payload") or {}
        error_code = res_payload.get("errorCode")
        if error_code:
            msg = f"cTrader error: {error_code} — {res_payload.get('description', '')}"
            logger.error(msg)
            return ExecutionResult(
                status="rejected",
                client_order_id=request.client_order_id,
                message=msg,
            )

        # Extract position/order ID from execution event or response
        position_id = (
            res_payload.get("positionId")
            or res_payload.get("orderId")
            or res_payload.get("position", {}).get("positionId")
            or res_payload.get("order", {}).get("orderId")
        )
        execution_price = res_payload.get("executionPrice") or res_payload.get("order", {}).get("executionPrice")

        logger.info(
            "cTrader submit_order response: positionId=%s executionPrice=%s payload_type=%s",
            position_id, execution_price, result.get("payloadType"),
        )

        return ExecutionResult(
            status="filled" if position_id else "submitted",
            client_order_id=request.client_order_id,
            broker_order_id=str(position_id) if position_id else None,
            actual_fill_price=float(execution_price) if execution_price else None,
            account_name=self.account_name,
            message="cTrader order executed",
        )

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        """Close a position via cTrader Open API."""
        if not request.broker_order_id:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message="cTrader close_order requires broker_order_id (positionId)",
            )

        position_id = int(request.broker_order_id)

        # Volume: close full position. cTrader ClosePositionReq uses volume in centilots.
        # If size is provided, use it; otherwise close full (volume=0 means full close in some APIs).
        volume = int(round(request.size * 100)) if request.size > 0 else 0

        payload = {
            "payloadType": _CLOSE_POSITION_REQ,
            "payload": {
                "positionId": position_id,
            },
        }
        if volume > 0:
            payload["payload"]["volume"] = volume

        logger.info(
            "cTrader close_order: positionId=%s volume=%s account=%s",
            position_id, volume, self.ctid_trader_account_id,
        )

        try:
            access_token = self._get_access_token()
            result = self._run_async(_send_authenticated_request(
                host=self.host,
                access_token=access_token,
                ctid_trader_account_id=self.ctid_trader_account_id,
                request_payload=payload,
            ))
        except Exception as exc:
            msg = f"cTrader close failed: {exc}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        res_payload = result.get("payload") or {}
        error_code = res_payload.get("errorCode")
        if error_code:
            msg = f"cTrader close error: {error_code} — {res_payload.get('description', '')}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        logger.info("cTrader close_order response: %s", res_payload)
        return ExecutionResult(
            status="filled",
            client_order_id=request.client_order_id,
            broker_order_id=str(position_id),
            message="cTrader position closed",
        )

    def get_account_information(self) -> Dict[str, Any]:
        """Fetch trader account information for dashboard snapshots."""
        payload = {
            "payloadType": _TRADER_REQ,
            "payload": {
                "ctidTraderAccountId": self.ctid_trader_account_id,
            },
        }

        try:
            access_token = self._get_access_token()
            result = self._run_async(_send_authenticated_request(
                host=self.host,
                access_token=access_token,
                ctid_trader_account_id=self.ctid_trader_account_id,
                request_payload=payload,
                expected_payload_type=_TRADER_RES,
            ))
        except Exception as exc:
            logger.error("cTrader get_account_information failed: %s", exc)
            return {"balance": 0.0, "equity": 0.0, "platform": "cTrader"}

        payload_data = result.get("payload") or {}
        trader = payload_data.get("trader") or payload_data
        leverage_in_cents = _to_int(trader.get("leverageInCents"))
        money_digits = trader.get("moneyDigits") or payload_data.get("moneyDigits")
        balance = _scale_money(trader.get("balance"), money_digits) or 0.0
        broker_name = trader.get("brokerName") or payload_data.get("brokerName")

        return {
            "balance": balance,
            # ProtoOATrader does not expose equity/free margin directly.
            "equity": balance,
            "margin": None,
            "freeMargin": None,
            "broker": broker_name,
            "server": broker_name,
            "platform": "cTrader",
            "leverage": (leverage_in_cents / 100) if leverage_in_cents is not None else None,
        }

    def _get_unrealized_pnl_by_position(self, access_token: str) -> Dict[str, Dict[str, Optional[float]]]:
        payload = {
            "payloadType": _GET_POSITION_UNREALIZED_PNL_REQ,
            "payload": {
                "ctidTraderAccountId": self.ctid_trader_account_id,
            },
        }

        try:
            result = self._run_async(_send_authenticated_request(
                host=self.host,
                access_token=access_token,
                ctid_trader_account_id=self.ctid_trader_account_id,
                request_payload=payload,
                expected_payload_type=_GET_POSITION_UNREALIZED_PNL_RES,
            ))
        except Exception as exc:
            logger.warning("cTrader unrealized PnL lookup failed: %s", exc)
            return {}

        payload_data = result.get("payload") or {}
        money_digits = payload_data.get("moneyDigits")
        items = payload_data.get("positionUnrealizedPnL") or []
        if not isinstance(items, list):
            logger.warning(
                "cTrader unrealized PnL lookup expected list, got %s",
                type(items).__name__,
            )
            return {}

        pnl_by_position: Dict[str, Dict[str, Optional[float]]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            position_id = str(item.get("positionId") or "")
            if not position_id:
                continue
            pnl_by_position[position_id] = {
                "grossUnrealizedPnL": _scale_money(item.get("grossUnrealizedPnL"), money_digits),
                "netUnrealizedPnL": _scale_money(item.get("netUnrealizedPnL"), money_digits),
            }
        return pnl_by_position

    def get_open_positions(self) -> list[Dict[str, Any]]:
        """Fetch the trader's current open positions."""
        payload = {
            "payloadType": _RECONCILE_REQ,
            "payload": {
                "ctidTraderAccountId": self.ctid_trader_account_id,
            },
        }

        try:
            access_token = self._get_access_token()
            result = self._run_async(_send_authenticated_request(
                host=self.host,
                access_token=access_token,
                ctid_trader_account_id=self.ctid_trader_account_id,
                request_payload=payload,
                expected_payload_type=_RECONCILE_RES,
            ))
        except Exception as exc:
            logger.error("cTrader get_open_positions failed: %s", exc)
            return []

        payload_data = result.get("payload") or {}
        positions = payload_data.get("position") or payload_data.get("positions") or []
        if not isinstance(positions, list):
            logger.warning("cTrader get_open_positions expected list, got %s", type(positions).__name__)
            return []

        pnl_by_position = self._get_unrealized_pnl_by_position(access_token)
        normalized_positions: list[Dict[str, Any]] = []
        for position in positions:
            if not isinstance(position, dict):
                continue

            trade_data = position.get("tradeData") or {}
            money_digits = position.get("moneyDigits") or trade_data.get("moneyDigits") or payload_data.get("moneyDigits")
            raw_volume = trade_data.get("volume") or position.get("volume")
            volume = _to_float(raw_volume)
            position_id = str(position.get("positionId") or trade_data.get("positionId") or "")
            pnl = pnl_by_position.get(position_id, {})

            normalized_positions.append(
                {
                    "id": position_id,
                    "symbol": (
                        position.get("symbolName")
                        or trade_data.get("symbolName")
                        or trade_data.get("symbolId")
                        or position.get("symbolId")
                    ),
                    "type": trade_data.get("tradeSide") or position.get("tradeSide"),
                    "volume": (volume / 100) if volume is not None else None,
                    "openPrice": _to_float(position.get("price") or trade_data.get("price")),
                    "currentPrice": _to_float(position.get("currentPrice")),
                    "sl": _to_float(position.get("stopLoss")),
                    "tp": _to_float(position.get("takeProfit")),
                    "profit": pnl.get("netUnrealizedPnL")
                    if pnl.get("netUnrealizedPnL") is not None
                    else _scale_money(position.get("profit"), money_digits),
                    "grossUnrealizedPnL": pnl.get("grossUnrealizedPnL"),
                    "netUnrealizedPnL": pnl.get("netUnrealizedPnL"),
                    "swap": _scale_money(position.get("swap"), money_digits),
                    "commission": _scale_money(position.get("commission"), money_digits),
                    "usedMargin": _scale_money(position.get("usedMargin"), money_digits),
                    "comment": trade_data.get("comment") or position.get("comment"),
                    "time": _to_iso8601(trade_data.get("openTimestamp") or position.get("openTimestamp")),
                }
            )

        logger.info(
            "cTrader get_open_positions: fetched %d positions for account %s",
            len(normalized_positions),
            self.ctid_trader_account_id,
        )
        return normalized_positions
