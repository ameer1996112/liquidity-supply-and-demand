from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import websockets

from src.adapters.execution.bybit_adapter import _bybit_sign

logger = logging.getLogger(__name__)

_tasks: Dict[str, asyncio.Task] = {}


def _extract_realized_pnl_and_order_id(event: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    if (event.get("topic") or "") != "execution":
        return None
    data = event.get("data") or []
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


def _update_db_sync(supabase_client, order_id: str, pnl: float) -> None:  # type: ignore[no-untyped-def]
    now = datetime.now(timezone.utc).isoformat()
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
                expires = int(datetime.now(timezone.utc).timestamp() * 1000) + 10_000
                sign_payload = f"GET/realtime{expires}"
                sig = _bybit_sign(api_secret, sign_payload)
                await ws.send(json.dumps({"op": "auth", "args": [api_key, expires, sig]}))
                await ws.send(json.dumps({"op": "subscribe", "args": ["execution"]}))

                logger.info("[Bybit Stream] Connected (%s)", account_name)
                while True:
                    raw = await ws.recv()
                    evt = json.loads(raw)

                    extracted = _extract_realized_pnl_and_order_id(evt)
                    if not extracted:
                        continue

                    pnl, order_id = extracted
                    await asyncio.get_event_loop().run_in_executor(
                        None, _update_db_sync, supabase_client, order_id, pnl
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Bybit Stream] Disconnected (%s): %s", account_name, exc)
            await asyncio.sleep(5)


def ensure_bybit_streaming(
    api_key: str,
    api_secret: str,
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    key = (account_name or api_key or "bybit").strip()
    t = _tasks.get(key)
    if t and not t.done():
        return
    loop = asyncio.get_event_loop()
    _tasks[key] = loop.create_task(_run(api_key, api_secret, supabase_client, account_name))

