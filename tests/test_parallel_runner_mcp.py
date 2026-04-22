from __future__ import annotations

import asyncio
import json
import os

import pytest

from scripts.optimizer import parallel_runner
from scripts.optimizer.desktop_page import TradingViewDesktopPage
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
    monkeypatch.setattr(
        parallel_runner,
        "results_file_for_broker",
        lambda broker, results_label=None: tmp_path / (
            "parallel_results.json" if results_label is None else f"parallel_results_{results_label}.json"
        ),
    )
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

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    worker_pages: list[tuple[int, str, str]] = []

    async def fake_worker_task(*args, **kwargs) -> None:
        page = kwargs["page"]
        assert isinstance(page, TradingViewDesktopPage)
        worker_pages.append((kwargs["worker_id"], page.tab_id, page.url))

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
            results_label="run-123",
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
    assert worker_pages == [
        (0, "tab-a", "https://www.tradingview.com/chart/AAA/"),
        (1, "tab-b", "https://www.tradingview.com/chart/BBB/"),
    ]


def test_run_parallel_clamps_worker_tasks_to_prepared_mcp_sessions(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(
        parallel_runner,
        "results_file_for_broker",
        lambda broker, results_label=None: tmp_path / (
            "parallel_results.json" if results_label is None else f"parallel_results_{results_label}.json"
        ),
    )
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: 4321)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    class FakeController:
        async def ensure_optimizer_workspace(self, **kwargs):
            return [OptimizerWorkspaceSlot(index=0, tab_id="tab-a", chart_id="AAA")]

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())

    worker_ids: list[int] = []

    async def fake_worker_task(*args, **kwargs) -> None:
        worker_ids.append(kwargs["worker_id"])

    monkeypatch.setattr(parallel_runner, "worker_task", fake_worker_task)

    result = asyncio.run(
        parallel_runner.run_parallel(
            pairs=["EURUSD", "GBPUSD"],
            n_workers=3,
            mode="bayesian",
            n_trials=1,
            dd_limit=10.0,
            dry_run=False,
            broker="vantage",
            results_label="run-clamped",
        )
    )

    assert result == {}
    assert worker_ids == [0]


def test_run_parallel_dry_run_launches_workers_without_browser(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(
        parallel_runner,
        "results_file_for_broker",
        lambda broker, results_label=None: tmp_path / (
            "parallel_results.json" if results_label is None else f"parallel_results_{results_label}.json"
        ),
    )
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
        broker="vantage",
        backtest_range="365d",
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


def test_run_parallel_surfaces_workspace_errors_without_chrome_language(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(
        parallel_runner,
        "results_file_for_broker",
        lambda broker, results_label=None: tmp_path / (
            "parallel_results.json" if results_label is None else f"parallel_results_{results_label}.json"
        ),
    )
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: None)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)

    controller_calls: list[dict[str, object]] = []

    class FakeController:
        async def ensure_optimizer_workspace(self, **kwargs):
            controller_calls.append(kwargs)
            raise RuntimeError("desktop bridge unavailable")

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())
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
    assert "desktop bridge unavailable" in message
    assert "Chrome" not in message
    assert "Google Chrome" not in message
    assert controller_calls == [
        {
            "required_tabs": 1,
            "bootstrap_symbol": "EURUSD",
            "broker": "vantage",
        }
    ]


def test_worker_task_retries_when_optimizer_returns_no_result(monkeypatch, tmp_path) -> None:
    results: dict[str, object] = {}
    error_log: list[dict[str, object]] = []
    pair_queue: asyncio.Queue[str] = asyncio.Queue()
    asyncio.run(pair_queue.put("EURUSD"))

    monkeypatch.setattr(parallel_runner, "MAX_PAIR_RETRIES", 0)

    async def no_sleep(*_args, **_kwargs) -> None:
        return None

    async def fake_optimize_pair_on_page(*args, **kwargs):
        return None

    monkeypatch.setattr(parallel_runner.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(parallel_runner, "optimize_pair_on_page", fake_optimize_pair_on_page)

    asyncio.run(
        parallel_runner.worker_task(
            worker_id=0,
            page=None,
            pair_queue=pair_queue,
            results=results,
            results_file=tmp_path / "parallel_results.json",
            latest_results_file=tmp_path / "parallel_results_latest.json",
            results_lock=asyncio.Lock(),
            error_log=error_log,
            broker="vantage",
            mode="bayesian",
            n_trials=1,
            dd_limit=10.0,
            dry_run=True,
            runtime_state=None,
            run_id=None,
        )
    )

    assert results == {}
    assert error_log == [
        {
            "symbol": "EURUSD",
            "worker": 0,
            "error": "No valid optimization result produced for EURUSD",
        }
    ]


def test_run_parallel_uses_run_scoped_results_file_for_resume(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(parallel_runner, "setup_logging", lambda: None)
    monkeypatch.setattr(parallel_runner, "detect_desktop_cdp_pid", lambda: None)
    monkeypatch.setattr(parallel_runner, "WORKER_STARTUP_DELAY", 0)

    base_results = tmp_path / "parallel_results_oanda.json"
    base_results.write_text(json.dumps({"EURUSD": {"score": 1.0}}))
    run_results = tmp_path / "parallel_results_oanda_run-42.json"

    monkeypatch.setattr(
        parallel_runner,
        "results_file_for_broker",
        lambda broker, results_label=None: run_results if results_label else base_results,
    )

    class FakeController:
        async def ensure_optimizer_workspace(self, **kwargs):
            return [OptimizerWorkspaceSlot(index=0, tab_id="tab-a", chart_id="AAA")]

    monkeypatch.setattr(parallel_runner, "OptimizerMcpController", lambda: FakeController())
    monkeypatch.setattr(parallel_runner, "OptimizerRuntimeState", FakeRuntimeState)

    async def fake_worker_task(*args, **kwargs) -> None:
        kwargs["results"]["EURUSD"] = {"score": 2.0, "params": {"stage": 2}}
        parallel_runner.write_results_snapshot(
            kwargs["results"],
            kwargs["results_file"],
            latest_results_file=kwargs["latest_results_file"],
        )

    monkeypatch.setattr(parallel_runner, "worker_task", fake_worker_task)

    result = asyncio.run(
        parallel_runner.run_parallel(
            pairs=["EURUSD"],
            n_workers=1,
            mode="bayesian",
            n_trials=1,
            dd_limit=10.0,
            dry_run=False,
            broker="oanda",
            results_label="run-42",
        )
    )

    assert result["EURUSD"]["score"] == 2.0
    assert json.loads(run_results.read_text())["EURUSD"]["score"] == 2.0
    assert json.loads(base_results.read_text())["EURUSD"]["score"] == 2.0
