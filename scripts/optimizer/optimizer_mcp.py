from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

from scripts.optimizer.desktop_page import TradingViewDesktopPage
from scripts.optimizer.tradingview_mcp import TradingViewMcpClient

# Map broker names to valid TradingView exchange prefixes.
BROKER_TO_TV_EXCHANGE: dict[str, str] = {
    "VANTAGE": "VANTAGE",
    "OANDA":   "OANDA",
    "FXCM":    "FXCM",
}

# Some brokers expose instruments under a generic feed token even though the
# chart metadata and search filter still identify the real exchange/broker.
BROKER_TO_TV_SYMBOL_PREFIX: dict[str, str] = {
    "VANTAGE": "VANTAGE",
    "OANDA":   "OANDA",
    "FXCM":    "FX",
}


def broker_to_tv_exchange(broker: str) -> str:
    """Resolve a broker name to its TradingView exchange prefix."""
    return BROKER_TO_TV_EXCHANGE.get(broker.upper(), broker.upper())


def broker_to_tv_symbol_prefix(broker: str) -> str:
    """Resolve the symbol prefix TradingView accepts for navigation commands."""
    return BROKER_TO_TV_SYMBOL_PREFIX.get(broker.upper(), broker.upper())


@dataclass(frozen=True)
class OptimizerWorkspaceSlot:
    index: int
    tab_id: str
    chart_id: str | None
    broker: str | None = None
    symbol: str | None = None
    timeframe: str | None = None


