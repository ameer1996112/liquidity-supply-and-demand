# Multi‑Venue Bot (Prop + Personal + Crypto) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the current TradingView→pipeline system to execute and stream PnL across multiple venues (MetaApi/MT5, cTrader, Binance, Bybit) with prop vs personal modes routed via account profiles.

**Architecture:** Keep TradingView alerts as the single signal source. Route each signal to a list of `AccountProfile`s (existing “broker profiles” generalized) and select a venue-specific `ExecutionAdapter` via the execution router. Add venue-specific streaming services that normalize fills/closures/PnL into the existing DB model.

**Tech Stack:** Python (FastAPI + worker), `requests`, `asyncio`, `websockets` (new), MetaApi SDK (existing), Supabase (existing).

---

## File Structure (Locked)

**Create**
- `src/core/account_profiles.py` — unify profile loading/validation; backward compatible with existing broker profile formats.
- `src/adapters/execution/binance_adapter.py` — REST execution for Binance spot+futures.
- `src/adapters/execution/bybit_adapter.py` — REST execution for Bybit spot+futures.
- `src/services/binance_streaming_service.py` — Binance user-data stream → normalized DB updates.
- `src/services/bybit_streaming_service.py` — Bybit private WS → normalized DB updates.
- `tests/test_execution_router_multi_venue.py` — adapter routing tests.
- `tests/test_crypto_adapters_signing.py` — HMAC signing and request construction tests.

**Modify**
- `src/core/broker_profiles.py` — keep as-is but call into `src/core/account_profiles.py` (or deprecate gradually).
- `src/adapters/execution/router.py` — select adapter by `profile["venue"]`.
- `config/settings.py` — add settings for streaming bootstrap + crypto environment variable conventions.
- `requirements.txt` — add `websockets` dependency for streaming services.

**Out of Scope (separate plan)**
- cTrader Open API execution + streaming (requires firm-specific app registration + OAuth details)

Note: This plan ships the multi-venue foundation + Binance/Bybit execution & streaming first. cTrader is handled in a dedicated follow-up plan once Open API credentials are available.

---

## Task 1: Introduce `AccountProfile` + Venue Routing (Foundation)

**Files:**
- Create: `src/core/account_profiles.py`
- Modify: `src/core/broker_profiles.py`
- Modify: `src/adapters/execution/router.py`
- Test: `tests/test_execution_router_multi_venue.py`

- [ ] **Step 1: Write failing tests for multi-venue adapter routing**

Create `tests/test_execution_router_multi_venue.py`:

```python
from src.adapters.execution.router import get_adapter


def test_router_metaapi_profile_defaults_to_metaapi():
    adapter = get_adapter(profile={"name": "acc", "token": "t", "meta_api_account_id": "a"})
    assert adapter.__class__.__name__ == "MetaApiAdapter"


def test_router_binance_profile_selects_binance_adapter():
    adapter = get_adapter(profile={"venue": "binance", "name": "acc", "api_key": "k", "api_secret": "s"})
    assert adapter.__class__.__name__ == "BinanceAdapter"


def test_router_bybit_profile_selects_bybit_adapter():
    adapter = get_adapter(profile={"venue": "bybit", "name": "acc", "api_key": "k", "api_secret": "s"})
    assert adapter.__class__.__name__ == "BybitAdapter"
```

- [ ] **Step 2: Run the tests to confirm failure**

Run: `PYTHONPATH=. pytest tests/test_execution_router_multi_venue.py -v`  
Expected: FAIL (imports/classes don’t exist yet, or router always returns MetaApi).

- [ ] **Step 3: Add `AccountProfile` loader (backward compatible)**

