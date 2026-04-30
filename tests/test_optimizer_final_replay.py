import asyncio
from types import SimpleNamespace

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.optimizer import TradingViewOptimizer
from scripts.optimizer.tab_worker import ApplyOutcome


def _result(
    *,
    net_profit: float = 100.0,
    profit_factor: float = 1.2,
    max_drawdown_pct: float = 4.0,
    total_trades: int = 10,
    win_rate: float = 40.0,
) -> BacktestResult:
    result = BacktestResult(
        symbol="GBPUSD",
        params={"risk_pct": 0.4},
        net_profit=net_profit,
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct,
        max_drawdown=max_drawdown_pct * 100,
        total_trades=total_trades,
        win_rate=win_rate,
    )
    result.calculate_score()
    return result


class ReplayWorker:
    def __init__(self, replay_result: BacktestResult):
        self.replay_result = replay_result
        self.applied_params = None

    async def _apply_params(self, params: dict, *, allow_unchanged_hash: bool = False) -> ApplyOutcome:
        self.applied_params = (params, allow_unchanged_hash)
        return ApplyOutcome(ok=True, fresh=True, reason="replay_verified", attempt=1)

    async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
        self.replay_result.symbol = symbol
        self.replay_result.params = params.copy()
        return self.replay_result


def test_replay_verification_keeps_matching_replay_metrics() -> None:
    optimizer = TradingViewOptimizer(["GBPUSD"], generate_report=False)
    candidate = _result()
    worker = ReplayWorker(_result())

    verified = asyncio.run(
        optimizer._verify_final_result_replay(worker, "GBPUSD", candidate)
    )

    assert verified.validation_metrics["final_replay"]["matched_original"] is True
    assert worker.applied_params == (candidate.params, True)
    assert verified.net_profit == candidate.net_profit


def test_replay_verification_replaces_stale_candidate_metrics() -> None:
    optimizer = TradingViewOptimizer(["GBPUSD"], generate_report=False)
    candidate = _result(net_profit=6230.76, profit_factor=1.351, max_drawdown_pct=4.56, total_trades=134)
    replay = _result(net_profit=1171.61, profit_factor=1.088, max_drawdown_pct=5.97, total_trades=108)
    worker = ReplayWorker(replay)

    verified = asyncio.run(
        optimizer._verify_final_result_replay(worker, "GBPUSD", candidate)
    )

    final_replay = verified.validation_metrics["final_replay"]
    assert final_replay["matched_original"] is False
    assert final_replay["original"]["total_trades"] == 134
    assert final_replay["replay"]["total_trades"] == 108
    assert verified.net_profit == 1171.61
    assert verified.total_trades == 108
