"""
config.py — All constants for the TradingView Strategy Optimizer.
"""

from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "scripts" / "optimization_results"
RESULTS_DIR.mkdir(exist_ok=True)

CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"

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

# ─── Parameter grids ──────────────────────────────────────────────────────────

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

# ─── Input index mapping ───────────────────────────────────────────────────────
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

# ─── Hill-climbing params ─────────────────────────────────────────────────────
# Ordered by expected impact. Each entry: (param_name, [values_to_test], type)
# type: "numeric" = fill(), "checkbox" = toggle, "rr_mode" = special handling

HILL_CLIMB_PARAMS = [
    # 1. RR Mode: dynamic rules vs fixed 2.5 vs fixed 4.0
    ("rr_mode", ["dynamic", "fixed_2.5", "fixed_4.0"], "rr_mode"),
    # 2. AI Filter on/off
    ("enable_ai_quality_filter", [True, False], "checkbox"),
    # 3. AI threshold (only matters if AI filter is on)
    ("ai_quality_threshold", [50, 60, 70], "numeric"),
    # 4. Min TP Distance
    ("min_tp_distance_pips", [5, 10, 15], "numeric"),
    # 5. Liq Distance (asset-class dependent — resolved at runtime)
    ("liq_distance", [10, 20, 30], "liq_distance"),
    # 6. Time-Based Exit
    ("max_bars_held", [24, 48, 72], "numeric"),
    # 7. SL Buffer
    ("stop_loss_buffer_pips", [0.5, 1.0, 2.0], "numeric"),
    # 8. Break-Even Mode
    ("use_break_even", [True, False], "checkbox"),
    # 9. Double TP Mode
    ("enable_double_tp", [True, False], "checkbox"),
    # 10. Pivot Strength
    ("liq_pivot_len", [3, 5, 8], "numeric"),
    # 11. Max Liquidity Lines
    ("pvtMax", [3, 5, 10], "numeric"),
    # 12. Max Sweep to Touch Bars
    ("max_sweep_to_touch_bars", [10, 15, 20], "numeric"),
    # 13. Max Peak to Touch Bars
    ("max_peak_to_touch_bars", [25, 35, 50], "numeric"),
    # 14. Min Body %
    ("min_body_perc", [30, 50, 70], "numeric"),
    # 15. Max Zones Displayed
    ("max_zones", [10, 20, 30], "numeric"),
    # 16. Max Trades/Day
    ("max_trades_per_day", [1, 2, 3], "numeric"),
]