Create `src/core/account_profiles.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal, Optional


Venue = Literal["metaapi_mt5", "ctrader", "binance", "bybit"]
Mode = Literal["prop", "personal"]
AssetClass = Literal["forex_cfd", "crypto"]


@dataclass(frozen=True)
class AccountProfile:
    name: str
    venue: Venue
    mode: Mode
    asset_class: AssetClass

    # MetaApi/MT5
    meta_api_account_id: str = ""
    token: str = ""
    region: str = ""

    # Crypto (Binance/Bybit)
    api_key: str = ""
    api_secret: str = ""
    subaccount: str = ""

    # Risk & routing
    risk_pct: float = 1.0
    max_positions: int = 3

    @staticmethod
    def from_dict(row: Dict[str, Any]) -> "AccountProfile":
        name = (row.get("name") or "profile").strip()
        venue = (row.get("venue") or "").strip().lower() or "metaapi_mt5"
        if venue == "metaapi":
            venue = "metaapi_mt5"
        if venue not in {"metaapi_mt5", "ctrader", "binance", "bybit"}:
            raise ValueError(f"Unknown venue: {venue}")

        mode = (row.get("mode") or "personal").strip().lower()
        if mode not in {"prop", "personal"}:
            raise ValueError(f"Unknown mode: {mode}")

        asset_class = (row.get("asset_class") or ("crypto" if venue in {"binance", "bybit"} else "forex_cfd")).strip().lower()
        if asset_class not in {"forex_cfd", "crypto"}:
            raise ValueError(f"Unknown asset_class: {asset_class}")

        return AccountProfile(
            name=name,
            venue=venue,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            asset_class=asset_class,  # type: ignore[arg-type]
            meta_api_account_id=str(row.get("meta_api_account_id") or row.get("account_id") or "").strip(),
            token=str(row.get("token") or "").strip(),
            region=str(row.get("region") or "").strip(),
            api_key=str(row.get("api_key") or "").strip(),
            api_secret=str(row.get("api_secret") or "").strip(),
            subaccount=str(row.get("subaccount") or "").strip(),
            risk_pct=float(row.get("risk_pct", 1.0)),
            max_positions=int(row.get("max_positions", 3)),
        )


def coerce_profiles(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert profile dicts to a normalized dict format used by pipeline/logic.

    Keeps existing keys for backward compatibility while adding:
      - venue, mode, asset_class
      - api_key/api_secret for crypto
    """
    out: List[Dict[str, Any]] = []
    for row in rows:
        p = AccountProfile.from_dict(row)
        d = dict(row)
        d.setdefault("name", p.name)
        d["venue"] = p.venue
        d["mode"] = p.mode
        d["asset_class"] = p.asset_class
        if p.venue == "metaapi_mt5":
            d.setdefault("meta_api_account_id", p.meta_api_account_id)
            d.setdefault("token", p.token)
            if p.region:
                d.setdefault("region", p.region)
        if p.venue in {"binance", "bybit"}:
            d.setdefault("api_key", p.api_key)
            d.setdefault("api_secret", p.api_secret)
        out.append(d)
    return out
```

- [ ] **Step 4: Wire `broker_profiles.get_active_profiles()` to normalize via `coerce_profiles()`**

Modify `src/core/broker_profiles.py` at the end of each return path to normalize:

```python
from src.core.account_profiles import coerce_profiles

# ...
return coerce_profiles(out)
```

- [ ] **Step 5: Extend execution router to choose adapter by `profile["venue"]`**

Modify `src/adapters/execution/router.py` (top imports will change):

```python
from src.adapters.execution.binance_adapter import BinanceAdapter
from src.adapters.execution.bybit_adapter import BybitAdapter
```

Then update the profile branch:

```python
if profile and isinstance(profile, dict):
    venue = (profile.get("venue") or "").strip().lower() or "metaapi_mt5"
    if venue in {"metaapi_mt5", "metaapi"}:
        token = (profile.get("token") or "").strip()
        account_id = (profile.get("meta_api_account_id") or profile.get("account_id") or "").strip()
        account_name = (profile.get("name") or "").strip() or None
        region = (profile.get("region") or "").strip() or None
        if token and account_id:
            return MetaApiAdapter(token=token, account_id=account_id, account_name=account_name, region=region)
    if venue == "binance":
        return BinanceAdapter(
            api_key=(profile.get("api_key") or "").strip(),
            api_secret=(profile.get("api_secret") or "").strip(),
            account_name=(profile.get("name") or "").strip() or None,
        )
    if venue == "bybit":
        return BybitAdapter(
            api_key=(profile.get("api_key") or "").strip(),
            api_secret=(profile.get("api_secret") or "").strip(),
            account_name=(profile.get("name") or "").strip() or None,
        )
```

- [ ] **Step 6: Run the routing tests again**

Run: `PYTHONPATH=. pytest tests/test_execution_router_multi_venue.py -v`  
Expected: FAIL (BinanceAdapter/BybitAdapter not implemented yet).

