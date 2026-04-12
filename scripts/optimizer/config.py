"""
config.py — All constants for the TradingView Strategy Optimizer.
"""

from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "scripts" / "optimization_results"
RESULTS_DIR.mkdir(exist_ok=True)

CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"

# ─── Prop-firm constraints ────────────────────────────────────────────────────

PROP_FIRM_MAX_DD_PCT = 10.0   # Hard limit: score = 0 if DD% exceeds this

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
    "max_trades_per_day":       {"type": "int",         "low": 1,    "high": 4},
    "max_daily_loss_pct":       {"type": "float",       "low": 2.0,  "high": 5.0},   # prop firm safe range
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

# ─── Default pairs ────────────────────────────────────────────────────────────

DEFAULT_PAIRS = [
    # Major USD Pairs
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
    # JPY Pairs
    "USDJPY", "GBPJPY", "EURJPY", "NZDJPY", "CADJPY", "AUDJPY", "CHFJPY",
    # GBP Crosses
    "EURGBP", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
    # EUR Crosses
    "EURAUD", "EURCAD", "EURCHF", "EURNZD",
    # AUD/NZD Crosses
    "AUDNZD", "AUDCAD", "AUDCHF",
    # CAD/CHF Crosses
    "CADCHF", "NZDCAD", "NZDCHF",
    # Gold & Metals
    "XAUUSD", "XAGUSD",
    # Indices
    "NAS100", "US30", "US500",
]

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
# Discovered by tv_debug3.py on 2026-04-06 — dialog has inputs[0..56].

INPUT_INDEX = {
    "account_size_usd": 0,           # 50000
    "risk_per_trade_pct": 1,         # 0.5
    "max_zones": 8,                  # 20
    "min_body_perc": 9,              # 50
    "liq_pivot_len": 12,             # 5 (Pivot Strength)
    "pvtMax": 13,                    # 5 (Max Liquidity Lines)
    "liq_max_distance_pips_forex": 15,   # 20
    "liq_max_distance_pips_gold": 16,    # 150
    "liq_max_distance_pips_index": 17,   # 500
    "liq_entry_max_dist": 18,        # 10 (Max Zone-to-Liq Distance)
    "stop_loss_buffer_pips": 31,     # 1 (SL Buffer Pips)
    "use_custom_rr": 32,             # checkbox: Override Use Fixed RR
    "risk_reward_ratio": 33,         # 3 (Custom R:R Ratio)
    "min_tp_distance_pips": 34,      # 15
    "take_profit_pips": 35,          # 0 (Fixed TP Override)
    "use_break_even": 36,            # checkbox: Break-Even Mode
    "max_bars_held": 37,             # 72 (Time-Based Exit)
    "enable_double_tp": 38,          # checkbox: Double TP Mode
    "max_position_size_lots": 39,    # 100
    "max_lots_per_10k": 40,          # 10
    "max_usd_risk_cap": 41,          # 0
    "max_daily_loss_pct": 43,        # 4
    "max_daily_profit_pct": 44,      # 5
    "max_trades_per_day": 46,        # 2
    "trading_start_hour": 48,        # 6
    "trading_end_hour": 49,          # 22
    "enable_ai_quality_filter": 51,  # checkbox: AI Quality Filter
    "ai_quality_threshold": 52,      # 60
    "max_peak_to_touch_bars": 55,    # 30
    "max_sweep_to_touch_bars": 56,   # 15
}

# CHECKBOX indices — these need special handling (toggle, not fill)
CHECKBOX_INDICES = {32, 36, 38, 51}

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
