from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.tab_worker import ApplyOutcome, TabWorker
from scripts.optimizer import tab_worker as tab_worker_module


if "playwright.async_api" not in sys.modules:
    playwright_module = ModuleType("playwright")
    async_api_module = ModuleType("playwright.async_api")

    async def _async_playwright():  # pragma: no cover - import shim only
        raise RuntimeError("playwright shim should not be called in tests")

    async_api_module.async_playwright = _async_playwright
    async_api_module.Page = object
    async_api_module.Browser = object
    sys.modules["playwright"] = playwright_module
    sys.modules["playwright.async_api"] = async_api_module

from scripts.optimizer.optimizer import TradingViewOptimizer


class DummyOptimizer:
    pass


class DummyPage:
    def __init__(self, title: str = "EURJPY 5 Vantage", url: str = "") -> None:
        self._title = title
        self.url = url or "https://www.tradingview.com/chart/test/?symbol=VANTAGE%3AEURJPY"
        self.evaluate_called = False

    async def title(self) -> str:
        return self._title

    async def evaluate(self, script: str):  # pragma: no cover - guard rail
        self.evaluate_called = True
        raise AssertionError("metrics should not be read when the symbol mismatches")


class MetricsPage(DummyPage):
    def __init__(self, title: str = "EURJPY 5 Vantage", metrics: dict | None = None) -> None:
        super().__init__(title=title)
        self._metrics = metrics or {}

    async def evaluate(self, script: str):
        return self._metrics


class FallbackMetricsPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURJPY 5 Vantage")

    async def evaluate(self, script: str):
        if script == tab_worker_module._JS_COLLECT_METRICS:
            return {
                "Net profit": "Net profit +123.45",
                "Total trades": "Total trades 42",
                "Profitable trades": "Profitable trades 55%",
                "Profit factor": "Profit factor 1.8",
                "Max equity drawdown": "1,250|Max equity drawdown 2.5%",
            }
        raise AssertionError(f"unexpected script in FallbackMetricsPage: {script[:120]}")


class MenuSettingsPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.dialog_open = False
        self.menu_open = False

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            return []
        if "__tvPickSettingsDialog(true)" in script or "__tvPickSettingsDialog(false)" in script:
            return self.dialog_open
        if "const rect = d.getBoundingClientRect?.();" in script:
            return self.dialog_open
        if "strategyButton.click()" in script:
            self.menu_open = True
            return True
        if "text === 'Settings…'" in script:
            if not self.menu_open:
                return False
            self.dialog_open = True
            return True
        raise AssertionError(f"unexpected script in MenuSettingsPage: {script[:120]}")


class DirectLegendSettingsPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.dialog_open = False

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            return []
        if "__tvPickSettingsDialog(true)" in script or "__tvPickSettingsDialog(false)" in script:
            return self.dialog_open
        if "const rect = d.getBoundingClientRect?.();" in script:
            return self.dialog_open
        if "const titles = Array.from" in script and "bestButton.click()" in script:
            self.dialog_open = True
            return True
        raise AssertionError(f"unexpected script in DirectLegendSettingsPage: {script[:120]}")


class AriaLegendSettingsMouseFallbackPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.dialog_open = False
        self.mouse_clicks: list[tuple[int, int, bool]] = []

        class _Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float, double: bool = False) -> None:
                self.outer.mouse_clicks.append((int(round(x)), int(round(y)), double))
                if not double:
                    self.outer.dialog_open = True

        self.mouse = _Mouse(self)

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            return []
        if "__tvPickSettingsDialog(true)" in script or "__tvPickSettingsDialog(false)" in script:
            return self.dialog_open
        if "const titles = Array.from" in script and "bestButton.click()" in script:
            return False
        if "const buttons = Array.from" in script and "return {x: box.x + box.width / 2, y: box.y + box.height / 2};" in script:
            return {"x": 410, "y": 260}
        raise AssertionError(f"unexpected script in AriaLegendSettingsMouseFallbackPage: {script[:120]}")


class StrategyReportPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.report_open = False

        class _Keyboard:
            async def press(self, key_combo: str) -> None:
                return None

        self.keyboard = _Keyboard()

    async def evaluate(self, script: str):
        if "document.querySelector('[data-name=\"report-range-button\"]')" in script:
            return self.report_open
        if "const metricLabels = [" in script:
            return self.report_open
        if "item.text === 'Strategy Tester'" in script and "item.text === 'Strategy Report'" in script:
            self.report_open = True
            return True
        raise AssertionError(f"unexpected script in StrategyReportPage: {script[:120]}")


class MouseStrategyReportPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.report_open = False
        self.mouse_clicks: list[tuple[int, int]] = []

        class _Keyboard:
            async def press(self, key_combo: str) -> None:
                return None

        class _Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float, double: bool = False) -> None:
                self.outer.mouse_clicks.append((int(round(x)), int(round(y))))
                self.outer.report_open = True

        self.keyboard = _Keyboard()
        self.mouse = _Mouse(self)

    async def evaluate(self, script: str):
        if "document.querySelector('[data-name=\"report-range-button\"]')" in script:
            return self.report_open
        if "const metricLabels = [" in script:
            return self.report_open
        if "item.text === 'Strategy Tester'" in script and "item.text === 'Strategy Report'" in script:
            return {"clicked": True, "x": 990, "y": 748}
        raise AssertionError(f"unexpected script in MouseStrategyReportPage: {script[:120]}")


class DesktopClientSwitchPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="TradingView")
        self.url = "https://www.tradingview.com/chart/test123/?symbol=OANDA%3AEURUSD"
        self.goto_called = False
        self.symbol = "EURUSD"
        self.tab_id = "desktop-tab"

        class _Client:
            def __init__(self, outer) -> None:
                self.outer = outer
                self.calls: list[tuple[str, ...]] = []

            async def run(self, *args: str):
                self.calls.append(args)
                if args and args[0] == "symbol":
                    self.outer.symbol = args[1].split(":")[-1]
                return {"success": True}

        self._client = _Client(self)

    async def evaluate(self, script: str, *_args):
        if ".symbol?.() || ''" in script:
            return self.symbol
        if "normalize(el.textContent) === 'S&D Algo [Pro]'" in script:
            return True
        if script == tab_worker_module._JS_FIND_LOADING:
            return None
        if script == tab_worker_module._JS_HAS_REPORT_TIMEOUT:
            return False
        return None

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_called = True
        self.url = url


class DesktopTimeframePage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="TradingView")
        self.tab_id = "desktop-tab"
        self.resolution = "60"

        class _Client:
            def __init__(self, outer) -> None:
                self.outer = outer
                self.calls: list[tuple[str, ...]] = []

            async def run(self, *args: str):
                self.calls.append(args)
                if args == ("timeframe", "5"):
                    self.outer.resolution = "5"
                return {"success": True}

        self._client = _Client(self)

    async def evaluate(self, script: str, *_args):
        if ".resolution?.() || ''" in script:
            return self.resolution
        if "const candidates = Array.from(document.querySelectorAll('button, [role=\"button\"], [role=\"tab\"]'))" in script:
            return False
        return None


class FxcmSearchPage(DummyPage):
    def __init__(self, *, broker_after: str = "FXCM", error_badge: bool = False, search_success: bool = True) -> None:
        super().__init__(title="TradingView", url="https://www.tradingview.com/chart/test123/?symbol=OANDA%3AUSDJPY")
        self.tab_id = "desktop-tab"
        self.symbol = "USDJPY"
        self.broker = "OANDA"
        self.resolution = "5"
        self.search_open = False
        self.query = ""
        self.search_success = search_success
        self.broker_after = broker_after
        self.error_badge = error_badge
        self.goto_called = False

    async def title(self) -> str:
        return f"{self.symbol} 5 {self.broker}"

    async def evaluate(self, script: str, *args):
        if ".symbol?.() || ''" in script:
            return f"{self.broker}:{self.symbol}"
        if ".resolution?.() || ''" in script:
            return self.resolution
        if "normalize(el.textContent) === 'S&D Algo [Pro]'" in script:
            return True
        if script == tab_worker_module._JS_FIND_LOADING:
            return None
        if script == tab_worker_module._JS_HAS_REPORT_TIMEOUT:
            return False
        if "const hasSearch = () => {" in script:
            self.search_open = True
            return True
        if "const { targetSymbol, targetBroker } = payload;" in script:
            target_symbol = args[0]["targetSymbol"]
            if not self.search_success:
                return {"state": "no-match"}
            self.query = target_symbol
            self.symbol = target_symbol
            self.broker = self.broker_after
            self.url = f"https://www.tradingview.com/chart/test123/?symbol={self.broker}%3A{self.symbol}"
            return {"state": "selected"}
        if "const normalize = (text) => (text || '').replace(/\\\\s+/g, ' ').trim().toLowerCase();" in script and "invalid symbol" in script:
            return self.error_badge
        return None

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_called = True
        self.url = url


class BlankThenCustomProfilePage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.profile_reads = 0
        self.escape_presses = 0

        class _Keyboard:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def press(self, key_combo: str) -> None:
                if key_combo == "Escape":
                    self.outer.escape_presses += 1

        self.keyboard = _Keyboard(self)

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            return []
        if "const combo = dialog.querySelector('button[role=\"combobox\"]');" in script:
            self.profile_reads += 1
            if self.profile_reads < 3:
                return ""
            return "Custom"
        if "el.textContent?.trim() === 'Custom'" in script:
            return True
        if "__tvPickSettingsDialog(true)" in script:
            return self.profile_reads >= 3
        raise AssertionError(f"unexpected script in BlankThenCustomProfilePage: {script[:120]}")


class ReloadThenCustomProfilePage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.profile_reads = 0
        self.escape_presses = 0
        self.reloaded = False

        class _Keyboard:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def press(self, key_combo: str) -> None:
                if key_combo == "Escape":
                    self.outer.escape_presses += 1

        self.keyboard = _Keyboard(self)

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            return []
        if "const combo = dialog.querySelector('button[role=\"combobox\"]');" in script:
            self.profile_reads += 1
            if not self.reloaded:
                return ""
            return "Custom"
        if "el.textContent?.trim() === 'Custom'" in script:
            return True
        if "__tvPickSettingsDialog(true)" in script:
            return self.reloaded
        raise AssertionError(f"unexpected script in ReloadThenCustomProfilePage: {script[:120]}")


class ChartSettingsPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.chart_dialog_open = True
        self.mouse_clicks: list[tuple[int, int]] = []

        class _Keyboard:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def press(self, key_combo: str) -> None:
                if key_combo == "Escape":
                    self.outer.chart_dialog_open = False

        class _Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float, double: bool = False) -> None:
                self.outer.mouse_clicks.append((int(round(x)), int(round(y))))
                self.outer.chart_dialog_open = False

        self.keyboard = _Keyboard(self)
        self.mouse = _Mouse(self)

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            if not self.chart_dialog_open:
                return []
            return [
                {
                    "score": -100,
                    "ready": False,
                    "chartSettings": True,
                    "combo": False,
                    "tabs": [
                        "symbol",
                        "status line",
                        "scales and lines",
                        "canvas",
                        "trading",
                        "alerts",
                    ],
                    "text": "Settings Symbol Status line Scales and lines Canvas Trading Alerts Events",
                }
            ]
        if "__tvPickSettingsDialog(true)" in script or "__tvPickSettingsDialog(false)" in script:
            return False
        if "reason: 'top-right-fallback'" in script:
            if not self.chart_dialog_open:
                return None
            return {"x": 1188, "y": 310, "reason": "top-right-fallback"}
        raise AssertionError(f"unexpected script in ChartSettingsPage: {script[:120]}")


