from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.optimizer.tradingview_mcp import TradingViewMcpClient


@dataclass(frozen=True)
class OptimizerWorkspaceSlot:
    index: int
    broker: str
    symbol: str
    timeframe: str | None = None


class OptimizerMcpController:
    def __init__(self, client: TradingViewMcpClient | Any | None = None) -> None:
        self._client = client or TradingViewMcpClient()

    async def healthcheck(self) -> tuple[bool, str]:
        return await self._client.healthcheck()

    async def ensure_ready(self) -> None:
        ready, reason = await self.healthcheck()
        if not ready:
            raise RuntimeError(
                f"{reason}. Open TradingView Desktop, verify the MCP bridge is running, "
                "and retry once the app is ready."
            )

    async def _run_command(self, command: str, *args: str) -> dict[str, Any]:
        result = await self._client.run(command, *args)
        if not result.get("success", True):
            error = str(result.get("error") or "unknown MCP error")
            formatted_args = " ".join(args)
            raise RuntimeError(
                f"TradingView MCP {command} {formatted_args}".strip()
                + f" failed: {error}"
            )
        return result

    async def ensure_optimizer_workspace(
        self,
        required_tabs: int,
        bootstrap_symbol: str,
        broker: str,
        bootstrap_timeframe: str | None = None,
    ) -> list[OptimizerWorkspaceSlot]:
        await self.ensure_ready()
        prepared_tabs: list[OptimizerWorkspaceSlot] = []
        for index in range(required_tabs):
            await self.set_symbol(bootstrap_symbol, broker)
            if bootstrap_timeframe is not None:
                await self.set_timeframe(bootstrap_timeframe)
            prepared_tabs.append(
                OptimizerWorkspaceSlot(
                    index=index,
                    broker=broker.upper(),
                    symbol=bootstrap_symbol.upper(),
                    timeframe=bootstrap_timeframe,
                )
            )
        return prepared_tabs

    async def set_symbol(self, pair: str, broker: str) -> None:
        await self._run_command("symbol", f"{broker.upper()}:{pair.upper()}")

    async def set_timeframe(self, value: str) -> None:
        await self._run_command("timeframe", value)
