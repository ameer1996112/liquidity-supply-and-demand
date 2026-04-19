from __future__ import annotations

from typing import Any

from scripts.optimizer.tradingview_mcp import TradingViewMcpClient


class OptimizerMcpController:
    def __init__(self, client: TradingViewMcpClient | Any | None = None) -> None:
        self._client = client or TradingViewMcpClient()

    async def healthcheck(self) -> tuple[bool, str]:
        return await self._client.healthcheck()

    async def ensure_ready(self) -> None:
        ready, reason = await self.healthcheck()
        if not ready:
            raise RuntimeError(reason)

    async def ensure_optimizer_workspace(
        self,
        required_tabs: int,
        bootstrap_symbol: str,
        broker: str,
    ) -> list[str]:
        await self.ensure_ready()
        return [f"{broker}:{bootstrap_symbol}"] * required_tabs

    async def set_symbol(self, pair: str, broker: str) -> None:
        await self._client.run("symbol", f"{broker.upper()}:{pair.upper()}")

    async def set_timeframe(self, value: str) -> None:
        await self._client.run("timeframe", value)
