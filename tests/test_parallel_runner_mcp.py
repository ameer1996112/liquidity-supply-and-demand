from __future__ import annotations

import asyncio

import pytest

from scripts.optimizer import parallel_runner
from scripts.optimizer.optimizer_mcp import OptimizerWorkspaceSlot


class FakePage:
    def __init__(self, url: str) -> None:
        self.url = url


class FakeContext:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages


class FakeBrowser:
    def __init__(self, pages: list[FakePage]) -> None:
        self.contexts = [FakeContext(pages)]


class FakeChromium:
    def __init__(self, browser: FakeBrowser, connect_urls: list[str]) -> None:
        self._browser = browser
        self._connect_urls = connect_urls

    async def connect_over_cdp(self, url: str) -> FakeBrowser:
        self._connect_urls.append(url)
        return self._browser


class FakePlaywright:
    def __init__(self, browser: FakeBrowser, connect_urls: list[str]) -> None:
        self.chromium = FakeChromium(browser, connect_urls)

    async def __aenter__(self) -> FakePlaywright:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeRuntimeState:
    def __init__(self, results_dir) -> None:
        self.results_dir = results_dir
        self.start_run_calls: list[dict[str, object]] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.states: list[tuple[str, str]] = []

    def start_run(self, **kwargs):
        self.start_run_calls.append(kwargs)
        return {"run_id": "run-1"}

    def record_run_event(self, run_id: str, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, payload))

    def set_run_state(self, run_id: str, state: str) -> None:
        self.states.append((run_id, state))


def test_run_parallel_uses_mcp_workspace_slots_to_assign_pages(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(parallel_runner, "results_file_for_broker", lambda broker: tmp_path / "parallel_results.json")
    monkeypatch.setattr(parallel_runner, "detect_cdp_pid", lambda: 4321)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)
    monkeypatch.setattr(parallel_runner, "ensure_tradingview_tabs", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ensure_tradingview_tabs should not be used")))

    controller_calls: list[dict[str, object]] = []

    class FakeController:
        async def ensure_optimizer_workspace(self, **kwargs):
            controller_calls.append(kwargs)
            return [
                OptimizerWorkspaceSlot(index=0, tab_id="tab-a", chart_id="AAA"),
                OptimizerWorkspaceSlot(index=1, tab_id="tab-b", chart_id="BBB"),
            ]

    connect_urls: list[str] = []
    browser = FakeBrowser(
        [
            FakePage("https://www.tradingview.com/chart/BBB/"),
            FakePage("https://www.tradingview.com/chart/AAA/"),
        ]
    )
    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())
    monkeypatch.setattr(parallel_runner, "async_playwright", lambda: FakePlaywright(browser, connect_urls))
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    worker_pages: list[tuple[int, str]] = []

    async def fake_worker_task(*args, **kwargs) -> None:
        worker_pages.append((kwargs["worker_id"], kwargs["page"].url))

    monkeypatch.setattr(parallel_runner, "worker_task", fake_worker_task)

    result = asyncio.run(
        parallel_runner.run_parallel(
            pairs=["EURUSD", "GBPUSD"],
            n_workers=2,
            mode="bayesian",
            n_trials=1,
            dd_limit=10.0,
            dry_run=False,
            broker="vantage",
            raw_args=["--pairs", "EURUSD,GBPUSD"],
        )
    )

    assert result == {}
    assert controller_calls == [
        {
            "required_tabs": 2,
            "bootstrap_symbol": "EURUSD",
            "broker": "vantage",
        }
    ]
    assert connect_urls == [parallel_runner.TRADINGVIEW_DESKTOP_CDP_URL]
    assert worker_pages == [
        (0, "https://www.tradingview.com/chart/AAA/"),
        (1, "https://www.tradingview.com/chart/BBB/"),
    ]


def test_run_parallel_reports_desktop_cdp_errors_without_chrome_language(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(parallel_runner, "results_file_for_broker", lambda broker: tmp_path / "parallel_results.json")
    monkeypatch.setattr(parallel_runner, "detect_cdp_pid", lambda: None)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)

    controller_calls: list[dict[str, object]] = []

    class FakeController:
        async def ensure_optimizer_workspace(self, **kwargs):
            controller_calls.append(kwargs)
            return [
                OptimizerWorkspaceSlot(index=0, tab_id="tab-a", chart_id="AAA"),
            ]

    class FailingChromium:
        async def connect_over_cdp(self, url: str):
            raise OSError("desktop bridge unavailable")

    class FailingPlaywright:
        def __init__(self) -> None:
            self.chromium = FailingChromium()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())
    monkeypatch.setattr(parallel_runner, "async_playwright", lambda: FailingPlaywright())
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            parallel_runner.run_parallel(
                pairs=["EURUSD"],
                n_workers=1,
                mode="bayesian",
                n_trials=1,
                dd_limit=10.0,
                dry_run=False,
                broker="vantage",
            )
        )

    message = str(exc_info.value)
    assert "TradingView Desktop CDP target" in message
    assert "Chrome" not in message
    assert "Google Chrome" not in message
    assert controller_calls == [
        {
            "required_tabs": 1,
            "bootstrap_symbol": "EURUSD",
            "broker": "vantage",
        }
    ]