class OptimizerMcpController:
    _CDP_TARGETS_URL = "http://127.0.0.1:9222/json/list"
    _TAB_BOOTSTRAP_SETTLE_ATTEMPTS = 12
    _TAB_BOOTSTRAP_SETTLE_SLEEP_SECS = 1.0
    _WORKSPACE_EXPANSION_RETRIES_PER_MISSING_TAB = 3

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

    async def _workspace_target_counts(self) -> tuple[int, int]:
        result = await self._run_command("tab list", "tab", "list")
        tabs = list(result.get("tabs") or [])
        page_target_count = int(result.get("page_target_count") or len(tabs))
        return len(tabs), page_target_count

    @staticmethod
    def _tab_id(tab: dict[str, Any]) -> str:
        return str(tab.get("id") or "")

    def _workspace_bootstrap_error(self, message: str) -> RuntimeError:
        return RuntimeError(
            f"{message}. Retry once TradingView Desktop is ready and tab creation is working."
        )

    @staticmethod
    def _is_chart_page(target: dict[str, Any]) -> bool:
        url = str(target.get("url") or "")
        return "tradingview.com/chart/" in url

    @staticmethod
    def _is_new_tab_shell(target: dict[str, Any]) -> bool:
        url = str(target.get("url") or "")
        return url.startswith("file://") and "/app/new-tab/index.html" in url

    @staticmethod
    def _normalize_page_target(target: dict[str, Any], index: int) -> dict[str, Any]:
        url = str(target.get("url") or "")
        title = str(target.get("title") or "")
        if title.startswith("Live stock"):
            title = title.replace("Live stock, index, futures, Forex and Bitcoin charts on ", "")
        return {
            "index": index,
            "id": str(target.get("id") or ""),
            "title": title,
            "url": url,
            "chart_id": url.split("/chart/")[1].split("/")[0].split("?")[0] if "/chart/" in url else None,
            "kind": "chart" if OptimizerMcpController._is_chart_page(target) else "new_tab",
        }

    async def _list_workspace_pages(self) -> list[dict[str, Any]]:
        def _load_targets() -> list[dict[str, Any]]:
            with urlopen(self._CDP_TARGETS_URL, timeout=5) as response:
                payload = json.load(response)
            return list(payload or [])

        raw_targets = await asyncio.to_thread(_load_targets)
        pages: list[dict[str, Any]] = []
        for index, target in enumerate(raw_targets):
            if target.get("type") != "page":
                continue
            if not (self._is_chart_page(target) or self._is_new_tab_shell(target)):
                continue
            pages.append(self._normalize_page_target(target, index))
        return pages

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

    @staticmethod
    def _pick_bootstrap_shell_page(pages: list[dict[str, Any]]) -> dict[str, Any] | None:
        shell_pages = [
            page
            for page in pages
            if page.get("kind") == "new_tab" and OptimizerMcpController._tab_id(page)
        ]
        if not shell_pages:
            return None
        shell_pages.sort(key=lambda page: int(page.get("index") or -1))
        return shell_pages[-1]

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
            _, before_page_target_count = await self._workspace_target_counts()
            await self._run_command("tab new", "tab", "new")
            tabs, page_target_count = await self._wait_for_tab_count(
                required_tabs=required_tabs,
                minimum_count=before_count + 1,
                minimum_page_targets=before_page_target_count + 1,
            )
            if len(tabs) <= before_count and page_target_count <= before_page_target_count:
                raise self._workspace_bootstrap_error(
                    "TradingView MCP tab creation did not increase the available chart or page target count"
                )
        return self._build_workspace_slots(tabs[:required_tabs])

    async def _wait_for_tab_count(
        self,
        *,
        required_tabs: int,
        minimum_count: int,
        minimum_page_targets: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Poll tab list because updated TradingView can open an intermediate new-tab shell first."""
        result = await self._run_command("tab list", "tab", "list")
        tabs = list(result.get("tabs") or [])
        page_target_count = int(result.get("page_target_count") or len(tabs))
        if (
            len(tabs) >= required_tabs
            or len(tabs) >= minimum_count
            or page_target_count >= minimum_page_targets
        ):
            return tabs, page_target_count

        for _ in range(self._TAB_BOOTSTRAP_SETTLE_ATTEMPTS - 1):
            await asyncio.sleep(self._TAB_BOOTSTRAP_SETTLE_SLEEP_SECS)
            result = await self._run_command("tab list", "tab", "list")
            tabs = list(result.get("tabs") or [])
            page_target_count = int(result.get("page_target_count") or len(tabs))
            if (
                len(tabs) >= required_tabs
                or len(tabs) >= minimum_count
                or page_target_count >= minimum_page_targets
            ):
                return tabs, page_target_count

        return tabs, page_target_count

    async def _wait_for_new_workspace_tab(
        self,
        *,
        known_tab_ids: set[str],
        minimum_page_targets: int,
    ) -> dict[str, Any]:
        """Wait for a brand-new chart tab to appear after `tab new`."""
        for _ in range(self._TAB_BOOTSTRAP_SETTLE_ATTEMPTS):
            result = await self._run_command("tab list", "tab", "list")
            tabs = list(result.get("tabs") or [])
            page_target_count = int(result.get("page_target_count") or len(tabs))
            fresh_tabs = [tab for tab in tabs if self._tab_id(tab) not in known_tab_ids]
            if fresh_tabs:
                fresh_tabs.sort(key=lambda tab: int(tab.get("index") or -1))
                return fresh_tabs[-1]
            if page_target_count >= minimum_page_targets:
                await asyncio.sleep(self._TAB_BOOTSTRAP_SETTLE_SLEEP_SECS)
                continue
            await asyncio.sleep(self._TAB_BOOTSTRAP_SETTLE_SLEEP_SECS)

        raise self._workspace_bootstrap_error(
            "TradingView MCP created a new page target but never exposed a fresh chart tab"
        )

    async def _wait_for_new_workspace_page(
        self,
        *,
        known_page_ids: set[str],
    ) -> dict[str, Any]:
        """Wait for a fresh TradingView page target, including new-tab shell pages."""
        for _ in range(self._TAB_BOOTSTRAP_SETTLE_ATTEMPTS):
            pages = await self._list_workspace_pages()
            fresh_pages = [page for page in pages if self._tab_id(page) not in known_page_ids]
            if fresh_pages:
                shell_pages = [page for page in fresh_pages if page.get("kind") == "new_tab"]
                if shell_pages:
                    return shell_pages[0]
                return fresh_pages[0]
            await asyncio.sleep(self._TAB_BOOTSTRAP_SETTLE_SLEEP_SECS)

        raise self._workspace_bootstrap_error(
            "TradingView MCP created no fresh TradingView page after tab creation"
        )

    # Brokers whose symbols can't be loaded via URL query string.
    _SEARCH_DIALOG_BROKERS = {"FXCM"}

    @staticmethod
    def _bootstrap_chart_url(
        *,
        bootstrap_chart_id: str | None,
        bootstrap_symbol: str,
        broker: str,
    ) -> str:
        tv_exchange = broker_to_tv_exchange(broker)
        # Brokers that require the search dialog can't be bootstrapped via URL.
        # Just open a blank chart; the worker's _switch_symbol will navigate.
        if tv_exchange.upper() in OptimizerMcpController._SEARCH_DIALOG_BROKERS:
            if bootstrap_chart_id:
                return f"https://www.tradingview.com/chart/{bootstrap_chart_id}/"
            return "https://www.tradingview.com/chart/"
        symbol_token = f"{tv_exchange}%3A{bootstrap_symbol.upper()}"
        if bootstrap_chart_id:
            return f"https://www.tradingview.com/chart/{bootstrap_chart_id}/?symbol={symbol_token}"
        return f"https://www.tradingview.com/chart/?symbol={symbol_token}"

    async def _promote_new_tab_to_chart(
        self,
        *,
        shell_tab: dict[str, Any],
        bootstrap_chart_id: str | None,
        bootstrap_symbol: str,
        broker: str,
        known_chart_ids: set[str],
        known_page_ids: set[str],
    ) -> dict[str, Any]:
        shell_tab_id = self._tab_id(shell_tab)
        bootstrap_url = self._bootstrap_chart_url(
            bootstrap_chart_id=bootstrap_chart_id,
            bootstrap_symbol=bootstrap_symbol,
            broker=broker,
        )
        page = TradingViewDesktopPage(tab_id=shell_tab_id, chart_id=bootstrap_chart_id)
        await page.goto(bootstrap_url)

        for _ in range(self._TAB_BOOTSTRAP_SETTLE_ATTEMPTS * 2):
            pages = await self._list_workspace_pages()
            for candidate in pages:
                candidate_id = self._tab_id(candidate)
                if candidate.get("kind") != "chart":
                    continue
                if candidate_id == shell_tab_id:
                    return candidate
                if candidate_id not in known_chart_ids and candidate_id not in known_page_ids:
                    return candidate
            await asyncio.sleep(self._TAB_BOOTSTRAP_SETTLE_SLEEP_SECS)

        raise self._workspace_bootstrap_error(
            "TradingView new-tab shell did not become a chart tab after bootstrap navigation"
        )

    async def ensure_optimizer_workspace(
        self,
        required_tabs: int,
        bootstrap_symbol: str,
        broker: str,
        bootstrap_timeframe: str | None = None,
    ) -> list[OptimizerWorkspaceSlot]:
        await self.ensure_ready()
        existing_tabs = await self._list_workspace_tabs()
        existing_pages = await self._list_workspace_pages()
        reusable_tabs = sorted(
            existing_tabs,
            key=lambda tab: int(tab.get("index") or -1),
        )[-required_tabs:]
        bootstrap_chart_id = next(
            (str(tab.get("chart_id") or "") for tab in existing_tabs if tab.get("chart_id")),
            None,
        ) or None
        known_tab_ids = {self._tab_id(tab) for tab in existing_tabs}
        known_page_ids = {self._tab_id(page) for page in existing_pages}
        fresh_tabs: list[dict[str, Any]] = []

        if not reusable_tabs and required_tabs > 0:
            bootstrap_shell = self._pick_bootstrap_shell_page(existing_pages)
            if bootstrap_shell is not None:
                try:
                    bootstrap_tab = await self._promote_new_tab_to_chart(
                        shell_tab=bootstrap_shell,
                        bootstrap_chart_id=bootstrap_chart_id,
                        bootstrap_symbol=bootstrap_symbol,
                        broker=broker,
                        known_chart_ids=known_tab_ids,
                        known_page_ids=known_page_ids,
                    )
                except RuntimeError as exc:
                    raise self._workspace_bootstrap_error(
                        f"TradingView Supercharts bootstrap failed: {exc}"
                    ) from exc

                reusable_tabs = [bootstrap_tab]
                bootstrap_chart_id = str(bootstrap_tab.get("chart_id") or "") or bootstrap_chart_id
                known_tab_ids.add(self._tab_id(bootstrap_tab))
                known_page_ids.add(self._tab_id(bootstrap_tab))

        missing_tabs = max(required_tabs - len(reusable_tabs), 0)

        for _ in range(missing_tabs):
            promoted_tab: dict[str, Any] | None = None
            last_error: RuntimeError | None = None

            for _attempt in range(self._WORKSPACE_EXPANSION_RETRIES_PER_MISSING_TAB):
                await self._run_command("tab new", "tab", "new")
                fresh_page = await self._wait_for_new_workspace_page(
                    known_page_ids=known_page_ids,
                )
                known_page_ids.add(self._tab_id(fresh_page))

                if fresh_page.get("kind") == "chart":
                    promoted_tab = fresh_page
                    break

                try:
                    promoted_tab = await self._promote_new_tab_to_chart(
                        shell_tab=fresh_page,
                        bootstrap_chart_id=bootstrap_chart_id,
                        bootstrap_symbol=bootstrap_symbol,
                        broker=broker,
                        known_chart_ids=known_tab_ids,
                        known_page_ids=known_page_ids,
                    )
                    known_page_ids.add(self._tab_id(promoted_tab))
                    break
                except RuntimeError as exc:
                    last_error = exc

            if promoted_tab is None:
                failed_slot = len(reusable_tabs) + len(fresh_tabs) + 1
                detail = str(last_error) if last_error else "unknown workspace expansion error"
                raise RuntimeError(
                    f"Failed to provision requested TradingView chart tab "
                    f"{failed_slot}/{required_tabs}: {detail}"
                )

            fresh_tabs.append(promoted_tab)
            known_tab_ids.add(self._tab_id(promoted_tab))

        ready_tabs = sorted(
            [*reusable_tabs, *fresh_tabs],
            key=lambda tab: int(tab.get("index") or -1),
        )
        if len(ready_tabs) != required_tabs:
            raise RuntimeError(
                f"Requested {required_tabs} TradingView chart tab(s) but only prepared {len(ready_tabs)}"
            )
        ready_slots = self._build_workspace_slots(ready_tabs)
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
        tv_symbol_prefix = broker_to_tv_symbol_prefix(broker)
        await self._run_command("symbol", "symbol", f"{tv_symbol_prefix}:{pair.upper()}")

    async def set_timeframe(self, value: str) -> None:
        await self._run_command("timeframe", "timeframe", value)