class WrongDialogThenReopenPage(DummyPage):
    def __init__(self) -> None:
        super().__init__(title="EURUSD 5 OANDA")
        self.profile_reads = 0
        self.wrong_dialog_open = True
        self.open_attempts = 0

        class _Keyboard:
            async def press(self, key_combo: str) -> None:
                return None

        self.keyboard = _Keyboard()

    async def evaluate(self, script: str):
        if "return __tvDescribeSettingsDialogs();" in script:
            if self.wrong_dialog_open:
                return [
                    {
                        "score": -100,
                        "ready": False,
                        "chartSettings": True,
                        "combo": False,
                        "tabs": ["symbol", "status line", "scales and lines", "canvas", "trading"],
                        "text": "Settings Symbol Status line Scales and lines Canvas Trading",
                    }
                ]
            return []
        if "const combo = dialog.querySelector('button[role=\"combobox\"]');" in script:
            self.profile_reads += 1
            return "Custom" if not self.wrong_dialog_open else ""
        if "el.textContent?.trim() === 'Custom'" in script:
            return True
        if "__tvPickSettingsDialog(true)" in script:
            return not self.wrong_dialog_open
        if "__tvPickSettingsDialog(false)" in script:
            return not self.wrong_dialog_open
        if "reason: 'top-right-fallback'" in script:
            if self.wrong_dialog_open:
                return {"x": 1188, "y": 310, "reason": "top-right-fallback"}
            return None
        raise AssertionError(f"unexpected script in WrongDialogThenReopenPage: {script[:120]}")


def test_apply_params_rejects_unchanged_final_results_hash(monkeypatch) -> None:
    page = DummyPage()
    worker = TabWorker(page, DummyOptimizer())

    async def always_true() -> bool:
        return True

    async def same_hash() -> str:
        return "deadbeef"

    async def no_op(*args, **kwargs):  # pragma: no cover - test shim
        return None

    monkeypatch.setattr(page, "evaluate", no_op)
    monkeypatch.setattr(worker, "_open_settings", always_true)
    monkeypatch.setattr(worker, "_ensure_custom_profile", always_true)
    monkeypatch.setattr(worker, "_click_ok", always_true)
    monkeypatch.setattr(worker, "_wait_dialog_close", always_true)
    monkeypatch.setattr(worker, "_wait_for_update_complete", always_true)
    monkeypatch.setattr(worker, "_get_results_hash", same_hash)

    outcome = asyncio.run(worker._apply_params({}))

    assert outcome == ApplyOutcome(
        ok=False,
        fresh=False,
        reason="stale_result_hash",
        attempt=3,
        results_hash_before="deadbeef",
        results_hash_after="deadbeef",
    )


def test_apply_params_fails_when_settings_dialog_does_not_close(monkeypatch) -> None:
    page = DummyPage()
    worker = TabWorker(page, DummyOptimizer())
    update_wait_calls: list[str] = []

    async def always_true() -> bool:
        return True

    async def dialog_stays_open() -> bool:
        return False

    async def fake_wait_for_update_complete() -> bool:
        update_wait_calls.append("waited")
        return True

    async def changing_hash() -> str:
        return "abc123"

    async def no_op(*args, **kwargs):  # pragma: no cover - test shim
        return None

    monkeypatch.setattr(page, "evaluate", no_op)
    monkeypatch.setattr(worker, "_open_settings", always_true)
    monkeypatch.setattr(worker, "_ensure_custom_profile", always_true)
    monkeypatch.setattr(worker, "_click_ok", always_true)
    monkeypatch.setattr(worker, "_wait_dialog_close", dialog_stays_open)
    monkeypatch.setattr(worker, "_wait_for_update_complete", fake_wait_for_update_complete)
    monkeypatch.setattr(worker, "_get_results_hash", changing_hash)

    outcome = asyncio.run(worker._apply_params({}))

    assert outcome.ok is False
    assert outcome.reason == "settings_dialog_still_open"
    assert outcome.attempt == 3
    assert update_wait_calls == []


def test_read_results_rejects_symbol_mismatch_before_collecting_metrics() -> None:
    page = DummyPage(title="GBPJPY 5 Vantage")
    worker = TabWorker(page, DummyOptimizer())

    with pytest.raises(RuntimeError, match="Symbol mismatch"):
        asyncio.run(worker._read_results("EURJPY", {}))

    assert page.evaluate_called is False


def test_read_results_records_verified_symbol() -> None:
    page = MetricsPage(
        title="USDCAD 5 Vantage",
        metrics={
            "Total P&L": "$1200",
            "Total trades": "42",
            "Profitable trades": "55%",
            "Profit factor": "1.31",
            "Max equity drawdown": "$500|5.5%",
        },
    )
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._read_results("USDCAD", {}))

    assert result.symbol == "USDCAD"
    assert result.verified_symbol == "USDCAD"


def test_read_results_prefers_drawdown_percent_from_metric_text() -> None:
    page = MetricsPage(
        title="USDCHF 5 Vantage",
        metrics={
            "Total P&L": "$2902.66|5.81%",
            "Total trades": "306",
            "Profit factor": "1.073",
            "Max equity drawdown": "$7,059.46|12.02%",
        },
    )
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._read_results("USDCHF", {}))

    assert result.verified_symbol == "USDCHF"
    assert result.max_drawdown == pytest.approx(7059.46, rel=1e-6)
    assert result.max_drawdown_pct == pytest.approx(12.02, rel=1e-6)
    assert result.drawdown_source == "percent"