- [ ] **Step 7: Commit**

```bash
git add src/core/account_profiles.py src/core/broker_profiles.py src/adapters/execution/router.py tests/test_execution_router_multi_venue.py
git commit -m "DEV-0: add multi-venue profile routing scaffold"
```

---

## Task 2: Binance Execution Adapter (Spot + Futures)

**Files:**
- Create: `src/adapters/execution/binance_adapter.py`
- Test: `tests/test_crypto_adapters_signing.py`

- [ ] **Step 1: Add failing tests for Binance HMAC signing and URL building**

Create `tests/test_crypto_adapters_signing.py`:

```python
import hmac
import hashlib
from urllib.parse import urlencode

from src.adapters.execution.binance_adapter import _sign_query


def test_binance_sign_query_matches_hmac_sha256():
    secret = "testsecret"
    params = {"symbol": "BTCUSDT", "timestamp": 1700000000000}
    query = urlencode(params)
    expected = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    assert _sign_query(secret, query) == expected
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `PYTHONPATH=. pytest tests/test_crypto_adapters_signing.py -v`  
Expected: FAIL (module not found).

- [ ] **Step 3: Implement Binance adapter (minimal REST for v1)**

Create `src/adapters/execution/binance_adapter.py`:

```python
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
        """
        V1: map OrderRequest into either:
          - SPOT market order when request.entry is None
          - FUTURES market order otherwise (spot limit/stop orders are not implemented in v1)
        """
        if not self.api_key or not self.api_secret:
            return ExecutionResult(status="failed", message="BINANCE_MISSING_KEYS", client_order_id=request.client_order_id)

        symbol = request.symbol.replace("/", "").upper()
        side = request.side.upper()

        # Heuristic routing:
        # - If SL/TP provided, we assume futures (because spot OCO/stop logic is more complex)
        is_futures = bool(request.sl or request.tp)
        base_url = self.base_url_futures if is_futures else self.base_url_spot
        path = "/fapi/v1/order" if is_futures else "/api/v3/order"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "newClientOrderId": request.client_order_id,
        }

        # For simplicity in v1, interpret `size` as "quantity" directly.
        # Production: introduce a per-symbol sizing map (contracts vs lots).
        params["quantity"] = str(request.size)

        try:
            data = self._request("POST", base_url, path, params)
            order_id = str(data.get("orderId") or data.get("orderId", "") or "")
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
        """
        V1: for futures, place reduceOnly market order in opposite direction.
        For spot, place opposite market order of the same quantity.
        """
        if not self.api_key or not self.api_secret:
            return ExecutionResult(status="failed", message="BINANCE_MISSING_KEYS", client_order_id=request.client_order_id)

        symbol = request.symbol.replace("/", "").upper()
        qty = float(request.size or 0.0)
        if qty <= 0:
            return ExecutionResult(status="failed", message="BINANCE_CLOSE_MISSING_SIZE", client_order_id=request.client_order_id)

        entry_side = (request.side or "").lower()
        if entry_side not in {"buy", "sell"}:
            return ExecutionResult(status="failed", message="BINANCE_CLOSE_MISSING_SIDE", client_order_id=request.client_order_id)

        close_side = "SELL" if entry_side == "buy" else "BUY"

        is_futures = True  # close is primarily used for futures positions in v1
        base_url = self.base_url_futures if is_futures else self.base_url_spot
        path = "/fapi/v1/order" if is_futures else "/api/v3/order"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": str(qty),
            "newClientOrderId": request.client_order_id,
        }
        if is_futures:
            params["reduceOnly"] = "true"

        try:
            data = self._request("POST", base_url, path, params)
            order_id = str(data.get("orderId") or "")
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
```

- [ ] **Step 4: Run signing test**

Run: `PYTHONPATH=. pytest tests/test_crypto_adapters_signing.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/execution/binance_adapter.py tests/test_crypto_adapters_signing.py
git commit -m "DEV-0: add binance execution adapter (v1)"
```

---

## Task 3: Bybit Execution Adapter (Spot + Futures)

**Files:**
- Create: `src/adapters/execution/bybit_adapter.py`
- Test: `tests/test_crypto_adapters_signing.py`

- [ ] **Step 1: Add failing test for Bybit signature**

Append to `tests/test_crypto_adapters_signing.py`:

```python
from src.adapters.execution.bybit_adapter import _bybit_sign


