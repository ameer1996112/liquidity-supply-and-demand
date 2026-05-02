import pytest

from scripts.optimizer.prop_profiles import load_prop_profile, params_pass_prop_profile


def test_prop_profile_rejects_unsafe_cfd_params() -> None:
    profile = load_prop_profile("generic_cfd_safe")

    ok, reasons = params_pass_prop_profile(
        {
            "risk_per_trade_pct": 0.75,
            "max_daily_loss_pct": 3.5,
            "daily_kill_pct": 4.0,
            "total_kill_pct": 7.0,
            "max_trades_per_day": 4,
            "news_blackout_enabled": False,
        },
        profile,
        "USDCAD",
    )

    assert ok is False
    assert "risk_per_trade_pct=0.75 > 0.5" in reasons
    assert "news_blackout_enabled_required" in reasons


def test_futures_profile_uses_dollar_limits() -> None:
    profile = load_prop_profile("topstep_50k_safe")

    ok, reasons = params_pass_prop_profile(
        {
            "max_contracts": 3,
            "estimated_max_loss_usd": 1300,
            "estimated_daily_loss_usd": 800,
            "news_blackout_enabled": True,
        },
        profile,
        "NQ",
    )

    assert ok is False
    assert "max_contracts=3 > 2" in reasons
    assert "estimated_max_loss_usd=1300.0 > 1200.0" in reasons
    assert "estimated_daily_loss_usd=800.0 > 700.0" in reasons


def test_futures_profile_rejects_non_futures_symbol() -> None:
    ok, reasons = params_pass_prop_profile(
        {"max_contracts": 1, "estimated_max_loss_usd": 100, "estimated_daily_loss_usd": 100},
        load_prop_profile("topstep_50k_safe"),
        "XAUUSD",
    )

    assert ok is False
    assert "symbol_not_futures_compatible" in reasons


def test_load_prop_profile_rejects_unknown_profile() -> None:
    with pytest.raises(KeyError):
        load_prop_profile("missing")