def test_read_results_extracts_drawdown_percent_from_plain_cell_text() -> None:
    page = MetricsPage(
        title="USDCHF 5 Vantage",
        metrics={
            "Total P&L": "$1200|2.4%",
            "Total trades": "220",
            "Profit factor": "1.08",
            "Max equity drawdown": "7,059.46 USD 12.02%",
        },
    )
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._read_results("USDCHF", {}))

    assert result.max_drawdown == pytest.approx(7059.46, rel=1e-6)
    assert result.max_drawdown_pct == pytest.approx(12.02, rel=1e-6)
    assert result.drawdown_source == "percent"


def test_read_results_extracts_drawdown_percent_when_cell_body_has_percent_only() -> None:
    page = MetricsPage(
        title="GBPJPY 5 Vantage",
        metrics={
            "Total P&L": "$1200|2.4%",
            "Total trades": "220",
            "Profit factor": "1.08",
            "Max equity drawdown": "$7,059.46|$7,059.46 USD 12.02%",
        },
    )
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._read_results("GBPJPY", {}))

    assert result.max_drawdown == pytest.approx(7059.46, rel=1e-6)
    assert result.max_drawdown_pct == pytest.approx(12.02, rel=1e-6)
    assert result.drawdown_source == "percent"


def test_format_trial_log_line_is_atomic_and_worker_scoped() -> None:
    optimizer = TradingViewOptimizer(
        pairs=["USDCAD"],
        bayesian_mode=True,
        n_trials=2,
        generate_report=False,
    )
    optimizer.worker_id = 4
    result = BacktestResult(
        symbol="USDCAD",
        verified_symbol="USDCAD",
        params={},
        profit_factor=1.12,
        max_drawdown_pct=9.8,
        total_trades=211,
        net_profit=1000,
        max_drawdown=900,
        score=16.42,
    )

    line = optimizer._format_trial_log_line(
        symbol="USDCAD",
        trial_num=7,
        n_trials=150,
        eta="52m1s",
        result=result,
    )

    assert "[worker-4][USDCAD]" in line
    assert "Trial   7/150" in line
    assert "PF=1.12" in line
    assert "DD=9.8%" in line
    assert "S=16.42" in line


def test_range_matches_label_uses_actual_day_span() -> None:
    assert TabWorker._range_matches_label(
        "Apr 13, 2025 — Apr 13, 2026Apr 13, 2025 — Apr 13, 2026",
        "Last 365 days",
    )
    assert TabWorker._range_matches_label(
        "Jan 13, 2026 — Apr 13, 2026Jan 13, 2026 — Apr 13, 2026",
        "Last 90 days",
    )
    assert TabWorker._range_matches_label(
        "Mar 14, 2026 — Apr 13, 2026Mar 14, 2026 — Apr 13, 2026",
        "Last 30 days",
    )
    assert TabWorker._range_matches_label(
        "Apr 13, 2021 — Apr 13, 2026Apr 13, 2021 — Apr 13, 2026",
        "Entire history",
    )
    assert not TabWorker._range_matches_label(
        "Jan 5, 2026 — Apr 13, 2026Jan 5, 2026 — Apr 13, 2026",
        "Last 365 days",
    )
    assert not TabWorker._range_matches_label(
        "Feb 20, 2026 — Apr 13, 2026Feb 20, 2026 — Apr 13, 2026",
        "Last 30 days",
    )


def test_wait_for_load_recovers_strategy_report_timeout(monkeypatch) -> None:
    page = DummyPage()
    worker = TabWorker(page, DummyOptimizer())
    recover_calls: list[str] = []
    loading_values = iter([None, None])
    timeout_values = iter([True, False])
    now = {"value": 0.0}

    async def fake_check_loading() -> str | None:
        return next(loading_values, None)

    async def fake_check_timeout() -> bool:
        return next(timeout_values, False)

    async def fake_recover() -> None:
        recover_calls.append("recover")

    async def fake_sleep(seconds: float) -> None:
        now["value"] += seconds

    monkeypatch.setattr(worker, "_check_loading_text", fake_check_loading)
    monkeypatch.setattr(worker, "_check_timeout_banner", fake_check_timeout)
    monkeypatch.setattr(worker, "_recover_strategy_report_timeout", fake_recover)
    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(tab_worker_module.time, "time", lambda: now["value"])

    asyncio.run(worker._wait_for_load(timeout=5))

    assert recover_calls == ["recover"]


def test_wait_for_update_complete_requires_results_to_settle(monkeypatch) -> None:
    page = DummyPage()
    worker = TabWorker(page, DummyOptimizer())
    now = {"value": 0.0}
    settle_calls: list[str] = []
    update_clicks: list[str] = []
    loading_values = iter(["Updating report", None])

    async def fake_check_loading() -> str | None:
        return next(loading_values, None)

    async def fake_wait_for_results_stable() -> bool:
        settle_calls.append("settle")
        return True

    async def fake_sleep(seconds: float) -> None:
        now["value"] += seconds

    async def fake_evaluate(script: str, *_args):
        if script == tab_worker_module._JS_CLICK_UPDATE_REPORT:
            update_clicks.append("click")
            return False
        raise AssertionError(f"unexpected evaluate in wait-for-update test: {script[:120]}")

    monkeypatch.setattr(worker, "_check_loading_text", fake_check_loading)
    monkeypatch.setattr(worker, "_wait_for_results_stable", fake_wait_for_results_stable, raising=False)
    monkeypatch.setattr(worker.page, "evaluate", fake_evaluate)
    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(tab_worker_module.time, "time", lambda: now["value"])

    result = asyncio.run(worker._wait_for_update_complete())

    assert result is True
    assert settle_calls == ["settle"]
    assert update_clicks