def test_bybit_signature_is_hmac_sha256_hex():
    secret = "testsecret"
    payload = "1700000000000testkey5000{\"foo\":\"bar\"}"
    sig = _bybit_sign(secret, payload)
    assert isinstance(sig, str)
    assert len(sig) == 64
```

- [ ] **Step 2: Run tests (expect failure)**

Run: `PYTHONPATH=. pytest tests/test_crypto_adapters_signing.py -v`  
Expected: FAIL (module missing).

- [ ] **Step 3: Implement Bybit adapter (minimal REST v1)**

Create `src/adapters/execution/bybit_adapter.py`:

```python
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
        r = requests.post(url, headers=self._headers(ts, body_str), data=body_str, timeout=self.timeout_seconds)
        r.raise_for_status()
        return r.json()

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        if not self.api_key or not self.api_secret:
            return ExecutionResult(status="failed", message="BYBIT_MISSING_KEYS", client_order_id=request.client_order_id)

        symbol = request.symbol.replace("/", "").upper()
        side = "Buy" if request.side.lower() == "buy" else "Sell"

        # Heuristic: SL/TP => futures (linear), else spot
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

        # Bybit supports takeProfit/stopLoss for linear; set when provided
        if category == "linear":
            if request.tp:
                body["takeProfit"] = str(request.tp)
            if request.sl:
                body["stopLoss"] = str(request.sl)

        try:
            data = self._post("/v5/order/create", body)
            result = data.get("result") or {}
            order_id = str(result.get("orderId") or "")
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
            return ExecutionResult(status="failed", message="BYBIT_MISSING_KEYS", client_order_id=request.client_order_id)

        symbol = request.symbol.replace("/", "").upper()
        qty = float(request.size or 0.0)
        if qty <= 0:
            return ExecutionResult(status="failed", message="BYBIT_CLOSE_MISSING_SIZE", client_order_id=request.client_order_id)

        entry_side = (request.side or "").lower()
        if entry_side not in {"buy", "sell"}:
            return ExecutionResult(status="failed", message="BYBIT_CLOSE_MISSING_SIDE", client_order_id=request.client_order_id)

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
            order_id = str(result.get("orderId") or "")
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
```

- [ ] **Step 4: Run signing tests**

Run: `PYTHONPATH=. pytest tests/test_crypto_adapters_signing.py -v`  
Expected: PASS.

- [ ] **Step 5: Run multi-venue routing tests**

Run: `PYTHONPATH=. pytest tests/test_execution_router_multi_venue.py -v`  
Expected: PASS (router returns `BinanceAdapter` / `BybitAdapter`).

- [ ] **Step 6: Commit**

```bash
git add src/adapters/execution/bybit_adapter.py tests/test_crypto_adapters_signing.py tests/test_execution_router_multi_venue.py
git commit -m "DEV-0: add bybit execution adapter (v1)"
```

---

## Task 4: Add WebSocket Dependency for Streaming

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependency**

Append to `requirements.txt` (near HTTP or streaming section):

```txt
websockets>=12.0
```

- [ ] **Step 2: Install**

Run: `source ./venv/bin/activate && pip install -r requirements.txt`  
Expected: installs `websockets`.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "DEV-0: add websockets dependency for streaming services"
```

---

## Task 5: Add Settings Flag for Multi‑Venue Streaming

**Files:**
- Modify: `config/settings.py`

- [ ] **Step 1: Add Settings field**

Add to the `Settings` class in `config/settings.py`:

```python
enable_multi_venue_streaming: bool = Field(
    default=False,
    description="Enable Binance/Bybit streaming bootstrap in worker loop. Env: ENABLE_MULTI_VENUE_STREAMING.",
    validation_alias=AliasChoices("ENABLE_MULTI_VENUE_STREAMING", "enable_multi_venue_streaming"),
)
```

- [ ] **Step 2: Run import/type sanity**

