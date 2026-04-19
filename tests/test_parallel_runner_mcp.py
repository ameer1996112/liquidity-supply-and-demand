from __future__ import annotations

import asyncio
import os

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

    async def close(self) -> None:
        return None


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
    last_instance: "FakeRuntimeState | None" = None

    def __init__(self, results_dir) -> None:
        self.results_dir = results_dir
        self.start_run_calls: list[dict[str, object]] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.states: list[tuple[str, str]] = []
        self.pairs_started: list[tuple[int, str]] = []
        self.pairs_completed: list[tuple[int, str]] = []
        FakeRuntimeState.last_instance = self

    def start_run(self, **kwargs):
        self.start_run_calls.append(kwargs)
        return {"run_id": "run-1"}

    def record_run_event(self, run_id: str, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, payload))

    def set_run_state(self, run_id: str, state: str) -> None:
        self.states.append((run_id, state))

    def mark_pair_started(self, *, run_id: str, worker_id: int, symbol: str) -> None:
        self.pairs_started.append((worker_id, symbol))

    def mark_pair_completed(self, *, run_id: str, worker_id: int, symbol: str) -> None:
        self.pairs_completed.append((worker_id, symbol))


def test_run_parallel_uses_mcp_workspace_slots_to_assign_pages(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(parallel_runner, "results_file_for_broker", lambda broker: tmp_path / "parallel_results.json")
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: 4321)
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
    assert FakeRuntimeState.last_instance is not None
    assert FakeRuntimeState.last_instance.start_run_calls == [
        {
            "args": ["--parallel", "--pairs", "EURUSD,GBPUSD"],
            "mode": "bayesian",
            "workers": 2,
            "log_file": str(parallel_runner.PARALLEL_LOG_FILE),
            "optimizer_pid": os.getpid(),
            "desktop_cdp_pid": 4321,
        }
    ]
    assert connect_urls == [parallel_runner.TRADINGVIEW_DESKTOP_CDP_URL]
    assert worker_pages == [
        (0, "https://www.tradingview.com/chart/AAA/"),
        (1, "https://www.tradingview.com/chart/BBB/"),
    ]


def test_run_parallel_dry_run_launches_workers_without_browser(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(parallel_runner, "results_file_for_broker", lambda broker: tmp_path / "parallel_results.json")
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: None)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)

    controller_used = False

    class ForbiddenController:
        def __init__(self) -> None:
            nonlocal controller_used
            controller_used = True

        async def ensure_optimizer_workspace(self, **kwargs):
            raise AssertionError("MCP workspace prep should not run in dry-run mode")

    class ForbiddenPlaywright:
        def __init__(self) -> None:
            raise AssertionError("Playwright should not be started in dry-run mode")

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", ForbiddenController)
    monkeypatch.setattr(parallel_runner, "async_playwright", ForbiddenPlaywright)
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    async def fake_optimize_pair_on_page(
        page,
        symbol,
        mode,
        n_trials,
        dd_limit,
        dry_run,
        runtime_state=None,
        run_id=None,
        worker_id=None,
    ):
        assert dry_run is True
        assert page is None
        return parallel_runner.BacktestResult(
            symbol=symbol,
            params={"dry_run": True},
            net_profit=999.0,
            total_trades=50,
            win_rate=55.0,
            profit_factor=1.5,
            max_drawdown_pct=5.0,
            score=1.5,
        )

    monkeypatch.setattr(parallel_runner, "optimize_pair_on_page", fake_optimize_pair_on_page)

    result = asyncio.run(
        parallel_runner.run_parallel(
            pairs=["EURUSD"],
            n_workers=1,
            mode="bayesian",
            n_trials=1,
            dd_limit=10.0,
            dry_run=True,
            broker="vantage",
        )
    )

    assert controller_used is False
    assert result["EURUSD"]["params"] == {"dry_run": True}
    assert result["EURUSD"]["score"] == 1.5


def test_run_parallel_reports_desktop_cdp_errors_without_chrome_language(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(parallel_runner, "results_file_for_broker", lambda broker: tmp_path / "parallel_results.json")
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: None)
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
