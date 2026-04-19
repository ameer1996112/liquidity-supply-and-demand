from __future__ import annotations

from src.services.optimizer_portfolio_service import allocate_portfolio_weights


def test_allocate_portfolio_weights_drops_pair_until_final_caps_are_respected() -> None:
    allocation = allocate_portfolio_weights(
        [
            {"symbol": "EURUSD", "status": "PASS", "safety_rank": 0.95, "drawdown_curve": [0, -1, -2]},
            {"symbol": "GBPJPY", "status": "PASS", "safety_rank": 0.60, "drawdown_curve": [0, -4, -10]},
        ],
        portfolio_dd_limit=6.0,
        portfolio_daily_limit=3.0,
    )

    assert allocation["weights"]["EURUSD"] == 1.0
    assert allocation["weights"]["GBPJPY"] == 0.0
    assert allocation["combined_max_drawdown_pct"] <= 6.0
    assert allocation["combined_daily_drawdown_pct"] <= 3.0


def test_allocate_portfolio_weights_excludes_rejected_pairs_from_portfolio() -> None:
    allocation = allocate_portfolio_weights(
        [
            {"symbol": "EURUSD", "status": "PASS", "safety_rank": 0.95, "drawdown_curve": [0, -1, -2]},
            {"symbol": "GBPJPY", "status": "REJECT", "safety_rank": 0.99, "drawdown_curve": [0, -3, -7]},
        ],
        portfolio_dd_limit=6.0,
        portfolio_daily_limit=3.0,
    )

    assert allocation["weights"]["EURUSD"] == 1.0
    assert allocation["weights"]["GBPJPY"] == 0.0
    assert allocation["combined_max_drawdown_pct"] == 2.0
    assert allocation["combined_daily_drawdown_pct"] == 1.0
