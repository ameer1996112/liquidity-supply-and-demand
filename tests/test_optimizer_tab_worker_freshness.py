from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.tab_worker import ApplyOutcome, TabWorker


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
    assert not TabWorker._range_matches_label(
        "Jan 5, 2026 — Apr 13, 2026Jan 5, 2026 — Apr 13, 2026",
        "Last 365 days",
    )


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
