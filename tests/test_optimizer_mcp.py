import asyncio

from scripts.optimizer.optimizer_mcp import OptimizerMcpController


def test_optimizer_mcp_healthcheck_returns_reason_from_client() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return False, "desktop not open"

    controller = OptimizerMcpController(client=FakeClient())
    ready, reason = asyncio.run(controller.healthcheck())
    assert ready is False
    assert reason == "desktop not open"


def test_optimizer_mcp_ensure_ready_raises_actionable_error() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return False, "TradingView Desktop not detected"

    controller = OptimizerMcpController(client=FakeClient())

    try:
        asyncio.run(controller.ensure_ready())
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "TradingView Desktop not detected" in str(exc)
        assert "Open TradingView Desktop" in str(exc)
        assert "verify the MCP bridge is running" in str(exc)
        assert "retry once the app is ready" in str(exc)


def test_optimizer_mcp_ensure_workspace_bootstraps_tabs() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []
            self.tab_state: list[dict[str, object]] = [
                {
                    "index": 0,
                    "id": "tab-1",
                    "title": "First chart",
                    "url": "https://www.tradingview.com/chart/AAA/",
                    "chart_id": "AAA",
                }
            ]

        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, object]:
            self.calls.append(args)
            if args == ("tab", "list"):
                return {"success": True, "tab_count": len(self.tab_state), "tabs": list(self.tab_state)}
            if args == ("tab", "new"):
                next_index = len(self.tab_state)
                next_tab_number = next_index + 1
                chart_id = ["AAA", "BBB", "CCC", "DDD"][next_index]
                self.tab_state.append(
                    {
                        "index": next_index,
                        "id": f"tab-{next_tab_number}",
                        "title": f"Chart {next_tab_number}",
                        "url": f"https://www.tradingview.com/chart/{chart_id}/",
                        "chart_id": chart_id,
                    }
                )
                return {"success": True, "action": "new_tab_opened", "tab_count": len(self.tab_state), "tabs": list(self.tab_state)}
            if args == ("tab", "switch", "0"):
                return {"success": True, "action": "switched", "index": 0, "tab_id": "tab-1", "chart_id": "AAA"}
            if args == ("tab", "switch", "1"):
                return {"success": True, "action": "switched", "index": 1, "tab_id": "tab-2", "chart_id": "BBB"}
            if args[0] == "symbol":
                return {"success": True}
            if args[0] == "timeframe":
                return {"success": True}
            return {"success": True}

    client = FakeClient()
    controller = OptimizerMcpController(client=client)
    workspace = asyncio.run(
        controller.ensure_optimizer_workspace(
            required_tabs=3,
            bootstrap_symbol="BTCUSDT",
            broker="vantage",
            bootstrap_timeframe="15m",
        )
    )

    assert [slot.index for slot in workspace] == [0, 1, 2]
    assert [slot.tab_id for slot in workspace] == ["tab-1", "tab-2", "tab-3"]
    assert [slot.chart_id for slot in workspace] == ["AAA", "BBB", "CCC"]
    assert [slot.broker for slot in workspace] == ["VANTAGE", "VANTAGE", "VANTAGE"]
    assert [slot.symbol for slot in workspace] == ["BTCUSDT", "BTCUSDT", "BTCUSDT"]
    assert [slot.timeframe for slot in workspace] == ["15m", "15m", "15m"]
    assert client.calls == [
        ("tab", "list"),
        ("tab", "new"),
        ("tab", "list"),
        ("tab", "new"),
        ("tab", "list"),
        ("tab", "switch", "0"),
        ("symbol", "VANTAGE:BTCUSDT"),
        ("timeframe", "15m"),
        ("tab", "switch", "1"),
        ("symbol", "VANTAGE:BTCUSDT"),
        ("timeframe", "15m"),
        ("tab", "switch", "2"),
        ("symbol", "VANTAGE:BTCUSDT"),
        ("timeframe", "15m"),
    ]


def test_optimizer_mcp_raises_on_failed_command_result() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, object]:
            if args == ("symbol", "VANTAGE:BTCUSDT"):
                return {"success": False, "error": "symbol rejected"}
            return {"success": True}

    controller = OptimizerMcpController(client=FakeClient())

    try:
        asyncio.run(controller.set_symbol("BTCUSDT", "vantage"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "TradingView MCP symbol failed during symbol VANTAGE:BTCUSDT: symbol rejected" in str(exc)


def test_optimizer_mcp_set_timeframe_uses_client_transport() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, bool]:
            self.calls.append(args)
            return {"success": True}

    client = FakeClient()
    controller = OptimizerMcpController(client=client)

    asyncio.run(controller.set_timeframe("1h"))

    assert client.calls == [("timeframe", "1h")]


def test_optimizer_mcp_wraps_transport_exception_with_action_context() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, object]:
            raise OSError("transport down")

    controller = OptimizerMcpController(client=FakeClient())

    try:
        asyncio.run(controller.set_timeframe("1h"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "TradingView MCP timeframe failed during timeframe 1h" in str(exc)
        assert "transport down" in str(exc)