Run: `PYTHONPATH=. python3 -c "from config import get_settings; print(get_settings().enable_multi_venue_streaming)"`  
Expected: prints `False` (unless env var is set).

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "DEV-0: add enable_multi_venue_streaming setting"
```

---

## Task 6: Binance Streaming Service (User Data Stream → DB)

**Files:**
- Create: `src/services/binance_streaming_service.py`
- Test: `tests/test_binance_stream_event_normalization.py`

- [ ] **Step 1: Create normalization tests**

Create `tests/test_binance_stream_event_normalization.py`:

```python
from src.services.binance_streaming_service import _extract_realized_pnl


def test_extract_realized_pnl_from_order_trade_update():
    evt = {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "x": "TRADE",
            "X": "FILLED",
            "rp": "12.34",
            "i": 123456,
        },
    }
    assert _extract_realized_pnl(evt) == 12.34
```

- [ ] **Step 2: Run tests (expect failure)**

Run: `PYTHONPATH=. pytest tests/test_binance_stream_event_normalization.py -v`  
Expected: FAIL (module missing).

- [ ] **Step 3: Implement streaming service (core loop + db update hook)**

Create `src/services/binance_streaming_service.py`:

```python
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
import websockets

logger = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None  # one per process


def _ms() -> int:
    return int(time.time() * 1000)


def _extract_realized_pnl(event: Dict[str, Any]) -> Optional[float]:
    if event.get("e") != "ORDER_TRADE_UPDATE":
        return None
    o = event.get("o") or {}
    # Binance futures: rp = realized profit
    rp = o.get("rp")
    try:
        return float(rp) if rp is not None else None
    except (TypeError, ValueError):
        return None


def _create_listen_key(api_key: str) -> str:
    r = requests.post(
        "https://fapi.binance.com/fapi/v1/listenKey",
        headers={"X-MBX-APIKEY": api_key},
        timeout=10,
    )
    r.raise_for_status()
    return (r.json() or {}).get("listenKey") or ""


def _keepalive_listen_key(api_key: str, listen_key: str) -> None:
    requests.put(
        "https://fapi.binance.com/fapi/v1/listenKey",
        headers={"X-MBX-APIKEY": api_key},
        params={"listenKey": listen_key},
        timeout=10,
    )


