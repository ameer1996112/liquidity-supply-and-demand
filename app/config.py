"""
Config dataclass mirroring SND_Strategy.pine inputs.

Strategy properties (from strategy() declaration):
- process_orders_on_close = True (fill orders on bar close)
- pyramiding = 0 (no stacking positions)
- slippage = 3 (ticks)
- commission_type = percent, commission_value = 0
- default_qty_type = fixed, default_qty_value = 100 (Pine overrides with pos_qty_units)
- calc_on_every_tick = False (evaluate once per bar)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BacktestConfig:
    """Pine inputs affecting trading outcomes."""

    # Strategy execution
    process_orders_on_close: bool = True
    pyramiding: int = 0
    slippage_ticks: int = 3
    commission_pct: float = 0.0
    calc_on_every_tick: bool = False

    # Instrument (affects pip_size, tick_size, contract_size)
    # XAUUSD: pip_size=0.01, tick_size=0.01, contract_size=100
    tick_size: float = 0.01  # syminfo.mintick - XAUUSD commonly 0.01
    pip_size: float = 0.01   # From get_auto_pip_size for XAU
    contract_size: float = 100.0  # GOLD_LOT_SIZE

    # Quick Setup
    config_profile: str = "Balanced (Recommended)"
    trade_direction: str = "Both"  # Both, Long Only, Short Only
    account_size_usd: float = 50000.0
    risk_per_trade_pct: float = 0.5
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Zone / Liquidity
    invalidate_on_wick: bool = True
    max_zones: int = 20
    min_body_perc: float = 50.0
    liq_pivot_len: int = 5
    structure_mode: str = "Relaxed (Wicks)"
    pvt_max: int = 5
    require_major_liquidity: bool = True
    use_one_candle_liquidity: bool = True
    liq_max_distance_pips_forex: float = 10.0
    liq_max_distance_pips_gold: float = 300.0
    liq_max_distance_pips_index: float = 5000.0

    # Risk / SL / TP
    stop_loss_buffer_pips: float = 1.0
    use_custom_rr: bool = False
    risk_reward_ratio: float = 2.0
    liq_entry_max_dist: float = 50.0
    min_tp_distance_pips: float = 5.0
    take_profit_pips: float = 0.0

    # Position sizing
    min_position_size_units: int = 1000
    max_position_size_lots: float = 10.0

    # Filters
    enable_trade_limit: bool = True
    max_trades_per_day: int = 2
    filter_dead_zone: bool = True
    filter_trading_hours: bool = True
    trading_start_hour: int = 7  # UTC
    trading_end_hour: int = 22   # UTC
    require_htf_flip: bool = True
    enable_ai_quality_filter: bool = True
    ai_quality_threshold: int = 60
    enable_grade_filter: bool = False
    min_entry_grade: str = "C"
    min_return_strength: int = 0

    # Advanced
    use_break_even: bool = False
    max_bars_held: int = 36
    enable_double_tp: bool = False
    use_fvg_confirmation: bool = False
    enable_accuracy_zones: bool = True

    # Date filter
    enable_date_filter: bool = True
    min_bar_index_for_entries: int = 100

    # Daily limits
    max_daily_loss_pct: float = 2.0
    max_daily_profit_pct: float = 5.0

    # Data / symbol
    initial_equity: float = 50000.0
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    # Symbol adapter: MT5 may use XAUUSDm, Vantage may differ
    symbol_aliases: dict = field(default_factory=lambda: {"XAUUSD": ["XAUUSDm", "XAUUSD.raw"]})

    def get_effective_liq_max_dist(self, is_gold: bool, is_index: bool) -> float:
        if is_index:
            return self.liq_max_distance_pips_index
        return self.liq_max_distance_pips_gold if is_gold else self.liq_max_distance_pips_forex

    def is_gold(self) -> bool:
        return "XAU" in self.symbol or "GOLD" in self.symbol

    def is_index(self) -> bool:
        idx = ["NAS", "US100", "NDX", "SPX", "US500", "US30", "DJI"]
        return any(x in self.symbol.upper() for x in idx)
