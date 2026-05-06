from scripts.optimizer import config as optimizer_config
from scripts.optimizer.param_contract import (
    DEFAULT_PINE_SOURCE,
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


def test_pine_liquidity_scans_are_bounded_for_tradingview_runtime() -> None:
    source = DEFAULT_PINE_SOURCE.read_text()

    assert "int rawMaxOff = bar_index - z.createdBarIndex - 2" in source
    assert "int maxOff = math.min(rawMaxOff, MAX_LIQ_SCAN_BARS)" in source
    assert "if not z.liquidityValid or na(z.lastEntryBar)" not in source


def test_pine_strategy_sends_ai_and_grade_context_without_filtering() -> None:
    source = DEFAULT_PINE_SOURCE.read_text()
    pine_inputs = extract_pine_inputs()

    removed_filter_inputs = {
        "enable_ai_quality_filter",
        "ai_quality_threshold",
        "enable_ai_lite_mode",
        "enable_grade_filter",
        "min_entry_grade",
    }

    assert removed_filter_inputs.isdisjoint(pine_inputs)
    assert "if canEnter and enable_grade_filter" not in source
    assert "Grade too low" not in source
    assert "F:ai_pine_score=" in source
    assert "zone_grade" in source


def test_pine_strategy_sends_configurable_ema_learning_context_without_filtering() -> None:
    source = DEFAULT_PINE_SOURCE.read_text()

    expected_context_fields = {
        "F:ema_context_length=",
        "F:ema_context_value=",
        "F:ema_context_zone_mid_distance_pips=",
        "F:ema_context_zone_side=",
        "F:ema_context_slope=",
        "F:ema_context_aligned=",
    }

    for field in expected_context_fields:
        assert source.count(field) == 2

    assert 'input.int(200, "ema_context_length"' in source
    assert 'input.int(10, "ema_context_slope_lookback"' in source
    assert 'input.float(0.10, "ema_context_neutral_atr_mult"' in source
    assert 'input.bool(true, "show_ema_context_line"' in source
    assert "EMA200_SLOPE_LOOKBACK" not in source
    assert "get_ema200_zone_context" not in source
    assert "EMA200 filter" not in source
    assert "Blocked by EMA200" not in source
    assert "ema200_zone_filter" not in source


def test_pine_strategy_removes_legacy_profile_and_dead_settings() -> None:
    source = DEFAULT_PINE_SOURCE.read_text()

    assert "config_profile" not in source
    assert "Conservative (Live Trading)" not in source
    assert "Balanced (Recommended)" not in source
    assert "Aggressive (Paper Trading)" not in source
    assert "use_profile_defaults" not in source
    assert "require_htf_flip" not in source
    assert "showActiveProfile" not in source
    assert "profileStatusTable" not in source
    assert "show_ai_debug_comment" not in source
    assert "enable_ai_shadow_mode" not in source
    assert "debug_entry_labels" not in source
    assert "show_zone_debug_labels" not in source
    assert "show_debug_labels" not in source
    assert "debug_liq_extra" not in source


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
    assert materialized["risk_per_trade_pct"] == 0.5
    assert materialized["require_major_liquidity"] is True
    assert materialized["enable_trade_limit"] is True
    assert materialized["filter_trading_hours"] is True
    assert materialized["max_peak_to_touch_bars"] == 48
    assert materialized["max_sweep_to_touch_bars"] == 19
    assert materialized["ema_context_length"] == 200
    assert materialized["ema_context_slope_lookback"] == 10
    assert materialized["ema_context_neutral_atr_mult"] == 0.10


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
