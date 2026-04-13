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

        async def _set_backtest_range(self, range_label: str) -> None:
            self.range_label = range_label

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
