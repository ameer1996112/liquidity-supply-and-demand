"""MetaApi execution adapter: sends orders to MetaApi REST MT5 bridge."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

from config import get_settings
from src.adapters.execution.interfaces import (
    CloseRequest,
    ExecutionAdapter,
    ExecutionResult,
    OrderRequest,
)

logger = logging.getLogger(__name__)

# Retry: max 3 attempts, backoff 1s then 2s. On 429: open circuit breaker and fail.
MAX_RETRIES = 2
RETRY_BACKOFF = (1.0, 2.0)
RATE_LIMIT_SLEEP = 60


class MetaApiAdapter:
    """
    Execution adapter that routes orders to a MetaApi MT5 account via HTTP.

    Docs: https://metaapi.cloud/docs/client/restApi/
    """

    def __init__(
        self,
        token: str,
        account_id: str,
        account_name: Optional[str] = None,
    ) -> None:
        self.token = token.strip()
        self.account_id = account_id.strip()
        self._account_name_from_config = (account_name or "").strip() or None
        self._account_name_cached: Optional[str] = None

        if not self.token or not self.account_id:
            raise ValueError("MetaApiAdapter requires non-empty token and account_id")

        # Allow region to be configured via settings (META_API_REGION)
        settings = get_settings()
        region = (getattr(settings, "meta_api_region", "new-york") or "new-york").strip()
        self.base_url = f"https://mt-client-api-v1.{region}.agiliumtrade.ai"
        logger.info("MetaApiAdapter using region '%s' (%s)", region, self.base_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _check_circuit_breaker(self) -> bool:
        """True if circuit is open (should not call MetaApi)."""
        try:
            from src.core.circuit_breaker import is_metaapi_circuit_open
            return is_metaapi_circuit_open()
        except Exception:  # noqa: BLE001
            return False

    def _request_with_retry(
        self,
        method: str,
        url: str,
        timeout: int = 10,
        json: Optional[Dict[str, Any]] = None,
    ) -> Optional[requests.Response]:
        """
        GET or POST with retries on timeout/5xx. On 429: open circuit breaker, sleep 60s, return None.
        """
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if method.upper() == "GET":
                    resp = requests.get(url, headers=self._headers(), timeout=timeout)
                else:
                    resp = requests.post(url, headers=self._headers(), json=json, timeout=timeout)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, OSError) as exc:
                last_exc = exc
                logger.warning("MetaApi %s %s attempt %s failed: %s", method, url[:80], attempt + 1, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2)
                continue

            if resp.status_code == 429:
                try:
                    from src.core.circuit_breaker import set_metaapi_circuit_open
                    set_metaapi_circuit_open()
                except Exception:  # noqa: BLE001
                    pass
                logger.warning("MetaApi rate limited (429); circuit breaker opened, sleeping %ss", RATE_LIMIT_SLEEP)
                time.sleep(RATE_LIMIT_SLEEP)
                return None
            if 500 <= resp.status_code < 600 and attempt < MAX_RETRIES:
                logger.warning("MetaApi %s %s HTTP %s; retrying in %.1fs", method, url[:80], resp.status_code, RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2)
                time.sleep(RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2)
                continue
            return resp
        if last_exc:
            logger.error("MetaApi _request_with_retry failed after %s attempts: %s", MAX_RETRIES + 1, last_exc)
        return None

    def _get_symbol_price(self, symbol: str) -> tuple[float | None, float | None]:
        """
        Fetch current bid/ask from MetaApi for the given symbol.

        Returns (bid, ask); any failures are logged and return (None, None).
        """
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/symbols/{symbol}/current-price"
        )
        resp = self._request_with_retry("GET", url, timeout=5)
        if resp is None or resp.status_code != 200:
            if resp is not None:
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

    def get_account_name(self) -> Optional[str]:
        """
        Fetch the account name from MetaApi or use config fallback.

        Tries GET /users/current/accounts/{account_id} first; if name is not
        available, returns the name passed at construction (e.g. from broker_profiles).
        """
        if self._account_name_cached is not None:
            return self._account_name_cached or self._account_name_from_config
        if self._account_name_from_config:
            self._account_name_cached = ""
            return self._account_name_from_config
        if self._check_circuit_breaker():
            return None
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}"
        )
        resp = self._request_with_retry("GET", url, timeout=5)
        if resp is None or resp.status_code != 200:
            self._account_name_cached = ""
            return None
        try:
            data = resp.json()
            name = (
                data.get("name")
                or data.get("accountName")
                or data.get("title")
            )
            if name and isinstance(name, str):
                self._account_name_cached = name.strip()
                return self._account_name_cached
        except (ValueError, TypeError):
            pass
        self._account_name_cached = ""
        return None

    def get_account_information(self) -> Dict[str, Any]:
        """Fetch current account balance/equity from MetaApi.

        Returns dict with at least 'balance' and 'equity' keys (0.0 on failure).
        """
        if self._check_circuit_breaker():
            logger.warning("MetaApi get_account_information skipped: circuit breaker open")
            return {"balance": 0.0, "equity": 0.0}
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/account-information"
        )
        resp = self._request_with_retry("GET", url, timeout=10)
        if resp is None:
            return {"balance": 0.0, "equity": 0.0}
        if resp.status_code != 200:
            logger.error(
                "MetaApi get_account_information failed: HTTP %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return {"balance": 0.0, "equity": 0.0}

        try:
            data = resp.json()
        except ValueError:
            logger.error(
                "MetaApi get_account_information invalid JSON: %s", resp.text[:200]
            )
            return {"balance": 0.0, "equity": 0.0}

        logger.info(
            "MetaApi account info: balance=%.2f equity=%.2f",
            data.get("balance", 0.0),
            data.get("equity", 0.0),
        )
        return data

    def get_open_positions(self) -> list[Dict[str, Any]]:
        """
        Fetch all open positions from MetaAPI.

        Returns:
            List of position dicts with keys:
            - id: Position ID (str)
            - symbol: Trading symbol
            - type: POSITION_TYPE_BUY or POSITION_TYPE_SELL
            - volume: Position size in lots
            - openPrice: Entry price
            - currentPrice: Current market price
            - sl: Stop loss (optional)
            - tp: Take profit (optional)
            - profit: Current unrealized profit in USD
            - swap: Swap charges
            - commission: Commission paid
            - comment: Order comment/EA identifier
            - time: Position open time (ISO 8601)
            - magic: Magic number (MT4/MT5)

        On failure or circuit breaker open, returns empty list [].
        """
        if self._check_circuit_breaker():
            logger.warning("MetaApi get_open_positions skipped: circuit breaker open")
            return []

        url = f"{self.base_url}/users/current/accounts/{self.account_id}/positions"
        resp = self._request_with_retry("GET", url, timeout=10)

        if resp is None:
            logger.error("MetaApi get_open_positions failed: timeout or retries exhausted")
            return []

        if resp.status_code != 200:
            logger.error(
                "MetaApi get_open_positions failed: HTTP %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return []

        try:
            data = resp.json()
            if not isinstance(data, list):
                logger.error("MetaApi get_open_positions: expected list, got %s", type(data).__name__)
                return []

            logger.info(
                "MetaApi get_open_positions: fetched %d positions for account %s",
                len(data),
                self.account_id,
            )
            return data

        except ValueError:
            logger.error(
                "MetaApi get_open_positions invalid JSON: %s", resp.text[:200]
            )
            return []

    def get_account_status(self) -> Dict[str, Any]:
        """
        Fetch enhanced account status including connection info.

        Combines data from:
        - /account-information (balance, equity, margin, etc.)
        - /accounts/{id} (server, platform, connection status)

        Returns:
            Dict with keys:
            - balance, equity, margin, freeMargin, marginLevel
            - server, platform, state, connectionStatus
            - lastSyncTime (added by this method)

        On failure, returns minimal dict with zeros.
        """
        if self._check_circuit_breaker():
            logger.warning("MetaApi get_account_status skipped: circuit breaker open")
            return {
                "balance": 0.0,
                "equity": 0.0,
                "connectionStatus": "circuit_breaker_open",
            }

        # Fetch account info (balance, equity, margin)
        account_info = self.get_account_information()

        # Fetch account details (server, platform, connection)
        account_url = f"{self.base_url}/users/current/accounts/{self.account_id}"
        resp = self._request_with_retry("GET", account_url, timeout=5)

        if resp and resp.status_code == 200:
            try:
                account_details = resp.json()
                # Merge account details into account_info
                account_info["server"] = account_details.get("server", "unknown")
                account_info["platform"] = account_details.get("platform", "unknown")
                account_info["state"] = account_details.get("state", "unknown")
                account_info["connectionStatus"] = account_details.get("connectionStatus", "unknown")
            except ValueError:
                logger.warning("Failed to parse account details JSON")

        # Add timestamp
        from datetime import datetime, timezone
        account_info["lastSyncTime"] = datetime.now(timezone.utc).isoformat()

        return account_info

    def get_historical_deals(self, start_time: str, end_time: str) -> list[Dict[str, Any]]:
        """
        Fetch historical deals (closed trades) from MetaAPI.

        Args:
            start_time: ISO 8601 timestamp (e.g., "2024-01-01T00:00:00Z")
            end_time: ISO 8601 timestamp (e.g., "2024-01-31T23:59:59Z")

        Returns:
            List of deal dicts with keys:
            - id: Deal ID
            - type: DEAL_TYPE_BUY or DEAL_TYPE_SELL
            - entryType: DEAL_ENTRY_IN, DEAL_ENTRY_OUT, etc.
            - symbol: Trading symbol
            - volume: Position size in lots
            - price: Execution price
            - profit: Profit in account currency
            - swap: Swap/rollover
            - commission: Commission
            - time: Deal execution time
            - positionId: Position ID this deal belongs to
            - orderId: Order ID that triggered this deal
        """
        if self._check_circuit_breaker():
            logger.warning("MetaApi get_historical_deals skipped: circuit breaker open")
            return []

        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/history-deals/time/{start_time}/{end_time}"
        )

        resp = self._request_with_retry("GET", url, timeout=30)
        if resp is None:
            logger.warning("MetaApi get_historical_deals: no response")
            return []

        if resp.status_code != 200:
            logger.error(
                "MetaApi get_historical_deals failed: HTTP %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.error(
                "MetaApi get_historical_deals invalid JSON: %s", resp.text[:200]
            )
            return []

        # Response can be a dict with "deals" key, or a list directly
        if isinstance(data, dict):
            deals = data.get("deals") or []
        else:
            deals = data if isinstance(data, list) else []

        logger.info("MetaApi fetched %d historical deals", len(deals))
        return deals

    def _trade_url(self) -> str:
        """Build trade endpoint URL for the configured MetaApi region."""
        return f"{self.base_url}/users/current/accounts/{self.account_id}/trade"

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

        if self._check_circuit_breaker():
            logger.warning("MetaApi submit_order skipped: circuit breaker open")
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message="MetaApi circuit breaker open (rate limit or failures)",
            )
        resp = self._request_with_retry(
            "POST",
            self._trade_url(),
            timeout=10,
            json=payload,
        )
        if resp is None:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message="MetaApi request failed after retries or rate limited",
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

        # TCA: Extract actual fill price from broker response
        # MetaAPI returns price in various fields depending on order type
        fill_price = (
            data.get("openPrice") or  # Position open price
            data.get("price") or       # Alternative price field
            request.entry              # Fallback to requested entry
        )

        logger.info(
            "MetaApi order submitted: client_order_id=%s broker_order_id=%s symbol=%s side=%s size=%s fill_price=%s",
            request.client_order_id,
            order_id,
            request.symbol,
            request.side,
            request.size,
            fill_price,
        )

        account_name = self.get_account_name()

        return ExecutionResult(
            status="filled",
            broker_order_id=str(order_id),
            client_order_id=request.client_order_id,
            message="MetaApi order filled",
            actual_fill_price=float(fill_price) if fill_price else None,
            account_name=account_name,
        )

    def modify_position(
        self, position_id: str, sl: float | None = None, tp: float | None = None
    ) -> ExecutionResult:
        """Modify SL/TP on an existing position via MetaApi POSITION_MODIFY."""
        payload: Dict[str, Any] = {
            "actionType": "POSITION_MODIFY",
            "positionId": position_id,
        }
        if sl is not None:
            payload["stopLoss"] = sl
        if tp is not None:
            payload["takeProfit"] = tp

        resp = self._request_with_retry(
            "POST",
            self._trade_url(),
            timeout=10,
            json=payload,
        )
        if resp is None:
            return ExecutionResult(
                status="failed",
                client_order_id=position_id,
                message="MetaApi request failed after retries or rate limited",
            )
        if resp.status_code != 200:
            msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("MetaApi modify_position failed: %s", msg)
            return ExecutionResult(
                status="failed",
                client_order_id=position_id,
                message=msg,
            )

        logger.info("MetaApi position %s SL/TP modified: sl=%s tp=%s", position_id, sl, tp)
        return ExecutionResult(
            status="filled",
            client_order_id=position_id,
            broker_order_id=position_id,
            message="Position SL/TP modified",
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

        if self._check_circuit_breaker():
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message="MetaApi circuit breaker open",
            )
        resp = self._request_with_retry(
            "POST",
            self._trade_url(),
            timeout=10,
            json=payload,
        )
        if resp is None:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message="MetaApi request failed after retries or rate limited",
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