async def _run(
    api_key: str,
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    listen_key = _create_listen_key(api_key)
    if not listen_key:
        logger.error("[Binance Stream] Could not create listenKey for %s", account_name)
        return

    ws_url = f"wss://fstream.binance.com/ws/{listen_key}"
    logger.info("[Binance Stream] Connecting %s", ws_url[:60])

    last_keepalive = 0
    keepalive_interval = 30 * 60  # 30 minutes

    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                logger.info("[Binance Stream] Connected (%s)", account_name)
                while True:
                    if _ms() - last_keepalive > keepalive_interval * 1000:
                        try:
                            _keepalive_listen_key(api_key, listen_key)
                            last_keepalive = _ms()
                        except Exception as _ka:  # noqa: BLE001
                            logger.warning("[Binance Stream] listenKey keepalive failed: %s", _ka)

                    raw = await ws.recv()
                    evt = json.loads(raw)

                    pnl = _extract_realized_pnl(evt)
                    if pnl is None:
                        continue

                    o = evt.get("o") or {}
                    order_id = str(o.get("i") or "").strip()
                    if not order_id:
                        continue

                    # Update DB row by broker_order_id (same convention as MetaApi streaming)
                    now = datetime.now(timezone.utc).isoformat()
                    try:
                        supabase_client.table("trading_signals").update(
                            {
                                "status": "CLOSED",
                                "pnl_usd": pnl,
                                "pnl": pnl,
                                "exit_time": now,
                                "closed_at": now,
                                "outcome": "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven",
                                "updated_at": now,
                            }
                        ).eq("broker_order_id", order_id).execute()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("[Binance Stream] DB update failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Binance Stream] Disconnected (%s): %s", account_name, exc)
            await asyncio.sleep(5)


def ensure_binance_streaming(
    api_key: str,
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    global _task
    if _task and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_run(api_key, supabase_client, account_name))
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. pytest tests/test_binance_stream_event_normalization.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/binance_streaming_service.py tests/test_binance_stream_event_normalization.py
git commit -m "DEV-0: add binance streaming service skeleton"
```

---

## Task 7: Bybit Streaming Service (Private WS → DB)

**Files:**
- Create: `src/services/bybit_streaming_service.py`
- Test: `tests/test_bybit_stream_event_normalization.py`

- [ ] **Step 1: Create tests for PnL extraction**

Create `tests/test_bybit_stream_event_normalization.py`:

```python
from src.services.bybit_streaming_service import _extract_realized_pnl_and_order_id


def test_extract_realized_pnl_and_order_id_from_execution_event():
    evt = {
        "topic": "execution",
        "data": [
            {"symbol": "BTCUSDT", "orderId": "abc123", "execPnl": "5.5"}
        ],
    }
    assert _extract_realized_pnl_and_order_id(evt) == (5.5, "abc123")
```

- [ ] **Step 2: Run tests (expect failure)**

Run: `PYTHONPATH=. pytest tests/test_bybit_stream_event_normalization.py -v`  
Expected: FAIL.

- [ ] **Step 3: Implement bybit WS skeleton**

Create `src/services/bybit_streaming_service.py`:

```python
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import websockets

from src.adapters.execution.bybit_adapter import _bybit_sign

logger = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None

def _extract_realized_pnl_and_order_id(event: Dict[str, Any]) -> Optional[tuple[float, str]]:
    if (event.get("topic") or "") != "execution":
        return None
    data = (event.get("data") or [])
    if not data:
        return None
    row = data[0] or {}
    order_id = str(row.get("orderId") or "").strip()
    if not order_id:
        return None
    pnl_raw = row.get("execPnl")
    try:
        pnl = float(pnl_raw)
    except (TypeError, ValueError):
        return None
    return (pnl, order_id)


async def _run(
    api_key: str,
    api_secret: str,
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    ws_url = "wss://stream.bybit.com/v5/private"
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                # Auth (Bybit): sign "GET/realtime{expires}"
                expires = int(datetime.now(timezone.utc).timestamp() * 1000) + 10_000
                sign_payload = f"GET/realtime{expires}"
                sig = _bybit_sign(api_secret, sign_payload)
                await ws.send(json.dumps({"op": "auth", "args": [api_key, expires, sig]}))

                # Subscribe: executions (contains orderId and execPnl)
                await ws.send(json.dumps({"op": "subscribe", "args": ["execution"]}))

                logger.info("[Bybit Stream] Connected (%s)", account_name)
                while True:
                    raw = await ws.recv()
                    evt = json.loads(raw)

                    extracted = _extract_realized_pnl_and_order_id(evt)
                    if not extracted:
                        continue
                    pnl, order_id = extracted

                    now = datetime.now(timezone.utc).isoformat()
                    try:
                        supabase_client.table("trading_signals").update(
                            {
                                "status": "CLOSED",
                                "pnl_usd": pnl,
                                "pnl": pnl,
                                "exit_time": now,
                                "closed_at": now,
                                "outcome": "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven",
                                "updated_at": now,
                            }
                        ).eq("broker_order_id", order_id).execute()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("[Bybit Stream] DB update failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Bybit Stream] Disconnected (%s): %s", account_name, exc)
            await asyncio.sleep(5)


def ensure_bybit_streaming(
    api_key: str,
    api_secret: str,
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    global _task
    if _task and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_run(api_key, api_secret, supabase_client, account_name))
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. pytest tests/test_bybit_stream_event_normalization.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/bybit_streaming_service.py tests/test_bybit_stream_event_normalization.py
git commit -m "DEV-0: add bybit streaming service skeleton"
```

---

## Task 8: Wire Streaming Services into Worker Process (Opt-In)

**Files:**
- Create: `src/services/streaming_bootstrap.py`
- Modify: `src/worker.py`
- Test: `tests/test_streaming_bootstrap.py`

- [ ] **Step 1: Write failing unit tests for streaming bootstrap dispatch**

Create `tests/test_streaming_bootstrap.py`:

```python
from src.services.streaming_bootstrap import ensure_streaming_for_profile


def test_ensure_streaming_for_profile_binance(monkeypatch):
    calls = []

    def _fake(api_key, supabase_client, account_name):
        calls.append((api_key, account_name))

    monkeypatch.setattr(
        "src.services.streaming_bootstrap.ensure_binance_streaming",
        _fake,
        raising=False,
    )

    ensure_streaming_for_profile({"venue": "binance", "api_key": "k", "name": "acc"}, supabase_client=None)
    assert calls == [("k", "acc")]


def test_ensure_streaming_for_profile_bybit(monkeypatch):
    calls = []

    def _fake(api_key, api_secret, supabase_client, account_name):
        calls.append((api_key, api_secret, account_name))

    monkeypatch.setattr(
        "src.services.streaming_bootstrap.ensure_bybit_streaming",
        _fake,
        raising=False,
    )

    ensure_streaming_for_profile({"venue": "bybit", "api_key": "k", "api_secret": "s", "name": "acc"}, supabase_client=None)
    assert calls == [("k", "s", "acc")]
```

- [ ] **Step 2: Run tests (expect failure)**

Run: `PYTHONPATH=. pytest tests/test_streaming_bootstrap.py -v`  
Expected: FAIL (module missing).

- [ ] **Step 3: Implement bootstrap module**

Create `src/services/streaming_bootstrap.py`:

```python
from __future__ import annotations

from typing import Any, Dict

from src.services.binance_streaming_service import ensure_binance_streaming
from src.services.bybit_streaming_service import ensure_bybit_streaming


def ensure_streaming_for_profile(profile: Dict[str, Any], supabase_client) -> None:  # type: ignore[no-untyped-def]
    venue = (profile.get("venue") or "").strip().lower()
    name = (profile.get("name") or "profile").strip()

    if venue == "binance":
        ensure_binance_streaming(
            api_key=(profile.get("api_key") or "").strip(),
            supabase_client=supabase_client,
            account_name=name,
        )
        return

    if venue == "bybit":
        ensure_bybit_streaming(
            api_key=(profile.get("api_key") or "").strip(),
            api_secret=(profile.get("api_secret") or "").strip(),
            supabase_client=supabase_client,
            account_name=name,
        )
        return
```

- [ ] **Step 4: Run tests (expect pass)**

Run: `PYTHONPATH=. pytest tests/test_streaming_bootstrap.py -v`  
Expected: PASS.

- [ ] **Step 5: Wire bootstrap into the worker (opt-in)**

Find the 60s watchdog tick block:

Run: `rg -n "last_watchdog_ts" src/worker.py | head`  
Expected: you’ll see the guard `if now - last_watchdog_ts >= 60:` and later `last_watchdog_ts = now`.

Inside that `if now - last_watchdog_ts >= 60:` block, right after `last_watchdog_ts = now`, add:

```python
from src.services.streaming_bootstrap import ensure_streaming_for_profile

if getattr(get_settings(), "enable_multi_venue_streaming", False):
    from src.core.broker_profiles import get_active_profiles
    profiles = get_active_profiles()
    for profile in profiles:
        ensure_streaming_for_profile(profile, supabase)
```

- Start MetaApi streaming for metaapi profiles (existing)
- Start Binance streaming for binance profiles
- Start Bybit streaming for bybit profiles

Add function (example to add in a new file `src/services/streaming_bootstrap.py` if you prefer clean boundaries):

```python
def ensure_streaming_for_profile(profile: dict, supabase_client) -> None:
    venue = (profile.get("venue") or "").lower()
    name = (profile.get("name") or "profile")
    if venue == "binance":
        from src.services.binance_streaming_service import ensure_binance_streaming
        ensure_binance_streaming(profile["api_key"], supabase_client, name)
    if venue == "bybit":
        from src.services.bybit_streaming_service import ensure_bybit_streaming
        ensure_bybit_streaming(profile["api_key"], profile["api_secret"], supabase_client, name)
```

- [ ] **Step 6: Commit**

```bash
git add src/services/streaming_bootstrap.py src/worker.py tests/test_streaming_bootstrap.py
git commit -m "DEV-0: bootstrap streaming services per venue"
```

---

## Plan Self-Review (Required)

**Spec coverage check**
- Multi-venue routing: Tasks 1–3
- Streaming enable flag: Task 5
- Streaming PnL: Tasks 6–8 (Binance/Bybit)
- Prop/personal modes: profile fields added in Task 1; enforcement remains in existing guards/risk (follow-up plan may be needed for rule presets per mode)

**Placeholder scan**
- cTrader is explicitly out-of-scope for this plan; create a dedicated plan after cTrader Open API credentials are available.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-multi-venue-bot.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session, batching with checkpoints

Which approach?
