from scripts.optimizer import config as optimizer_config
from scripts.optimizer.param_contract import (
    DEFAULT_PINE_SOURCE,
    extract_pine_inputs,
    optimizer_search_param_names,
    validate_optimizer_pine_contract,
)
from scripts.optimizer.tab_worker import TabWorker


class _FakeTrial:
    def suggest_categorical(self, _name, choices):
        return choices[0]

    def suggest_int(self, _name, low, _high):
        return low

    def suggest_float(self, _name, low, _high):
        return low


def test_optimizer_params_are_backed_by_canonical_pine_input_titles() -> None:
    pine_inputs = extract_pine_inputs()
    pine_titles = {item.title for item in pine_inputs.values()}

    searched = optimizer_search_param_names()
    assert searched <= pine_titles

    metadata = set(getattr(optimizer_config, "OPTIMIZER_METADATA_PARAMS", ()))
    assert metadata <= pine_titles
    context_defaults = set(getattr(optimizer_config, "OPTIMIZER_CONTEXT_PARAM_DEFAULTS", ()))
    assert context_defaults <= pine_titles
    synthetic_inputs = {
        input_name
        for input_names in getattr(
            optimizer_config, "OPTIMIZER_SYNTHETIC_PARAM_INPUTS", {}
        ).values()
        for input_name in input_names
    }
    ui_only = set(getattr(optimizer_config, "OPTIMIZER_UI_ONLY_PARAMS", ()))
    assert set(pine_inputs) <= searched | metadata | context_defaults | synthetic_inputs | ui_only

    for name, pine_input in pine_inputs.items():
        assert pine_input.title == name


def test_optimizer_pine_contract_startup_validation_passes() -> None:
    validate_optimizer_pine_contract()


def test_pine_strategy_uses_custom_profile_only() -> None:
    source = DEFAULT_PINE_SOURCE.read_text()

    assert 'options = ["Custom"]' in source
    assert "Conservative (Live Trading)" not in source
    assert "Balanced (Recommended)" not in source
    assert "Aggressive (Paper Trading)" not in source
    assert "use_profile_defaults" not in source
    assert "is_aggressive" not in source


def test_result_params_are_a_reproducible_pine_input_snapshot() -> None:
    materialized = optimizer_config.materialize_result_params(
        {
            "risk_pct": 0.4,
            "rr_mode": "fixed_3.0",
            "max_peak_to_touch_bars": 48,
            "max_sweep_to_touch_bars": 19,
        }
    )

    assert materialized["rr_mode"] == "fixed_3.0"
    assert materialized["use_custom_rr"] is True
    assert materialized["risk_reward_ratio"] == 3.0
    assert materialized["config_profile"] == "Custom"
    assert materialized["risk_per_trade_pct"] == 0.5
    assert materialized["require_major_liquidity"] is True
    assert materialized["require_htf_flip"] is True
    assert materialized["enable_trade_limit"] is True
    assert materialized["filter_trading_hours"] is True
    assert materialized["max_peak_to_touch_bars"] == 48
    assert materialized["max_sweep_to_touch_bars"] == 19


def test_prop_safety_params_are_profile_locked_not_search_params() -> None:
    locked = set(optimizer_config.PROP_PROFILE_LOCKED_PARAMS)

    assert {
        "risk_per_trade_pct",
        "risk_pct",
        "daily_kill_pct",
        "total_kill_pct",
        "max_daily_loss_pct",
        "max_trades_per_day",
        "news_blackout_enabled",
        "max_position_size_lots",
        "max_lots_per_10k",
    } <= locked
    assert locked.isdisjoint(optimizer_config.OPTUNA_SEARCH_SPACE)


def test_optimizer_has_separate_asset_class_param_spaces() -> None:
    spaces = optimizer_config.ASSET_CLASS_PARAM_SPACES

    assert set(spaces) == {"forex", "jpy", "gold", "index", "futures"}
    assert "liq_max_distance_pips_forex" in spaces["forex"]
    assert "liq_max_distance_pips_forex" in spaces["jpy"]
    assert "liq_max_distance_pips_gold" in spaces["gold"]
    assert "liq_max_distance_pips_index" in spaces["index"]
    assert "max_contracts" in spaces["futures"]


def test_fixed_overrides_can_lock_context_strategy_rules() -> None:
    worker = TabWorker(page=None, optimizer=object())

    params = worker.sample_params(
        _FakeTrial(),
        "XAUUSD",
        {
            "rr_mode": "fixed_4.0",
            "require_major_liquidity": True,
            "filter_trading_hours": True,
            "enable_ai_quality_filter": False,
            "trading_start_hour": 7,
            "trading_end_hour": 15,
            "max_trades_per_day": 1,
        },
    )

    assert params["rr_mode"] == "fixed_4.0"
    assert params["require_major_liquidity"] is True
    assert params["filter_trading_hours"] is True
    assert params["enable_ai_quality_filter"] is False
    assert params["trading_start_hour"] == 7
    assert params["trading_end_hour"] == 15
    assert params["max_trades_per_day"] == 1
