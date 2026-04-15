from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests
import websockets

logger = logging.getLogger(__name__)

_threads: Dict[str, threading.Thread] = {}


def _ms() -> int:
    return int(time.time() * 1000)


def _extract_realized_pnl_and_order_id(event: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    if event.get("e") != "ORDER_TRADE_UPDATE":
        return None
    o = event.get("o") or {}
    rp = o.get("rp")
    order_id = str(o.get("i") or "").strip()
    if not order_id:
        return None
    try:
        pnl = float(rp)
    except (TypeError, ValueError):
        return None
    return (pnl, order_id)


def _create_listen_key(api_key: str) -> str:
    r = requests.post(
        "https://fapi.binance.com/fapi/v1/listenKey",
        headers={"X-MBX-APIKEY": api_key},
        timeout=10,
    )
    r.raise_for_status()
    return str((r.json() or {}).get("listenKey") or "").strip()


def _keepalive_listen_key(api_key: str, listen_key: str) -> None:
    requests.put(
        "https://fapi.binance.com/fapi/v1/listenKey",
        headers={"X-MBX-APIKEY": api_key},
        params={"listenKey": listen_key},
        timeout=10,
    )


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
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    listen_key = _create_listen_key(api_key)
    if not listen_key:
        logger.error("[Binance Stream] Could not create listenKey for %s", account_name)
        return

    ws_url = f"wss://fstream.binance.com/ws/{listen_key}"
    logger.info("[Binance Stream] Connecting (%s)", account_name)

    last_keepalive = 0
    keepalive_interval_s = 30 * 60  # 30 minutes

    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                logger.info("[Binance Stream] Connected (%s)", account_name)
                while True:
                    if (_ms() - last_keepalive) > keepalive_interval_s * 1000:
                        try:
                            _keepalive_listen_key(api_key, listen_key)
                            last_keepalive = _ms()
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("[Binance Stream] listenKey keepalive failed: %s", exc)

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
            logger.warning("[Binance Stream] Disconnected (%s): %s", account_name, exc)
            await asyncio.sleep(5)


def ensure_binance_streaming(
    api_key: str,
    supabase_client,  # type: ignore[no-untyped-def]
    account_name: str,
) -> None:
    key = (account_name or api_key or "binance").strip()

    existing = _threads.get(key)
    if existing and existing.is_alive():
        return

    def _runner() -> None:
        try:
            asyncio.run(_run(api_key, supabase_client, account_name))
        except Exception as exc:  # noqa: BLE001
            logger.error("[Binance Stream] Runner crashed (%s): %s", account_name, exc)

    th = threading.Thread(target=_runner, daemon=True, name=f"binance-stream:{key}")
    _threads[key] = th
    th.start()
