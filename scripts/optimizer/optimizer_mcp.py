from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.optimizer.tradingview_mcp import TradingViewMcpClient


@dataclass(frozen=True)
class OptimizerWorkspaceSlot:
    index: int
    tab_id: str
    chart_id: str | None
    broker: str | None = None
    symbol: str | None = None
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

    async def _run_command(self, action: str, *args: str) -> dict[str, Any]:
        try:
            result = await self._client.run(*args)
        except Exception as exc:
            joined = " ".join(args)
            raise RuntimeError(f"TradingView MCP {action} failed during {joined}: {exc}") from exc
        if not result.get("success", True):
            error = str(result.get("error") or "unknown MCP error")
            joined = " ".join(args)
            raise RuntimeError(f"TradingView MCP {action} failed during {joined}: {error}")
        return result

    async def _list_workspace_tabs(self) -> list[dict[str, Any]]:
        result = await self._run_command("tab list", "tab", "list")
        return list(result.get("tabs") or [])

    def _workspace_bootstrap_error(self, message: str) -> RuntimeError:
        return RuntimeError(
            f"{message}. Retry once TradingView Desktop is ready and tab creation is working."
        )

    def _build_workspace_slots(
        self,
        tabs: list[dict[str, Any]],
        *,
        broker: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[OptimizerWorkspaceSlot]:
        slots: list[OptimizerWorkspaceSlot] = []
        for tab in tabs:
            slots.append(
                OptimizerWorkspaceSlot(
                    index=int(tab.get("index") or len(slots)),
                    tab_id=str(tab.get("id") or ""),
                    chart_id=tab.get("chart_id"),
                    broker=broker,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
        return slots

    async def ensure_optimizer_ready(
        self,
        required_tabs: int,
    ) -> list[OptimizerWorkspaceSlot]:
        await self.ensure_ready()
        tabs = await self._list_workspace_tabs()
        max_attempts = max(required_tabs, 1)
        attempts = 0
        while len(tabs) < required_tabs:
            attempts += 1
            if attempts > max_attempts:
                raise self._workspace_bootstrap_error(
                    f"TradingView MCP workspace bootstrap stalled after {attempts - 1} tab creation attempts"
                )
            before_count = len(tabs)
            await self._run_command("tab new", "tab", "new")
            tabs = await self._list_workspace_tabs()
            if len(tabs) <= before_count:
                raise self._workspace_bootstrap_error(
                    "TradingView MCP tab creation did not increase the available tab count"
                )
        return self._build_workspace_slots(tabs[:required_tabs])

    async def ensure_optimizer_workspace(
        self,
        required_tabs: int,
        bootstrap_symbol: str,
        broker: str,
        bootstrap_timeframe: str | None = None,
    ) -> list[OptimizerWorkspaceSlot]:
        ready_slots = await self.ensure_optimizer_ready(required_tabs)
        for slot in ready_slots:
            await self._run_command("tab switch", "tab", "switch", str(slot.index))
            await self.set_symbol(bootstrap_symbol, broker)
            if bootstrap_timeframe is not None:
                await self.set_timeframe(bootstrap_timeframe)
        refreshed_tabs = await self._list_workspace_tabs()
        prepared_tabs: list[OptimizerWorkspaceSlot] = []
        for slot in self._build_workspace_slots(refreshed_tabs[:required_tabs]):
            prepared_tabs.append(
                OptimizerWorkspaceSlot(
                    index=slot.index,
                    tab_id=slot.tab_id,
                    chart_id=slot.chart_id,
                    broker=broker.upper(),
                    symbol=bootstrap_symbol.upper(),
                    timeframe=bootstrap_timeframe,
                )
            )
        return prepared_tabs

    async def set_symbol(self, pair: str, broker: str) -> None:
        await self._run_command("symbol", "symbol", f"{broker.upper()}:{pair.upper()}")

    async def set_timeframe(self, value: str) -> None:
        await self._run_command("timeframe", "timeframe", value)
