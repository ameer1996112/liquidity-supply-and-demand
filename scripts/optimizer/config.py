"""
config.py — All constants for the TradingView Strategy Optimizer.
"""

from pathlib import Path

from src.services.optimizer_defaults import DEFAULT_PAIRS

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "scripts" / "optimization_results"
RESULTS_DIR.mkdir(exist_ok=True)

CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"

# ─── Prop-firm constraints ────────────────────────────────────────────────────

PROP_FIRM_MAX_DD_PCT = 10.0   # Hard limit: score = 0 if DD% exceeds this

PROP_PROFILE_LOCKED_PARAMS = (
    "risk_per_trade_pct",
    "risk_pct",
    "daily_kill_pct",
    "total_kill_pct",
    "max_daily_loss_pct",
    "max_trades_per_day",
    "news_blackout_enabled",
    "max_position_size_lots",
    "max_lots_per_10k",
)

# ─── Bayesian optimization ────────────────────────────────────────────────────

N_BAYESIAN_TRIALS = 150        # Total Optuna trials per pair (increased: 21 params now vs 16)
N_STARTUP_TRIALS = 35          # Random exploration before TPE kicks in (≈25% of trials)

# Full Optuna search space across all 16 tunable parameters.
# "liq_distance" is a placeholder — resolved per asset class at runtime.
OPTUNA_SEARCH_SPACE: dict = {
    # ── Risk/Reward ───────────────────────────────────────────────────────────
    "rr_mode":                  {"type": "categorical", "choices": ["dynamic", "fixed_2.5", "fixed_3.0", "fixed_4.0"]},

    # ── AI Quality Filter ─────────────────────────────────────────────────────
    "enable_ai_quality_filter": {"type": "categorical", "choices": [True, False]},
    "ai_quality_threshold":     {"type": "int",         "low": 40,   "high": 75},

    # ── Entry distance filters ────────────────────────────────────────────────
    "min_tp_distance_pips":     {"type": "float",       "low": 5.0,  "high": 20.0},
    "liq_distance":             {"type": "float",       "low": None, "high": None},  # resolved per asset class
    "liq_entry_max_dist":       {"type": "float",       "low": 5.0,  "high": 20.0},  # max zone-to-liq distance

    # ── Trade management ──────────────────────────────────────────────────────
    "max_bars_held":            {"type": "int",         "low": 24,   "high": 96},
    "stop_loss_buffer_pips":    {"type": "float",       "low": 0.5,  "high": 3.0},
    "use_break_even":           {"type": "categorical", "choices": [True, False]},
    "enable_double_tp":         {"type": "categorical", "choices": [True, False]},

    # ── Zone detection ────────────────────────────────────────────────────────
    "liq_pivot_len":            {"type": "int",         "low": 2,    "high": 10},
    "pvtMax":                   {"type": "int",         "low": 3,    "high": 15},
    "max_sweep_to_touch_bars":  {"type": "int",         "low": 8,    "high": 25},
    "max_peak_to_touch_bars":   {"type": "int",         "low": 20,   "high": 60},
    "min_body_perc":            {"type": "int",         "low": 20,   "high": 80},
    "max_zones":                {"type": "int",         "low": 10,   "high": 30},

    # ── Daily trade limits ────────────────────────────────────────────────────
    # Prop-firm safety limits are profile-owned, not optimized.
    "max_daily_profit_pct":     {"type": "float",       "low": 3.0,  "high": 8.0},   # lock profits early

    # ── Session hours (key insight: different pairs peak in different sessions)
    # London open: 7, NY open: 13, overlap end: 17, Asian: 0-7
    # We use presets to avoid nonsensical combinations (e.g. start=20, end=8)
    "trading_start_hour":       {"type": "categorical", "choices": [0, 2, 5, 7, 8, 13]},
    "trading_end_hour":         {"type": "categorical", "choices": [12, 15, 17, 20, 22, 24]},
}

# Per-asset-class liquidity distance ranges (pips)
LIQ_DISTANCE_RANGES: dict = {
    "forex": {"low": 10.0,  "high": 35.0,  "param": "liq_max_distance_pips_forex"},
    "gold":  {"low": 80.0,  "high": 250.0, "param": "liq_max_distance_pips_gold"},
    "index": {"low": 250.0, "high": 800.0, "param": "liq_max_distance_pips_index"},
}

ASSET_CLASS_PARAM_SPACES: dict[str, dict[str, dict]] = {
    "forex": {
        **OPTUNA_SEARCH_SPACE,
        "liq_max_distance_pips_forex": {"type": "float", "low": 10.0, "high": 35.0},
    },
    "jpy": {
        **OPTUNA_SEARCH_SPACE,
        "liq_max_distance_pips_forex": {"type": "float", "low": 8.0, "high": 30.0},
    },
    "gold": {
        **OPTUNA_SEARCH_SPACE,
        "liq_max_distance_pips_gold": {"type": "float", "low": 80.0, "high": 250.0},
    },
    "index": {
        **OPTUNA_SEARCH_SPACE,
        "liq_max_distance_pips_index": {"type": "float", "low": 250.0, "high": 800.0},
    },
    "futures": {
        **OPTUNA_SEARCH_SPACE,
        "max_contracts": {"type": "int", "low": 1, "high": 2},
        "estimated_daily_loss_usd": {"type": "float", "low": 100.0, "high": 700.0},
        "estimated_max_loss_usd": {"type": "float", "low": 250.0, "high": 1200.0},
    },
}

