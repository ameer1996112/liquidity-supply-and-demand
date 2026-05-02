from scripts.optimizer.prop_account_simulator import simulate_prop_account
from scripts.optimizer.prop_profiles import load_prop_profile


def test_prop_account_simulator_rejects_daily_loss_breach() -> None:
    report = simulate_prop_account(
        "USDCAD",
        {"risk_per_trade_pct": 0.5},
        {"max_daily_loss_pct": 3.5, "max_drawdown_pct": 4.0},
        load_prop_profile("generic_cfd_safe"),
        "generic_cfd_safe",
    )

    assert report["status"] == "rejected"
    assert "daily_loss_breach" in report["breaches"]


def test_prop_account_simulator_is_approximate_without_trades() -> None:
    report = simulate_prop_account(
        "NQ",
        {"max_contracts": 1, "news_blackout_enabled": True},
        {"max_drawdown": 1000, "max_daily_loss_usd": 500},
        load_prop_profile("topstep_50k_safe"),
        "topstep_50k_safe",
    )

    assert report["simulation_precision"] == "approximate"
    assert report["status"] == "watch_only"
