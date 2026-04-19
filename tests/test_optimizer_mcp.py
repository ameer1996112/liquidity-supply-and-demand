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

        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, bool]:
            self.calls.append(args)
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
    assert [slot.broker for slot in workspace] == ["VANTAGE", "VANTAGE", "VANTAGE"]
    assert [slot.symbol for slot in workspace] == ["BTCUSDT", "BTCUSDT", "BTCUSDT"]
    assert [slot.timeframe for slot in workspace] == ["15m", "15m", "15m"]
    assert client.calls == [
        ("symbol", "VANTAGE:BTCUSDT"),
        ("timeframe", "15m"),
        ("symbol", "VANTAGE:BTCUSDT"),
        ("timeframe", "15m"),
        ("symbol", "VANTAGE:BTCUSDT"),
        ("timeframe", "15m"),
    ]


def test_optimizer_mcp_raises_on_failed_command_result() -> None:
    class FakeClient:
        async def healthcheck(self) -> tuple[bool, str]:
            return True, "ok"

        async def run(self, *args: str) -> dict[str, object]:
            return {"success": False, "error": "symbol rejected"}

    controller = OptimizerMcpController(client=FakeClient())

    try:
        asyncio.run(controller.set_symbol("BTCUSDT", "vantage"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "TradingView MCP symbol VANTAGE:BTCUSDT failed: symbol rejected" in str(exc)


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