OPTIMIZER_SYNTHETIC_PARAMS = ("rr_mode",)
OPTIMIZER_SYNTHETIC_PARAM_INPUTS = {
    "rr_mode": ("use_custom_rr", "risk_reward_ratio"),
}

OPTIMIZER_METADATA_PARAM_DEFAULTS = {
    "risk_pct": 0.4,
    "daily_kill_pct": 3.5,
    "total_kill_pct": 6.5,
    "consec_loss_kill": 2,
    "min_hold_minutes": 2,
    "news_blackout_enabled": False,
}

OPTIMIZER_METADATA_PARAMS = tuple(OPTIMIZER_METADATA_PARAM_DEFAULTS)

OPTIMIZER_CONTEXT_PARAM_DEFAULTS = {
    **OPTIMIZER_METADATA_PARAM_DEFAULTS,
    "config_profile": "Custom",
    "trade_direction": "Both",
    "account_size_usd": 50000,
    "risk_per_trade_pct": 0.5,
    "max_daily_loss_pct": 3.0,
    "enable_date_filter": False,
    "invalidate_on_wick": True,
    "structure_mode": "Relaxed (Wicks)",
    "require_major_liquidity": True,
    "use_fvg_confirmation": False,
    "enable_accuracy_zones": True,
    "take_profit_pips": 0.0,
    "use_custom_rr": True,
    "risk_reward_ratio": 4.0,
    "max_position_size_lots": 100.0,
    "max_lots_per_10k": 10.0,
    "max_usd_risk_cap": 0.0,
    "use_half_risk_second_trade": True,
    "enable_trade_limit": True,
    "max_trades_per_day": 3,
    "filter_trading_hours": True,
    "require_htf_flip": True,
    "enable_ai_lite_mode": False,
    "enable_grade_filter": False,
    "min_entry_grade": "C",
}


def parse_fixed_overrides(raw: str | None) -> dict:
    """Parse comma-separated key=value optimizer overrides from CLI flags."""
    fixed_overrides: dict = {}
    if not raw:
        return fixed_overrides
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        value = value.strip()
        if value.lower() == "true":
            parsed: object = True
        elif value.lower() == "false":
            parsed = False
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        fixed_overrides[key.strip()] = parsed
    return fixed_overrides


def materialize_result_params(params: dict) -> dict:
    """Return a complete params snapshot for optimizer replay/manual entry."""
    materialized = {**OPTIMIZER_CONTEXT_PARAM_DEFAULTS, **params}
    rr_mode = materialized.get("rr_mode")
    if rr_mode is not None:
        if str(rr_mode) == "dynamic":
            materialized["use_custom_rr"] = False
        else:
            materialized["use_custom_rr"] = True
            materialized["risk_reward_ratio"] = float(str(rr_mode).replace("fixed_", ""))
    return materialized

OPTIMIZER_UI_ONLY_PARAMS = (
    "plotLiq",
    "show_fractals",
    "show_liquidity_connectors",
    "zone_label_style",
    "zone_label_show_metrics",
    "show_blocked_trade_labels",
    "debug_level",
    "showZoneInspector",
    "manual_zone_id_input",
    "showActiveProfile",
    "show_performance_table",
    "showResults",
    "table_text_size",
    "show_grade_on_zone",
    "show_ai_score_on_label",
    "start_date",
    "end_date",
)

CHECKBOX_PARAM_NAMES = {
    "news_blackout_enabled",
    "enable_date_filter",
    "invalidate_on_wick",
    "require_major_liquidity",
    "use_fvg_confirmation",
    "enable_accuracy_zones",
    "use_custom_rr",
    "use_break_even",
    "enable_double_tp",
    "use_half_risk_second_trade",
    "enable_trade_limit",
    "filter_trading_hours",
    "require_htf_flip",
    "enable_ai_quality_filter",
    "enable_ai_lite_mode",
    "enable_grade_filter",
}

# ─── Default pairs ────────────────────────────────────────────────────────────

# ─── Legacy parameter grids (kept for --fast / --smart backward compat) ───────

PARAM_GRID_FULL = {
    "liq_max_distance_pips_forex": [10.0, 15.0, 20.0, 25.0, 30.0],
    "ai_quality_threshold": [40, 50, 55, 60, 65, 70],
    "min_tp_distance_pips": [5.0, 8.0, 10.0, 12.0, 15.0],
    "max_sweep_to_touch_bars": [8, 12, 15, 20, 25],
    "max_peak_to_touch_bars": [20, 25, 30, 40, 50],
}

