from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.optimizer import TradingViewOptimizer
from src.api_optimizer_runs import router


class StubOptimizerService:
    def __init__(self) -> None:
        self._runs = [
            {
                "id": "run-1",
                "strategy_id": "liq_sd_v1",
                "strategy_version": "1",
                "status": "running",
                "mode": "bayesian",
                "workers": 2,
                "pairs": ["EURUSD", "GBPUSD"],
                "n_trials": 25,
                "dd_limit": 6.0,
                "dry_run": True,
                "summary": {"total_pairs": 2, "running_pairs": 1, "completed_pairs": 0, "failed_pairs": 0},
            }
        ]

    def start_run(self, **payload: object) -> dict:
        return payload

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict]:
        runs = list(self._runs)
        if status:
            runs = [run for run in runs if run["status"] == status]
        if strategy_id:
            runs = [run for run in runs if run["strategy_id"] == strategy_id]
        if strategy_version:
            runs = [run for run in runs if run["strategy_version"] == strategy_version]
        return runs[:limit]


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr("src.api_optimizer_runs.get_optimizer_run_service", lambda: StubOptimizerService())
    return TestClient(app)


def test_create_optimizer_run_requires_strategy_identity(monkeypatch) -> None:
    response = _client(monkeypatch).post(
        "/api/optimizer/runs",
        json={
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
        },
    )

    assert response.status_code == 422


def test_create_optimizer_run_accepts_strategy_identity(monkeypatch) -> None:
    response = _client(monkeypatch).post(
        "/api/optimizer/runs",
        json={
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD"],
            "n_trials": 25,
            "dd_limit": 6.0,
            "dry_run": True,
            "broker": "vantage",
        },
    )

    assert response.status_code == 200
    assert response.json()["strategy_id"] == "liq_sd_v1"
    assert response.json()["strategy_version"] == "1"


def test_list_optimizer_runs_filters_by_strategy(monkeypatch) -> None:
    response = _client(monkeypatch).get("/api/optimizer/runs?strategy_id=liq_sd_v1&strategy_version=1")

    assert response.status_code == 200
    body = response.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["strategy_id"] == "liq_sd_v1"


def test_backtest_result_serializes_pair_decision() -> None:
    result = BacktestResult(
        symbol="EURUSD",
        params={"ema_mode": "ema200_aligned"},
        net_profit=1200.0,
        total_trades=22,
        win_rate=55.0,
        profit_factor=1.24,
        max_drawdown_pct=4.6,
        score=78.0,
    )

    result.decision = {"status": "PASS", "risk_weight": 1.0}

    payload = result.to_dict()

    assert payload["decision"]["status"] == "PASS"


def test_optimizer_run_enriches_timeout_partial_best(monkeypatch) -> None:
    partial_best = BacktestResult(
        symbol="EURUSD",
        params={"max_daily_loss_pct": 3.0},
        verified_symbol="EURUSD",
        net_profit=1200.0,
        total_trades=42,
        win_rate=55.0,
        profit_factor=1.24,
        max_drawdown=500.0,
        max_drawdown_pct=4.6,
        drawdown_source="percent",
        score=78.0,
    )

    class StubWorker:
        def __init__(self, page: object, optimizer: TradingViewOptimizer) -> None:
            self.best_result = partial_best
            self.results = [partial_best]

    async def _fake_connect(self: TradingViewOptimizer) -> None:
        return None

    async def _fake_optimize(
        self: TradingViewOptimizer, worker: StubWorker, symbol: str, n_trials: int
    ) -> BacktestResult:
        raise asyncio.TimeoutError

    checkpoint: dict[str, object] = {"completed": [], "results": {}}
    saved: dict[str, BacktestResult] = {}

    def _fake_save_checkpoint(
        self: TradingViewOptimizer, checkpoint_data: dict, symbol: str, result: BacktestResult
    ) -> None:
        saved[symbol] = result

    monkeypatch.setattr("scripts.optimizer.optimizer.TabWorker", StubWorker)
    monkeypatch.setattr(TradingViewOptimizer, "connect_to_brave", _fake_connect)
    monkeypatch.setattr(TradingViewOptimizer, "optimize_pair_bayesian", _fake_optimize)
    monkeypatch.setattr(TradingViewOptimizer, "_load_checkpoint", lambda self: checkpoint)
    monkeypatch.setattr(TradingViewOptimizer, "_save_checkpoint", _fake_save_checkpoint)
    monkeypatch.setattr(TradingViewOptimizer, "save_results", lambda self: None)

    optimizer = TradingViewOptimizer(
        pairs=["EURUSD"],
        bayesian_mode=True,
        generate_report=False,
    )
    optimizer.tv_pages = [object()]

    asyncio.run(optimizer.run())

    enriched = optimizer.best_per_pair["EURUSD"]
    assert enriched.decision["status"] == "PASS"
    assert enriched.forward_metrics["max_daily_loss_pct"] == 3.0
    assert saved["EURUSD"].decision["risk_weight"] == 1.0