def test_wait_for_results_stable_allows_slow_report_repaint_before_fingerprint_appears(monkeypatch) -> None:
    page = DummyPage()
    worker = TabWorker(page, DummyOptimizer())
    now = {"value": 0.0}

    async def fake_check_loading() -> str | None:
        return None

    async def fake_read_results_fingerprint_raw() -> str:
        if now["value"] < 11.0:
            return ""
        return "profit=1.2;dd=4.0"

    async def fake_sleep(seconds: float) -> None:
        now["value"] += seconds

    monkeypatch.setattr(worker, "_check_loading_text", fake_check_loading)
    monkeypatch.setattr(worker, "_read_results_fingerprint_raw", fake_read_results_fingerprint_raw)
    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(tab_worker_module.time, "time", lambda: now["value"])

    result = asyncio.run(worker._wait_for_results_stable())

    assert result is True


def test_switch_symbol_does_not_force_backtest_range(monkeypatch) -> None:
    page = DummyPage(title="XAUUSD 5 Vantage", url="https://www.tradingview.com/chart/test123/?symbol=VANTAGE%3AXAUUSD")
    worker = TabWorker(page, DummyOptimizer())
    goto_calls: list[str] = []
    range_calls: list[str] = []

    async def fake_goto(url: str, wait_until: str, timeout: int) -> None:
        goto_calls.append(url)
        page.url = url
        page._title = "USDJPY 5 Vantage"

    async def fake_wait_for_load(timeout: int = 30) -> None:
        return None

    async def fake_current_symbol() -> str:
        return "USDJPY"

    async def fake_set_backtest_range(label: str = "Entire history") -> bool:
        range_calls.append(label)
        return True

    async def fake_ensure_chart_timeframe_5m() -> bool:
        return True

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(page, "goto", fake_goto, raising=False)
    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)
    monkeypatch.setattr(worker, "_current_symbol", fake_current_symbol)
    monkeypatch.setattr(worker, "_set_backtest_range", fake_set_backtest_range)
    monkeypatch.setattr(worker, "_ensure_chart_timeframe_5m", fake_ensure_chart_timeframe_5m)

    asyncio.run(worker._switch_symbol("USDJPY"))

    assert goto_calls
    assert range_calls == []


def test_switch_symbol_restores_5m_timeframe(monkeypatch) -> None:
    page = DummyPage(title="XAUUSD 1D Vantage", url="https://www.tradingview.com/chart/test123/?symbol=VANTAGE%3AXAUUSD")
    worker = TabWorker(page, DummyOptimizer())
    events: list[str] = []

    async def fake_goto(url: str, wait_until: str, timeout: int) -> None:
        page.url = url
        page._title = "USDJPY 1D Vantage"

    async def fake_wait_for_load(timeout: int = 30) -> None:
        return None

    async def fake_current_symbol() -> str:
        return "USDJPY"

    async def fake_ensure_chart_timeframe_5m() -> bool:
        events.append("set-5m")
        return True

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(page, "goto", fake_goto, raising=False)
    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)
    monkeypatch.setattr(worker, "_current_symbol", fake_current_symbol)
    monkeypatch.setattr(worker, "_ensure_chart_timeframe_5m", fake_ensure_chart_timeframe_5m)

    asyncio.run(worker._switch_symbol("USDJPY"))

    assert events == ["set-5m"]


def test_switch_symbol_prefers_desktop_mcp_symbol_command(monkeypatch) -> None:
    page = DesktopClientSwitchPage()
    worker = TabWorker(page, DummyOptimizer())
    events: list[str] = []

    async def fake_sleep(seconds: float) -> None:
        events.append(f"sleep:{seconds}")

    async def fake_wait_for_load(timeout: int = 30) -> None:
        events.append(f"wait-load:{timeout}")

    async def fake_ensure_chart_timeframe_5m() -> bool:
        events.append("set-5m")
        return True

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)
    monkeypatch.setattr(worker, "_ensure_chart_timeframe_5m", fake_ensure_chart_timeframe_5m)

    asyncio.run(worker._switch_symbol("EURJPY"))

    assert page._client.calls == [("symbol", "VANTAGE:EURJPY")]
    assert page.goto_called is False
    assert "set-5m" in events


def test_switch_symbol_uses_search_selection_for_fxcm(monkeypatch) -> None:
    page = FxcmSearchPage()
    optimizer = DummyOptimizer()
    optimizer.broker = "fxcm"
    worker = TabWorker(page, optimizer)
    events: list[str] = []

    async def fake_sleep(seconds: float) -> None:
        return None

    async def fake_wait_for_load(timeout: int = 30) -> None:
        events.append(f"wait-load:{timeout}")

    async def fake_ensure_chart_timeframe_5m() -> bool:
        events.append("set-5m")
        return True

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)
    monkeypatch.setattr(worker, "_ensure_chart_timeframe_5m", fake_ensure_chart_timeframe_5m)

    asyncio.run(worker._switch_symbol("EURUSD"))

    assert page.search_open is True
    assert page.query == "EURUSD"
    assert page.broker == "FXCM"
    assert page.symbol == "EURUSD"
    assert page.goto_called is False
    assert "set-5m" in events


def test_switch_symbol_fails_fast_when_fxcm_search_has_no_result(monkeypatch) -> None:
    page = FxcmSearchPage(search_success=False)
    optimizer = DummyOptimizer()
    optimizer.broker = "fxcm"
    worker = TabWorker(page, optimizer)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="FXCM symbol search could not find EURUSD"):
        asyncio.run(worker._switch_symbol("EURUSD"))


