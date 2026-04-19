from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .tradingview_mcp import TradingViewMcpClient


def _to_js_invocation(expression: str, arg: Any | None) -> str:
    if arg is None:
        return expression
    return f"({expression})({json.dumps(arg)})"


@dataclass
class DesktopKeyboard:
    client: TradingViewMcpClient

    async def press(self, key_combo: str) -> None:
        parts = [part.strip() for part in key_combo.split("+") if part.strip()]
        if not parts:
            raise RuntimeError("keyboard.press requires a non-empty key")
        key = parts[-1]
        modifiers = [part.lower() for part in parts[:-1]]
        args = ["ui", "keyboard"]
        for modifier in modifiers:
            args.append(f"--{modifier}")
        args.append(key)
        await self.client.run(*args)


@dataclass
class DesktopMouse:
    client: TradingViewMcpClient

    async def click(self, x: float, y: float, double: bool = False) -> None:
        args = ["ui", "mouse", str(int(round(x))), str(int(round(y)))]
        if double:
            args.append("--double")
        await self.client.run(*args)


class TradingViewDesktopPage:
    def __init__(
        self,
        *,
        tab_id: str,
        chart_id: str | None,
        client: TradingViewMcpClient | None = None,
    ) -> None:
        self.tab_id = tab_id
        self.chart_id = chart_id
        self._client = (client or TradingViewMcpClient()).with_target(tab_id)
        self.keyboard = DesktopKeyboard(self._client)
        self.mouse = DesktopMouse(self._client)
        self._url_cache = (
            f"https://www.tradingview.com/chart/{chart_id}/" if chart_id else "https://www.tradingview.com/chart/"
        )

    @property
    def url(self) -> str:
        return self._url_cache

    async def title(self) -> str:
        value = await self.evaluate("document.title")
        return str(value or "")

    async def evaluate(self, expression: str, arg: Any | None = None) -> Any:
        result = await self._client.run("ui", "eval", _to_js_invocation(expression, arg))
        if not result.get("success", True):
            raise RuntimeError(str(result.get("error") or "ui eval failed"))
        return result.get("result")

    async def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None) -> None:
        await self.evaluate(f"window.location.href = {json.dumps(url)}; true")
        self._url_cache = url
        await asyncio.sleep(3.0)

    async def reload(self, wait_until: str | None = None, timeout: int | None = None) -> None:
        await self.evaluate("window.location.reload(); true")
        await asyncio.sleep(5.0)

