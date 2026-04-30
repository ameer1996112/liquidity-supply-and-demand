from scripts.optimizer import config as optimizer_config
from scripts.optimizer.param_contract import (
    extract_pine_inputs,
    optimizer_search_param_names,
    validate_optimizer_pine_contract,
)


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