PARAM_GRID_FAST = {
    "liq_max_distance_pips_forex": [12.0, 18.0, 25.0],
    "ai_quality_threshold": [50, 60, 70],
    "min_tp_distance_pips": [5.0, 10.0, 15.0],
    "max_sweep_to_touch_bars": [10, 15, 20],
    "max_peak_to_touch_bars": [25, 35, 50],
}

# Gold-specific parameters (different scale)
PARAM_GRID_GOLD = {
    "liq_max_distance_pips_gold": [80.0, 120.0, 150.0, 200.0],
    "ai_quality_threshold": [40, 50, 60, 70],
    "min_tp_distance_pips": [5.0, 10.0, 15.0],
    "max_sweep_to_touch_bars": [10, 15, 20],
    "max_peak_to_touch_bars": [25, 35, 50],
}

# Index-specific parameters
PARAM_GRID_INDEX = {
    "liq_max_distance_pips_index": [300.0, 400.0, 500.0, 700.0],
    "ai_quality_threshold": [40, 50, 60],
    "min_tp_distance_pips": [5.0, 8.0, 12.0],
    "max_sweep_to_touch_bars": [10, 15, 20],
    "max_peak_to_touch_bars": [25, 35, 50],
}

# ─── Input index mapping ──────────────────────────────────────────────────────
# Map parameter names to their INPUT INDEX in TradingView settings dialog.
# Verified against the live TradingView settings dialog on 2026-04-29.

INPUT_INDEX = {
    # ── Prop Firm Risk Management (6 new inputs at top, indices 0-5) ──────────
    "risk_pct":                 0,   # 0.4
    "daily_kill_pct":           1,   # 4.0
    "total_kill_pct":           2,   # 8.0
    "consec_loss_kill":         3,   # 2
    "min_hold_minutes":         4,   # 2
    "news_blackout_enabled":    5,   # checkbox: false
    # ── Visible strategy settings dialog inputs ─────────────────────────────
    "account_size_usd": 6,           # 50000
    "risk_per_trade_pct": 7,         # 0.5
    "max_zones": 14,                 # Max Zones Displayed
    "min_body_perc": 15,             # Min Body %
    "liq_pivot_len": 18,             # Pivot Strength
    "pvtMax": 19,                    # Max Liquidity Lines
    "liq_max_distance_pips_forex": 21,
    "liq_max_distance_pips_gold": 22,
    "liq_max_distance_pips_index": 23,
    "liq_entry_max_dist": 24,        # Max Zone-to-Liq Distance
    "stop_loss_buffer_pips": 37,     # SL Buffer Pips
    "use_custom_rr": 38,             # checkbox: Override Use Fixed RR
    "risk_reward_ratio": 39,         # Custom R:R Ratio
    "min_tp_distance_pips": 40,      # Min TP Distance
    "take_profit_pips": 41,          # Fixed TP Override
    "use_break_even": 42,            # checkbox: Break-Even Mode
    "max_bars_held": 43,             # Time-Based Exit
    "enable_double_tp": 44,          # checkbox: Double TP Mode
    "max_position_size_lots": 45,    # 100
    "max_lots_per_10k": 46,          # 10
    "max_usd_risk_cap": 47,          # 0
    "max_daily_loss_pct": 49,        # Daily Loss Limit
    "max_daily_profit_pct": 50,      # Daily Profit Target
    "max_trades_per_day": 52,        # Max Trades/Day
    "trading_start_hour": 54,        # Start Hour
    "trading_end_hour": 55,          # End Hour
    "enable_ai_quality_filter": 57,  # checkbox: AI Quality Filter
    "ai_quality_threshold": 58,      # Min Score
    "max_peak_to_touch_bars": 61,    # Max Peak to Touch Bars
    "max_sweep_to_touch_bars": 62,   # Max Sweep to Touch Bars
}

# CHECKBOX indices — these need special handling (toggle, not fill)
CHECKBOX_INDICES = {5, 38, 42, 44, 57}

# ─── Hill-climbing params (kept for --smart backward compat) ──────────────────

HILL_CLIMB_PARAMS = [
    ("rr_mode", ["dynamic", "fixed_2.5", "fixed_4.0"], "rr_mode"),
    ("enable_ai_quality_filter", [True, False], "checkbox"),
    ("ai_quality_threshold", [50, 60, 70], "numeric"),
    ("min_tp_distance_pips", [5, 10, 15], "numeric"),
    ("liq_distance", [10, 20, 30], "liq_distance"),
    ("max_bars_held", [24, 48, 72], "numeric"),
    ("stop_loss_buffer_pips", [0.5, 1.0, 2.0], "numeric"),
    ("use_break_even", [True, False], "checkbox"),
    ("enable_double_tp", [True, False], "checkbox"),
    ("liq_pivot_len", [3, 5, 8], "numeric"),
    ("pvtMax", [3, 5, 10], "numeric"),
    ("max_sweep_to_touch_bars", [10, 15, 20], "numeric"),
    ("max_peak_to_touch_bars", [25, 35, 50], "numeric"),
    ("min_body_perc", [30, 50, 70], "numeric"),
    ("max_zones", [10, 20, 30], "numeric"),
    ("max_trades_per_day", [1, 2, 3], "numeric"),
]
