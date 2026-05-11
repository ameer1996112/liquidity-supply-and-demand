"""MetaApi execution adapter: sends orders to MetaApi REST MT5 bridge."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from config import get_settings
from src.adapters.execution.interfaces import (
    CloseRequest,
    ExecutionResult,
    OrderRequest,
)
from src.services.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)

# Retry: max 4 attempts for timeouts/5xx (e.g. MT5 wake-up). On 429: open circuit breaker.
MAX_RETRIES = 4
RETRY_BACKOFF = (1.0, 3.0, 5.0, 10.0)
RATE_LIMIT_SLEEP = 60

# HTTP 504 "account not connected to broker / wrong region" requires longer waits because
# MetaAPI needs time to re-establish the MT5 terminal connection (can take 30-120s).
# We use a separate, slower backoff schedule and fewer retries to avoid hammering the API
# during broker-disconnect events. After exhausting these retries we open the circuit
# breaker for BROKER_DISCONNECT_CB_TTL seconds so polling loops back off gracefully.
MAX_RETRIES_BROKER_DISCONNECT = 2  # 3 total attempts: 0, 1, 2
RETRY_BACKOFF_BROKER_DISCONNECT = (15.0, 30.0)  # 45s cumulative before giving up
BROKER_DISCONNECT_CB_TTL = 120  # seconds — 2-min cool-off before next poll wave
BROKER_DISCONNECT_CB_TTL_WEEKEND = 600  # 10-min cool-off on weekends (markets closed)


def _is_forex_weekend() -> bool:
    """True if forex markets are closed (Friday 22:00 UTC → Sunday 21:00 UTC)."""
    now = datetime.now(timezone.utc)
    wd, hr = now.weekday(), now.hour
    if wd == 4 and hr >= 22:  # Friday after 22:00 UTC
        return True
    if wd == 5:  # All Saturday
        return True
    if wd == 6 and hr < 21:  # Sunday before 21:00 UTC
        return True
    return False


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
        region: Optional[str] = None,
    ) -> None:
        self.token = token.strip()
        self.account_id = account_id.strip()
        self._account_name_from_config = (account_name or "").strip() or None
        self._account_name_cached: Optional[str] = None
        self._name_fetched_from_api: bool = False  # OPT-3: permanent cache sentinel
        self.last_positions_fetch_error: Optional[str] = None

        if not self.token or not self.account_id:
            raise ValueError("MetaApiAdapter requires non-empty token and account_id")

        # Allow region to be configured explicitly or via settings (META_API_REGION)
        settings = get_settings()
        effective_region = (region or getattr(settings, "meta_api_region", "new-york") or "new-york").strip()
        self.base_url = f"https://mt-client-api-v1.{effective_region}.agiliumtrade.ai"
        logger.info("MetaApiAdapter using region '%s' (%s)", effective_region, self.base_url)

    def _circuit_breaker_account_key(self) -> str:
        """Stable per-account circuit-breaker key."""
        return self._account_name_from_config or self.account_id

    def _headers(self) -> Dict[str, str]:
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _check_circuit_breaker(self) -> bool:
        """True if circuit is open (should not call MetaApi)."""
        try:
            from src.core.circuit_breaker import is_metaapi_circuit_open
            # Check per-account first, then fall back to global.
            # Using account_name scopes the breaker so one bad account
            # doesn't block all other accounts.
            acct = self._circuit_breaker_account_key()
            return is_metaapi_circuit_open(account_name=acct)
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

        504 "broker not connected / wrong region" uses a separate slower backoff schedule
        (15s, 30s) because MetaAPI needs time to re-establish the MT5 terminal connection.
        After exhausting 504 retries the circuit breaker is opened for 2 minutes to prevent
        polling loops from hammering MetaAPI during broker-disconnect events.
        """
        last_exc = None
        broker_disconnect_attempt = 0  # separate counter for 504 retries

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
                    # Scope to per-account so other accounts are not blocked
                    acct = self._circuit_breaker_account_key()
                    set_metaapi_circuit_open(account_name=acct)
                except Exception:  # noqa: BLE001
                    pass
                logger.warning("MetaApi rate limited (429); circuit breaker opened, sleeping %ss", RATE_LIMIT_SLEEP)
                time.sleep(RATE_LIMIT_SLEEP)

            if resp.status_code == 401:
                logger.error("MetaApi authentication failed (401 Unauthorized for account %s). Check MetaAPI token.", self.account_id)
                raise PermissionError("METAAPI_AUTH_FAILED")

            # 504: broker not connected yet OR wrong region — needs slow back-off
            if resp.status_code == 504:
                if broker_disconnect_attempt < MAX_RETRIES_BROKER_DISCONNECT:
                    wait = RETRY_BACKOFF_BROKER_DISCONNECT[broker_disconnect_attempt] if broker_disconnect_attempt < len(RETRY_BACKOFF_BROKER_DISCONNECT) else 30.0
                    logger.warning(
                        "MetaApi %s %s HTTP 504 (broker not connected / region mismatch); "
                        "attempt %s/%s, retrying in %.0fs. "
                        "If persistent, verify META_API_REGION matches account region.",
                        method, url[:80], broker_disconnect_attempt + 1, MAX_RETRIES_BROKER_DISCONNECT, wait,
                    )
                    broker_disconnect_attempt += 1
                    time.sleep(wait)
                    continue
                else:
                    # All 504 retries exhausted — open circuit breaker to stop poll flooding
                    is_weekend = _is_forex_weekend()
                    cb_ttl = BROKER_DISCONNECT_CB_TTL_WEEKEND if is_weekend else BROKER_DISCONNECT_CB_TTL
                    if is_weekend:
                        logger.info(
                            "MetaApi %s %s HTTP 504 during weekend (expected — forex markets closed). "
                            "Account %s. Circuit breaker opened for %ss.",
                            method, url[:80], self.account_id, cb_ttl,
                        )
                    else:
                        logger.error(
                            "MetaApi %s %s HTTP 504 persisted after %s retries (account %s). "
                            "Opening circuit breaker for %ss. "
                            "Check: (1) META_API_REGION env var matches account region, "
                            "(2) broker terminal is online in MetaAPI dashboard.",
                            method, url[:80], MAX_RETRIES_BROKER_DISCONNECT + 1,
                            self.account_id, cb_ttl,
                        )
                    try:
                        from src.core.circuit_breaker import set_metaapi_circuit_open
                        set_metaapi_circuit_open(
                            ttl_seconds=cb_ttl,
                            account_name=self._circuit_breaker_account_key(),
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    # Only fire alert on non-weekend disconnects (weekends are expected)
                    if not is_weekend:
                        self._send_broker_disconnect_alert("504_broker_not_connected")
                    return resp

            if 500 <= resp.status_code < 600 and resp.status_code != 504 and attempt < MAX_RETRIES:
                logger.warning("MetaApi %s %s HTTP %s; retrying in %.1fs", method, url[:80], resp.status_code, RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2)
                time.sleep(RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2)
                continue
            return resp
        if last_exc:
            logger.error("MetaApi _request_with_retry failed after %s attempts: %s", MAX_RETRIES + 1, last_exc)
            self._send_broker_disconnect_alert("connection_exhausted")
        return None

    def _send_broker_disconnect_alert(self, reason: str) -> None:
        """Fire a Telegram/Discord alert when broker connection fails."""
        try:
            from src.services.alert_service import AlertService, TelegramAlertNotifier, DiscordAlertNotifier

            settings = get_settings()
            notifiers = []
            if settings.telegram_bot_token and settings.telegram_chat_id:
                notifiers.append(TelegramAlertNotifier())
            if getattr(settings, "discord_alerts_webhook_url", None):
                notifiers.append(DiscordAlertNotifier())

            if not notifiers:
                return

            from src.adapters.supabase import get_supabase
            sb = get_supabase()
            svc = AlertService(sb, notifiers=notifiers)
            svc.create_alert(
                alert_type="broker_disconnect",
                severity="critical",
                title="Broker Disconnected",
                message=(
                    f"MetaAPI connection to broker failed ({reason}). "
                    f"Account: {self.account_id[:12]}... "
                    f"Circuit breaker opened for {BROKER_DISCONNECT_CB_TTL}s. "
                    f"Check MetaAPI dashboard."
                ),
                metadata={
                    "account_id": self.account_id,
                    "account_name": self._account_name_from_config,
                    "reason": reason,
                },
                dedupe_minutes=10,
            )
        except Exception as exc:
            logger.debug("Failed to send broker disconnect alert: %s", exc)

    def _get_symbol_price(self, symbol: str) -> tuple[float | None, float | None]:
        """
        Fetch current bid/ask from MetaApi for the given symbol.

        Returns (bid, ask); any failures are logged and return (None, None).
        """
        # Translate to broker symbol (e.g. GBPUSD -> GBPUSD.raw for ACG-DEMO)
        broker_symbol = SymbolMapper.to_broker_symbol(symbol)
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/symbols/{broker_symbol}/current-price"
        )
        resp = self._request_with_retry("GET", url, timeout=10)
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

    def get_symbol_specification(self, symbol: str) -> Dict[str, Any] | None:
        """
        Fetch full symbol specification from MetaAPI broker.

        Returns dict with broker-specific data:
        - minVolume: Minimum lot size (e.g. 0.01)
        - maxVolume: Maximum lot size
        - volumeStep: Lot step (e.g. 0.01)
        - contractSize: Units per lot (100000 for forex, 100 for gold)
        - digits: Price decimal places
        - pipSize: Pip size in price terms (e.g. 0.0001 for EURUSD)
        - tickSize: Minimum price increment
        - spread: Current spread in points (if available)

        Returns None on failure.
        """
        if self._check_circuit_breaker():
            return None
        broker_symbol = SymbolMapper.to_broker_symbol(symbol)
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/symbols/{broker_symbol}/specification"
        )
        resp = self._request_with_retry("GET", url, timeout=10)
        if resp is None or resp.status_code != 200:
            if resp is not None:
                logger.warning(
                    "MetaApi get_symbol_specification failed for %s: HTTP %s %s",
                    symbol, resp.status_code, resp.text[:200],
                )
            return None
        try:
            data = resp.json()
            logger.debug(
                "MetaApi spec for %s: contractSize=%s minVol=%s volStep=%s digits=%s",
                symbol, data.get("contractSize"), data.get("minVolume"),
                data.get("volumeStep"), data.get("digits"),
            )
            return data
        except ValueError:
            logger.error("MetaApi get_symbol_specification invalid JSON for %s", symbol)
            return None

    def get_symbol_spread(self, symbol: str) -> float | None:
        """
        Get current spread in price terms (ask - bid) from broker.

        Returns spread as a float (e.g. 0.00012 for EURUSD) or None on failure.
        """
        bid, ask = self._get_symbol_price(symbol)
        if bid is not None and ask is not None and ask >= bid:
            spread = ask - bid
            logger.debug("Spread for %s: %.5f (bid=%.5f ask=%.5f)", symbol, spread, bid, ask)
            return spread
        return None

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
        Return the account name, cached permanently after first successful fetch.

        Uses config name if provided. Falls back to MetaApi API lookup on first call.
        Result (even empty string) is cached forever — account name never changes.
        """
        # Return config-provided name immediately (never an API call)
        if self._account_name_from_config:
            return self._account_name_from_config

        # Already fetched from API ("" means API returned nothing)
        # Use a private _name_fetched_from_api flag so we never re-fetch
        if getattr(self, "_name_fetched_from_api", False):
            return self._account_name_cached or None

        # First-time API fetch
        if self._check_circuit_breaker():
            return None
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}"
        )
        resp = self._request_with_retry("GET", url, timeout=10)
        self._name_fetched_from_api = True  # never fetch again regardless of outcome
        if resp is not None and resp.status_code == 200:
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
            return {
                "balance": 0.0,
                "equity": 0.0,
                "connectionStatus": "circuit_breaker_open",
            }
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/account-information"
        )
        resp = self._request_with_retry("GET", url, timeout=30)
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
            self.last_positions_fetch_error = "circuit_breaker_open"
            logger.warning("MetaApi get_open_positions skipped: circuit breaker open")
            return []

        self.last_positions_fetch_error = None
        url = f"{self.base_url}/users/current/accounts/{self.account_id}/positions"
        resp = self._request_with_retry("GET", url, timeout=30)

        if resp is None:
            self.last_positions_fetch_error = "request_failed"
            logger.error("MetaApi get_open_positions failed: timeout or retries exhausted")
            return []

        if resp.status_code != 200:
            self.last_positions_fetch_error = f"http_{resp.status_code}"
            logger.error(
                "MetaApi get_open_positions failed: HTTP %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return []

        try:
            data = resp.json()
            if not isinstance(data, list):
                self.last_positions_fetch_error = "invalid_payload"
                logger.error("MetaApi get_open_positions: expected list, got %s", type(data).__name__)
                return []

            logger.info(
                "MetaApi get_open_positions: fetched %d positions for account %s",
                len(data),
                self.account_id,
            )
            return data

        except ValueError:
            self.last_positions_fetch_error = "invalid_json"
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
        if self._check_circuit_breaker():
            account_info["connectionStatus"] = "circuit_breaker_open"
            account_info["lastSyncTime"] = datetime.now(timezone.utc).isoformat()
            return account_info

        # Fetch account details (server, platform, connection)
        account_url = f"{self.base_url}/users/current/accounts/{self.account_id}"
        resp = self._request_with_retry("GET", account_url, timeout=10)

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

    def _ensure_symbol_subscribed(self, broker_symbol: str) -> None:
        """Subscribe a symbol in the MetaAPI cloud terminal's Market Watch.

        MetaAPI cloud terminals only recognise symbols they have subscribed.
        New symbols (e.g. NAS100.raw) cause ERR_MARKET_UNKNOWN_SYMBOL (4301)
        if they were never added. This call is best-effort: failure is logged
        but does not block the order attempt.
        """
        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/subscriptions/{broker_symbol}"
        )
        try:
            resp = requests.put(
                url,
                headers=self._headers(),
                json={"subscriptions": [{"type": "quotes"}]},
                timeout=5,
            )
            if resp.status_code in (200, 201, 204):
                logger.info("Symbol subscribed in MetaAPI Market Watch: %s", broker_symbol)
            else:
                logger.debug(
                    "Symbol subscription for %s returned HTTP %s: %s",
                    broker_symbol, resp.status_code, resp.text[:200],
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Symbol subscription attempt failed for %s: %s", broker_symbol, exc)

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        """Submit a market order to MetaApi.

        Fast path: order is submitted immediately using signal SL/TP distances
        without a blocking price pre-fetch. MetaApi resolves the market price
        at fill time. This removes ~100–300 ms of serial HTTP latency.
        """
        side = (request.side or "").lower()
        if side not in {"buy", "sell"}:
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=f"Invalid side '{request.side}' for MetaApiAdapter",
            )

        action_type = "ORDER_TYPE_BUY" if side == "buy" else "ORDER_TYPE_SELL"

        # ✅ v5.1: Translate TradingView symbol to broker symbol
        broker_symbol = SymbolMapper.to_broker_symbol(request.symbol)
        if broker_symbol != request.symbol:
            logger.info(
                "Symbol translated: %s -> %s (broker-specific)",
                request.symbol, broker_symbol
            )

        # Ensure symbol is subscribed in MetaAPI cloud terminal's Market Watch.
        # MetaAPI cloud terminals only trade symbols they have subscribed; new
        # symbols (e.g. NAS100.raw) cause ERR_MARKET_UNKNOWN_SYMBOL (4301) if
        # they were never added. This is a best-effort call — failure is logged
        # but does not block the order.
        self._ensure_symbol_subscribed(broker_symbol)

        # ------------------------------------------------------------------
        # OPT-1 (latency): Use signal SL/TP values directly — no pre-fetch.
        # We preserve the signal's relative SL/TP distances to entry so the
        # stops are proportionally correct even as price moves. MetaApi fills
        # the market order at current bid/ask; the stop levels derived from the
        # original signal are passed as-is (already in broker price terms from
        # the Pine Script signal).
        # ------------------------------------------------------------------
        sl_value: float | None = float(request.sl) if request.sl is not None else None
        tp_value: float | None = float(request.tp) if request.tp is not None else None

        digits = self._infer_digits(request.entry, broker_symbol)
        if sl_value is not None:
            sl_value = round(sl_value, digits)
        if tp_value is not None:
            tp_value = round(tp_value, digits)

        logger.info(
            "MetaApi submit_order %s %s: SL=%.5f TP=%.5f (direct from signal, no pre-fetch)",
            broker_symbol, side,
            sl_value if sl_value is not None else 0.0,
            tp_value if tp_value is not None else 0.0,
        )

        # ✅ Use broker_symbol (translated) instead of request.symbol
        payload: Dict[str, Any] = {
            "actionType": action_type,
            "symbol": broker_symbol,
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

        # Timeout for trade POST: 30s to match MetaAPI broker latency (was 5s — caused EXEC FAIL on slow connections)
        resp = self._request_with_retry(
            "POST",
            self._trade_url(),
            timeout=30,
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

        # FIX 5: Prefer positionId over orderId as broker_order_id.
        # In MT5 hedging mode (all prop firms), orderId != positionId.
        # The broker positions endpoint returns 'id' which equals positionId,
        # so reconciliation must store positionId to match correctly.
        # Fall back to orderId for netting-mode accounts where positionId is absent.
        order_id = data.get("positionId") or data.get("orderId") or data.get("id")
        if not order_id:
            # ── Detect specific MT5 retcodes for actionable error messages ──
            numeric_code = data.get("numericCode")
            string_code = data.get("stringCode", "")
            if numeric_code == 10017 or string_code == "TRADE_RETCODE_TRADE_DISABLED":
                msg = (
                    f"MT5 TRADE_DISABLED (10017): Enable 'Algo Trading' in the MT5 terminal toolbar "
                    f"(must be GREEN). Also verify the account uses the master/trade password (not investor). "
                    f"Full response: {data}"
                )
                logger.error(msg)
                return ExecutionResult(
                    status="failed",
                    client_order_id=request.client_order_id,
                    message=msg,
                )
            msg = f"MetaApi response missing positionId/orderId: {data}"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )
        logger.info(
            "MetaApi broker_order_id resolved: positionId=%s orderId=%s -> using %s",
            data.get("positionId"),
            data.get("orderId"),
            order_id,
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

        # OPT-3: get_account_name() is permanently cached — zero cost after first call
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
        Close an existing MT5 position via MetaApi using POSITION_CLOSE_ID.

        Uses POSITION_CLOSE_ID which closes the full position by positionId
        without requiring volume or symbol — avoids partial-close bugs caused
        by the DB storing Pine signal size instead of the actual broker fill size.
        """
        if not request.broker_order_id:
            msg = "MetaApi close_order requires broker_order_id (positionId)"
            logger.error(msg)
            return ExecutionResult(
                status="failed",
                client_order_id=request.client_order_id,
                message=msg,
            )

        payload: Dict[str, Any] = {
            "actionType": "POSITION_CLOSE_ID",
            "positionId": str(request.broker_order_id),
            "comment": f"AI-Exit-{request.signal_id or request.alert_id}",
        }

        logger.info(
            "MetaApi close_order: client_order_id=%s positionId=%s symbol=%s (POSITION_CLOSE_ID)",
            request.client_order_id,
            request.broker_order_id,
            request.symbol,
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

    def get_deals_by_position(self, position_id: str) -> list[Dict[str, Any]]:
        """
        Fetch all deals for a specific position from MetaAPI.

        Args:
            position_id: The position ID to fetch deals for

        Returns:
            List of deal dictionaries. Returns empty list on failure, circuit breaker open,
            or if position_id is empty/None.
        """
        if not position_id:
            logger.error("get_deals_by_position called with empty position_id")
            return []

        if self._check_circuit_breaker():
            logger.warning("get_deals_by_position skipped: circuit breaker open")
            return []

        url = (
            f"{self.base_url}/users/current/accounts/"
            f"{self.account_id}/history-deals/position/{position_id}"
        )

        resp = self._request_with_retry("GET", url, timeout=30)
        if resp is None:
            logger.warning("get_deals_by_position: no response for position %s", position_id)
            return []

        if resp.status_code != 200:
            logger.error(
                "get_deals_by_position failed for position %s: HTTP %s %s",
                position_id,
                resp.status_code,
                resp.text[:200],
            )
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.error(
                "get_deals_by_position invalid JSON for position %s: %s",
                position_id,
                resp.text[:200],
            )
            return []

        # Response can be a dict with "deals" key, or a list directly
        if isinstance(data, dict):
            deals = data.get("deals") or []
        else:
            deals = data if isinstance(data, list) else []

        logger.info("get_deals_by_position: fetched %s deals for position %s", len(deals), position_id)
        return deals