def test_switch_symbol_fails_when_fxcm_lands_on_wrong_broker(monkeypatch) -> None:
    page = FxcmSearchPage(broker_after="OANDA")
    optimizer = DummyOptimizer()
    optimizer.broker = "fxcm"
    worker = TabWorker(page, optimizer)

    async def fake_sleep(seconds: float) -> None:
        return None

    async def fake_wait_for_load(timeout: int = 30) -> None:
        return None

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)

    with pytest.raises(RuntimeError, match="Broker mismatch: expected FXCM, observed OANDA"):
        asyncio.run(worker._switch_symbol("EURUSD"))


def test_ensure_chart_timeframe_5m_verifies_desktop_mcp_result(monkeypatch) -> None:
    page = DesktopTimeframePage()
    worker = TabWorker(page, DummyOptimizer())

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(worker._ensure_chart_timeframe_5m())

    assert result is True
    assert page._client.calls == [("timeframe", "5")]


def test_set_backtest_range_clicks_menu_when_current_span_is_wrong(monkeypatch) -> None:
    worker = TabWorker(DummyPage(), DummyOptimizer())
    events: list[object] = []
    texts = iter(
        [
            "Jan 5, 2026 — Apr 13, 2026Jan 5, 2026 — Apr 13, 2026",
            "Apr 13, 2025 — Apr 13, 2026Apr 13, 2025 — Apr 13, 2026",
        ]
    )

    async def fake_ensure_strategy_tester_open() -> None:
        events.append("ensure-open")

    async def fake_read_text() -> str:
        return next(texts)

    async def fake_select(range_label: str) -> bool:
        events.append(("select", range_label))
        return True

    async def fake_wait_for_update_complete() -> bool:
        events.append("wait-update")
        return True

    async def fake_wait_for_load(timeout: int = 30) -> None:
        events.append(("wait-load", timeout))

    monkeypatch.setattr(worker, "_ensure_strategy_tester_open", fake_ensure_strategy_tester_open)
    monkeypatch.setattr(worker, "_read_backtest_range_button_text", fake_read_text)
    monkeypatch.setattr(worker, "_select_backtest_range_preset", fake_select)
    monkeypatch.setattr(worker, "_wait_for_update_complete", fake_wait_for_update_complete)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)

    result = asyncio.run(worker._set_backtest_range("Last 365 days"))

    assert result is True
    assert events[0] == "ensure-open"
    assert ("select", "Last 365 days") in events
    assert "wait-update" in events


def test_set_backtest_range_requires_ui_confirmation_after_chart_shortcut(monkeypatch) -> None:
    worker = TabWorker(DummyPage(), DummyOptimizer())
    events: list[object] = []
    texts = iter(["", ""])

    async def fake_ensure_strategy_tester_open() -> None:
        events.append("ensure-open")

    async def fake_read_text() -> str:
        return next(texts)

    async def fake_select(range_label: str) -> bool:
        events.append(("select", range_label))
        return False

    async def fake_select_chart(range_label: str) -> bool:
        events.append(("chart-select", range_label))
        return True

    async def fake_wait_for_update_complete() -> bool:
        events.append("wait-update")
        return True

    async def fake_wait_for_load(timeout: int = 30) -> None:
        events.append(("wait-load", timeout))

    monkeypatch.setattr(worker, "_ensure_strategy_tester_open", fake_ensure_strategy_tester_open)
    monkeypatch.setattr(worker, "_read_backtest_range_button_text", fake_read_text)
    monkeypatch.setattr(worker, "_select_backtest_range_preset", fake_select)
    monkeypatch.setattr(worker, "_select_chart_date_range_tab", fake_select_chart)
    monkeypatch.setattr(worker, "_wait_for_update_complete", fake_wait_for_update_complete)
    monkeypatch.setattr(worker, "_wait_for_load", fake_wait_for_load)

    result = asyncio.run(worker._set_backtest_range("Last 365 days"))

    assert result is False
    assert ("select", "Last 365 days") in events
    assert ("chart-select", "Last 365 days") in events
    assert "wait-update" in events


def test_open_settings_uses_strategy_report_menu_when_available() -> None:
    page = MenuSettingsPage()
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._open_settings())

    assert result is True
    assert page.dialog_open is True


def test_open_settings_uses_direct_legend_settings_when_available() -> None:
    page = DirectLegendSettingsPage()
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._open_settings())

    assert result is True
    assert page.dialog_open is True


def test_open_settings_uses_mouse_fallback_for_aria_settings_button(monkeypatch) -> None:
    page = AriaLegendSettingsMouseFallbackPage()
    worker = TabWorker(page, DummyOptimizer())

    async def fake_page_query_snd(_page):
        return None

    monkeypatch.setattr(tab_worker_module, "page_query_snd", fake_page_query_snd)

    result = asyncio.run(worker._open_settings())

    assert result is True
    assert page.mouse_clicks == [(410, 260, False)]
    assert page.dialog_open is True


def test_ensure_custom_profile_recovers_from_blank_dialog_after_reopen(monkeypatch) -> None:
    page = BlankThenCustomProfilePage()
    worker = TabWorker(page, DummyOptimizer())

    async def no_sleep(*_args, **_kwargs) -> None:
        return None

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def reopen() -> bool:
        return True

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(worker, "_dismiss_tv_errors", noop)
    monkeypatch.setattr(worker, "_open_settings", reopen)

    assert asyncio.run(worker._ensure_custom_profile()) is True
    assert page.escape_presses >= 1


def test_ensure_custom_profile_reloads_strategy_after_blank_reopen(monkeypatch) -> None:
    page = ReloadThenCustomProfilePage()
    worker = TabWorker(page, DummyOptimizer())
    reload_calls: list[str] = []

    async def no_sleep(*_args, **_kwargs) -> None:
        return None

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def reopen() -> bool:
        return True

    async def reload_script() -> None:
        reload_calls.append("reload")
        page.reloaded = True

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(worker, "_dismiss_tv_errors", noop)
    monkeypatch.setattr(worker, "_open_settings", reopen)
    monkeypatch.setattr(worker, "_reload_strategy_script", reload_script)

    assert asyncio.run(worker._ensure_custom_profile()) is True
    assert reload_calls == ["reload"]


