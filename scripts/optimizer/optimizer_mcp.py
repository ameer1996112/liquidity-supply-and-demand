from __future__ import annotations

import asyncio
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
    _TAB_BOOTSTRAP_SETTLE_ATTEMPTS = 5
    _TAB_BOOTSTRAP_SETTLE_SLEEP_SECS = 0.5

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
            tabs = await self._wait_for_tab_count(required_tabs=required_tabs, minimum_count=before_count + 1)
            if len(tabs) <= before_count:
                raise self._workspace_bootstrap_error(
                    "TradingView MCP tab creation did not increase the available tab count"
                )
        return self._build_workspace_slots(tabs[:required_tabs])

    async def _wait_for_tab_count(
        self,
        *,
        required_tabs: int,
        minimum_count: int,
    ) -> list[dict[str, Any]]:
        """Poll tab list briefly because tab creation can be visible a moment later."""
        tabs = await self._list_workspace_tabs()
        if len(tabs) >= required_tabs or len(tabs) >= minimum_count:
            return tabs

        for _ in range(self._TAB_BOOTSTRAP_SETTLE_ATTEMPTS - 1):
            await asyncio.sleep(self._TAB_BOOTSTRAP_SETTLE_SLEEP_SECS)
            tabs = await self._list_workspace_tabs()
            if len(tabs) >= required_tabs or len(tabs) >= minimum_count:
                return tabs

        return tabs

    async def ensure_optimizer_workspace(
        self,
        required_tabs: int,
        bootstrap_symbol: str,
        broker: str,
        bootstrap_timeframe: str | None = None,
    ) -> list[OptimizerWorkspaceSlot]:
        # Just verify tabs exist — workers set their own symbol when they pick up a pair.
        # Per-tab bootstrap (switch + set_symbol for every slot) is wasteful and slow
        # when workers=10, adding ~30s per tab before any work starts.
        ready_slots = await self.ensure_optimizer_ready(required_tabs)
        return [
            OptimizerWorkspaceSlot(
                index=slot.index,
                tab_id=slot.tab_id,
                chart_id=slot.chart_id,
                broker=broker.upper(),
                symbol=bootstrap_symbol.upper(),
                timeframe=bootstrap_timeframe,
            )
            for slot in ready_slots
        ]

    async def set_symbol(self, pair: str, broker: str) -> None:
        await self._run_command("symbol", "symbol", f"{broker.upper()}:{pair.upper()}")

    async def set_timeframe(self, value: str) -> None:
        await self._run_command("timeframe", "timeframe", value)
