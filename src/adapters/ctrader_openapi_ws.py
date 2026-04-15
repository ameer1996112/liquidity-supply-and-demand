"""
cTrader Open API (Spotware) — minimal JSON-over-WebSocket client.

Used for connection testing and account discovery:
- App auth (client_id/client_secret)
- Get accounts by access token
- (Optional) Account auth for the first account

Docs:
- Send/receive JSON: https://help.ctrader.com/open-api/sending-receiving-json/
- Auth flow + GetAccountList: https://help.ctrader.com/open-api/account-authentication/
"""

from __future__ import annotations

import asyncio
import json
import ssl
import uuid
from typing import Any, Dict, List, Optional

import websockets

from config import get_settings


_APP_AUTH_REQ = 2100
_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
_ACCOUNT_AUTH_REQ = 2102

_WS_PORT_JSON = 5036
_WS_HOSTS = [
    "demo.ctraderapi.com",
    "live.ctraderapi.com",
]


def _msg(payload_type: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "clientMsgId": str(uuid.uuid4()),
        "payloadType": payload_type,
        "payload": payload,
    }


async def _recv_until_client_msg_id(
    ws: websockets.WebSocketClientProtocol,
    client_msg_id: str,
    timeout: float,
) -> Dict[str, Any]:
    async def _loop() -> Dict[str, Any]:
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("clientMsgId") == client_msg_id:
                return data

    return await asyncio.wait_for(_loop(), timeout=timeout)


async def _connect_and_fetch(host: str, access_token: str) -> List[Dict[str, Any]]:
    s = get_settings()
    client_id = (s.ctrader_client_id or "").strip()
    client_secret = (s.ctrader_client_secret.get_secret_value() if s.ctrader_client_secret else "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Missing CTRADER_CLIENT_ID/CTRADER_CLIENT_SECRET")

    url = f"wss://{host}:{_WS_PORT_JSON}"
    ssl_ctx = ssl.create_default_context()

    async with websockets.connect(url, ssl=ssl_ctx, ping_interval=None, close_timeout=2) as ws:
        # 1) App auth
        app_auth = _msg(_APP_AUTH_REQ, {"clientId": client_id, "clientSecret": client_secret})
        await ws.send(json.dumps(app_auth))
        _ = await _recv_until_client_msg_id(ws, app_auth["clientMsgId"], timeout=7)

        # 2) Accounts by access token
        acct_req = _msg(_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {"accessToken": access_token})
        await ws.send(json.dumps(acct_req))
        acct_res = await _recv_until_client_msg_id(ws, acct_req["clientMsgId"], timeout=10)

        payload = acct_res.get("payload") or {}
        accounts = payload.get("ctidTraderAccount") or payload.get("ctidTraderAccounts") or []
        if not isinstance(accounts, list):
            accounts = []

        # 3) Optional: account auth for the first account (verifies we can authenticate further)
        first_id: Optional[int] = None
        if accounts and isinstance(accounts[0], dict):
            try:
                first_id = int(accounts[0].get("ctidTraderAccountId") or 0)
            except Exception:
                first_id = None
        if first_id:
            acc_auth = _msg(_ACCOUNT_AUTH_REQ, {"ctidTraderAccountId": first_id, "accessToken": access_token})
            await ws.send(json.dumps(acc_auth))
            _ = await _recv_until_client_msg_id(ws, acc_auth["clientMsgId"], timeout=10)

        return accounts


async def fetch_accounts_via_websocket(access_token: str) -> List[Dict[str, Any]]:
    """
    Try both demo and live proxies and return the first non-empty account list.
    If both are empty but requests succeeded, returns an empty list.
    """
    last_err: Optional[Exception] = None
    for host in _WS_HOSTS:
        try:
            accounts = await _connect_and_fetch(host=host, access_token=access_token)
            if accounts:
                return accounts
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return []