def test_dismiss_wrong_settings_dialog_closes_chart_settings_modal() -> None:
    page = ChartSettingsPage()
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._dismiss_wrong_settings_dialog())

    assert result is True
    assert page.chart_dialog_open is False
    assert page.mouse_clicks == [(1188, 310)]


def test_ensure_custom_profile_recovers_when_chart_settings_opens_during_reopen(monkeypatch) -> None:
    page = WrongDialogThenReopenPage()
    worker = TabWorker(page, DummyOptimizer())
    reopen_calls: list[str] = []

    async def no_sleep(*_args, **_kwargs) -> None:
        return None

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def reopen() -> bool:
        reopen_calls.append("open")
        page.open_attempts += 1
        if page.open_attempts >= 2:
            page.wrong_dialog_open = False
        return True

    monkeypatch.setattr(tab_worker_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(worker, "_dismiss_tv_errors", noop)
    monkeypatch.setattr(worker, "_open_settings", reopen)

    assert asyncio.run(worker._ensure_custom_profile()) is True
    assert reopen_calls == ["open", "open"]


def test_ensure_strategy_tester_open_uses_strategy_report_control_when_metrics_delayed() -> None:
    page = StrategyReportPage()
    worker = TabWorker(page, DummyOptimizer())

    asyncio.run(worker._ensure_strategy_tester_open())

    assert page.report_open is True


def test_ensure_strategy_tester_open_uses_mouse_fallback_when_js_click_does_not_open_panel() -> None:
    page = MouseStrategyReportPage()
    worker = TabWorker(page, DummyOptimizer())

    asyncio.run(worker._ensure_strategy_tester_open())

    assert page.report_open is True
    assert page.mouse_clicks == [(990, 748)]


def test_bayesian_optimizer_uses_only_fresh_results_for_study_and_best_tracking(
    monkeypatch,
) -> None:
    study_calls: list[tuple[object, object, object]] = []

    class FakeTrial:
        pass

    class FakeStudy:
        def ask(self) -> FakeTrial:
            return FakeTrial()

        def tell(self, trial, value=None, state=None):
            study_calls.append((trial, value, state))

    study = FakeStudy()

    def fake_create_study(**kwargs):
        return study

    fake_optuna = SimpleNamespace(
        logging=SimpleNamespace(WARNING=30, set_verbosity=lambda level: None),
        create_study=fake_create_study,
        samplers=SimpleNamespace(TPESampler=lambda **kwargs: object()),
        trial=SimpleNamespace(TrialState=SimpleNamespace(FAIL="FAIL")),
    )

    monkeypatch.setitem(sys.modules, "optuna", fake_optuna)

    class FakeWorker:
        def __init__(self) -> None:
            self.results: list[BacktestResult] = []
            self.best_result = None
            self.apply_outcomes = [
                ApplyOutcome(ok=True, fresh=True, reason="fresh"),
                ApplyOutcome(ok=False, fresh=False, reason="stale_result_hash"),
                ApplyOutcome(ok=True, fresh=True, reason="fresh"),
            ]
            self.read_calls: list[tuple[str, dict]] = []

        async def _switch_symbol(self, symbol: str) -> None:
            self.symbol = symbol

        async def _require_last_365_days(self) -> None:
            self.range_label = "Last 365 days"

        async def _apply_params(self, params: dict) -> ApplyOutcome:
            return self.apply_outcomes.pop(0)

        def sample_params(self, trial, symbol: str, fixed_overrides: dict) -> dict:
            return {"trial": len(self.read_calls) + 1}

        async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
            self.read_calls.append((symbol, params))
            return BacktestResult(
                symbol=symbol,
                params=params,
                profit_factor=1.7,
                total_trades=120,
                max_drawdown_pct=6.0,
                win_rate=61.0,
                score=15.0,
            )

    optimizer = TradingViewOptimizer(
        pairs=["EURJPY"],
        bayesian_mode=True,
        n_trials=2,
        generate_report=False,
    )
    worker = FakeWorker()

    result = asyncio.run(optimizer.optimize_pair_bayesian(worker, "EURJPY", 2))

    assert result is not None
    assert result.score == pytest.approx(15.0)
    assert worker.read_calls == [("EURJPY", {"trial": 1})]
    assert len(study_calls) == 2
    assert study_calls[0][2] == "FAIL"
    assert study_calls[1][1] == pytest.approx(15.0)
    assert optimizer.best_per_pair == {}


def test_bayesian_optimizer_uses_configured_backtest_range(monkeypatch) -> None:
    class FakeTrial:
        pass

    class FakeStudy:
        def ask(self) -> FakeTrial:
            return FakeTrial()

        def tell(self, trial, value=None, state=None):
            return None

    fake_optuna = SimpleNamespace(
        logging=SimpleNamespace(WARNING=30, set_verbosity=lambda level: None),
        create_study=lambda **kwargs: FakeStudy(),
        samplers=SimpleNamespace(TPESampler=lambda **kwargs: object()),
        trial=SimpleNamespace(TrialState=SimpleNamespace(FAIL="FAIL")),
    )
    monkeypatch.setitem(sys.modules, "optuna", fake_optuna)

    class FakeWorker:
        def __init__(self) -> None:
            self.results: list[BacktestResult] = []
            self.best_result = None
            self.range_labels: list[str] = []

        async def _switch_symbol(self, symbol: str) -> None:
            self.symbol = symbol

        async def _require_backtest_range(self, range_label: str) -> None:
            self.range_labels.append(range_label)

        async def _apply_params(self, params: dict) -> ApplyOutcome:
            return ApplyOutcome(ok=True, fresh=True, reason="fresh")

        def sample_params(self, trial, symbol: str, fixed_overrides: dict) -> dict:
            return {"trial": 1}

        async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
            return BacktestResult(
                symbol=symbol,
                verified_symbol=symbol,
                params=params,
                profit_factor=1.42,
                total_trades=160,
                max_drawdown_pct=5.2,
                win_rate=58.0,
                score=17.5,
            )

    optimizer = TradingViewOptimizer(
        pairs=["EURUSD"],
        bayesian_mode=True,
        n_trials=1,
        generate_report=False,
        backtest_range="90d",
    )
    worker = FakeWorker()

    result = asyncio.run(optimizer.optimize_pair_bayesian(worker, "EURUSD", 1))

    assert result is not None
    assert worker.range_labels == ["Last 90 days"]


def test_bayesian_optimizer_reloads_after_repeated_read_timeouts(monkeypatch) -> None:
    class FakeTrial:
        pass

    class FakeStudy:
        def ask(self) -> FakeTrial:
            return FakeTrial()

        def tell(self, trial, value=None, state=None):
            pass

    fake_optuna = SimpleNamespace(
        logging=SimpleNamespace(WARNING=30, set_verbosity=lambda level: None),
        create_study=lambda **kwargs: FakeStudy(),
        samplers=SimpleNamespace(TPESampler=lambda **kwargs: object()),
        trial=SimpleNamespace(TrialState=SimpleNamespace(FAIL="FAIL")),
    )
    monkeypatch.setitem(sys.modules, "optuna", fake_optuna)

    async def no_sleep(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    class ReloadablePage:
        def __init__(self) -> None:
            self.reload_calls = 0

        async def reload(self, **kwargs) -> None:
            self.reload_calls += 1

    class FakeWorker:
        def __init__(self) -> None:
            self.page = ReloadablePage()
            self.results: list[BacktestResult] = []
            self.best_result = None
            self._read_attempts = 0
            self.recovery_calls: list[tuple[str, str]] = []

        async def _switch_symbol(self, symbol: str) -> None:
            self.recovery_calls.append(("switch", symbol))

        async def _require_last_365_days(self) -> None:
            self.recovery_calls.append(("range", "Last 365 days"))

        async def _apply_params(self, params: dict) -> ApplyOutcome:
            return ApplyOutcome(ok=True, fresh=True, reason="fresh")

        def sample_params(self, trial, symbol: str, fixed_overrides: dict) -> dict:
            return {"trial": self._read_attempts + 1}

        async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
            self._read_attempts += 1
            if self._read_attempts <= 3:
                raise asyncio.TimeoutError
            return BacktestResult(
                symbol=symbol,
                verified_symbol=symbol,
                params=params,
                profit_factor=1.18,
                total_trades=250,
                max_drawdown_pct=8.2,
                win_rate=58.0,
                score=15.0,
            )

    optimizer = TradingViewOptimizer(
        pairs=["EURJPY"],
        bayesian_mode=True,
        n_trials=4,
        generate_report=False,
    )
    worker = FakeWorker()

    result = asyncio.run(optimizer.optimize_pair_bayesian(worker, "EURJPY", 4))

    assert result is not None
    assert worker.page.reload_calls == 1
    assert ("switch", "EURJPY") in worker.recovery_calls
    assert ("range", "Last 365 days") in worker.recovery_calls


def test_bayesian_optimizer_raises_when_all_trials_fail(monkeypatch) -> None:
    class FakeTrial:
        pass

    class FakeStudy:
        def ask(self) -> FakeTrial:
            return FakeTrial()

        def tell(self, trial, value=None, state=None):
            return None

    fake_optuna = SimpleNamespace(
        logging=SimpleNamespace(WARNING=30, set_verbosity=lambda level: None),
        create_study=lambda **kwargs: FakeStudy(),
        samplers=SimpleNamespace(TPESampler=lambda **kwargs: object()),
        trial=SimpleNamespace(TrialState=SimpleNamespace(FAIL="FAIL")),
    )
    monkeypatch.setitem(sys.modules, "optuna", fake_optuna)

    class FakeWorker:
        def __init__(self) -> None:
            self.results: list[BacktestResult] = []
            self.best_result = None

        async def _switch_symbol(self, symbol: str) -> None:
            self.symbol = symbol

        async def _require_last_365_days(self) -> None:
            self.range_label = "Last 365 days"

        async def _apply_params(self, params: dict) -> ApplyOutcome:
            return ApplyOutcome(ok=False, fresh=False, reason="apply_failed")

        def sample_params(self, trial, symbol: str, fixed_overrides: dict) -> dict:
            return {"trial": 1}

        async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
            raise AssertionError("_read_results should not be called when apply fails")

    optimizer = TradingViewOptimizer(
        pairs=["EURJPY"],
        bayesian_mode=True,
        n_trials=2,
        generate_report=False,
    )
    worker = FakeWorker()

    with pytest.raises(RuntimeError, match="No valid optimization result produced for EURJPY"):
        asyncio.run(optimizer.optimize_pair_bayesian(worker, "EURJPY", 2))


def test_read_results_parses_fallback_metric_rows() -> None:
    page = FallbackMetricsPage()
    worker = TabWorker(page, DummyOptimizer())

    result = asyncio.run(worker._read_results("EURJPY", {"rr_mode": "dynamic"}))

    assert result.net_profit == 123.45
    assert result.total_trades == 42
    assert result.win_rate == 55.0
    assert result.profit_factor == 1.8
    assert result.max_drawdown == 1250.0
    assert result.max_drawdown_pct == 2.5
