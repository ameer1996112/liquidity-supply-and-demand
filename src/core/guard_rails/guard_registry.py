"""
Guard Registry — Single source of truth for all guard rails.

Each guard is registered with:
- setting_key: The key in risk_config_overrides / settings.py
- tier: critical | important | convenience
- group: capital_protection | trade_quality | scheduling
- value_type: bool | int | float
- default: Default value when no override exists
- min/max: Validation bounds for numeric thresholds
- description: Developer-facing description
- user_description: Plain-English trader-facing explanation

Tiers determine UI behavior:
- critical:     Red lock icon, type-to-confirm disable, audit logged
- important:    Yellow icon, toggle with confirmation toast
- convenience:  Green icon, free toggle

Author: Trinity Engine v3.1
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GuardDefinition:
    guard_id: str
    setting_key: str
    name: str
    description: str
    user_description: str
    tier: str  # critical | important | convenience
    group: str  # capital_protection | trade_quality | scheduling
    value_type: str  # bool | int | float
    default: Any = True
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""  # e.g., "%", "pips", "seconds", "lots"
    thresholds: list = field(default_factory=list)  # Additional threshold settings


@dataclass
class ThresholdDef:
    setting_key: str
    name: str
    value_type: str  # int | float
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""


# ══════════════════════════════════════════════════════════
# GUARD REGISTRY
# ══════════════════════════════════════════════════════════

GUARD_REGISTRY: dict[str, GuardDefinition] = {}


def _register(g: GuardDefinition) -> None:
    GUARD_REGISTRY[g.guard_id] = g


# ── Capital Protection (critical) ────────────────────────

_register(GuardDefinition(
    guard_id="kill_switch",
    setting_key="trading_kill_switch",
    name="Kill Switch",
    description="Emergency stop — blocks ALL trade execution",
    user_description="Emergency stop button. When ON, no trades will execute. Use this if something goes wrong.",
    tier="critical",
    group="capital_protection",
    value_type="bool",
    default=False,
))

_register(GuardDefinition(
    guard_id="daily_loss_limit",
    setting_key="trinity_max_daily_loss_pct",
    name="Daily Loss Limit",
    description="Blocks trading when daily loss exceeds threshold",
    user_description="Stops all trading for the day if your losses exceed this percentage of your account. Protects you from revenge trading.",
    tier="critical",
    group="capital_protection",
    value_type="float",
    default=4.0,
    min_value=0.5,
    max_value=10.0,
    unit="%",
))

_register(GuardDefinition(
    guard_id="max_drawdown",
    setting_key="trinity_max_drawdown_pct",
    name="Max Drawdown",
    description="Scales risk down as drawdown increases",
    user_description="Automatically reduces position sizes when your account drops from its peak. Prevents catastrophic loss.",
    tier="critical",
    group="capital_protection",
    value_type="float",
    default=8.0,
    min_value=1.0,
    max_value=20.0,
    unit="%",
))

_register(GuardDefinition(
    guard_id="max_lot_size",
    setting_key="max_lot_size",  # Worker reads s.max_lot_size (settings.py field)
    name="Max Position Size",
    description="Rejects trades exceeding maximum lot size",
    user_description="Blocks any trade that tries to open a position larger than this limit. Prevents oversized trades from signal errors.",
    tier="critical",
    group="capital_protection",
    value_type="float",
    default=100.0,
    min_value=0.1,
    max_value=1000.0,
    unit="lots",
))

_register(GuardDefinition(
    guard_id="weekly_loss_limit",
    setting_key="enable_weekly_loss_limit",
    name="Weekly Loss Limit",
    description="Blocks trading when weekly loss exceeds threshold",
    user_description="Stops all trading for the week if your weekly losses exceed the limit. Good for prop firm challenges.",
    tier="critical",
    group="capital_protection",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("weekly_max_loss_pct", "Weekly Max Loss", "float", 6.0, 1.0, 20.0, "%"),
    ],
))

_register(GuardDefinition(
    guard_id="monthly_loss_limit",
    setting_key="enable_monthly_loss_limit",
    name="Monthly Loss Limit",
    description="Blocks trading when monthly loss exceeds threshold",
    user_description="Stops all trading for the month if your monthly losses exceed the limit.",
    tier="critical",
    group="capital_protection",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("monthly_max_loss_pct", "Monthly Max Loss", "float", 10.0, 2.0, 30.0, "%"),
    ],
))

_register(GuardDefinition(
    guard_id="prop_guard",
    setting_key="enable_risk_scaling",
    name="Prop Firm Risk Scaling",
    description="Step-up protocol: asymmetric compounding + survival mode",
    user_description="Automatically adjusts your risk based on account performance. Scales down in drawdown, scales up when profitable. Essential for prop firm accounts.",
    tier="critical",
    group="capital_protection",
    value_type="bool",
    default=True,
))

# ── Trade Quality (important) ────────────────────────────

_register(GuardDefinition(
    guard_id="staleness_guard",
    setting_key="enable_staleness_guard",
    name="Signal Freshness",
    description="Rejects signals that are too old or price has moved",
    user_description="Blocks trade signals that arrived late (>5 seconds old) or when price has already moved away from the entry. Prevents slippage.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("staleness_max_age_seconds", "Max Signal Age", "int", 5, 1, 30, "sec"),
        ThresholdDef("staleness_max_price_deviation_pips", "Max Price Deviation", "float", 3.0, 0.5, 10.0, "pips"),
    ],
))

_register(GuardDefinition(
    guard_id="correlation_guard",
    setting_key="trinity_max_positions",
    name="Correlation & Position Limit",
    description="Limits open positions and blocks correlated pairs",
    user_description="Prevents opening too many trades at once, and blocks trades in correlated pairs (e.g., EURUSD + GBPUSD). Limits concentration risk.",
    tier="important",
    group="trade_quality",
    value_type="int",
    default=3,
    min_value=1,
    max_value=10,
    unit="positions",
))

_register(GuardDefinition(
    guard_id="ai_debate",
    setting_key="ai_debate_enabled",  # Controls Trading Council (9-stage multi-agent pipeline)
    name="AI Trading Council",
    description="9-stage multi-agent debate pipeline evaluating trade quality",
    user_description="AI analyzes each trade signal through multiple agents (Market Analyst, Bull/Bear Researchers, Risk Judge). Currently runs in shadow mode — logs analysis but does not block trades.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
))

_register(GuardDefinition(
    guard_id="daily_trade_limit",
    setting_key="pine_adaptive_enabled",  # Worker reads pine_guardian.adaptive_enabled
    name="Adaptive Trade Limit",
    description="Session-quality adaptive daily trade limit with streak adjustment",
    user_description="Intelligently limits trades per day based on session (London/NY), your recent win streak, and risk budget. Fewer slots after losses, more after wins.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("pine_max_trades_per_day", "Fallback Static Limit", "int", 0, 0, 20, "trades"),
        ThresholdDef("pine_daily_risk_budget_pct", "Daily Risk Budget", "float", 3.0, 0.1, 20.0, "%"),
    ],
))

_register(GuardDefinition(
    guard_id="spread_gate",
    setting_key="spread_gate_enabled",
    name="Minimum SL Distance",
    description="Blocks trades where stop loss is too tight (spread would eat the trade)",
    user_description="Rejects trades where the stop loss is too close to entry. If SL is smaller than the typical spread, the trade would likely be stopped out immediately. Minimum: 5 pips forex, 7 pips JPY, 30 pips gold, 10 points indices.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("min_sl_pips_forex", "Min SL - Forex", "float", 5.0, 1.0, 20.0, "pips"),
        ThresholdDef("min_sl_pips_jpy", "Min SL - JPY Pairs", "float", 7.0, 1.0, 20.0, "pips"),
        ThresholdDef("min_sl_pips_gold", "Min SL - Gold/Silver", "float", 30.0, 5.0, 100.0, "pips"),
        ThresholdDef("min_sl_pips_indices", "Min SL - Indices", "float", 10.0, 1.0, 50.0, "pts"),
    ],
))

## circuit_breaker: REMOVED from registry — always runs in LIVE mode,
## no setting key controls it. Cannot be toggled via UI.
## Reset via API: POST /risk/circuit-breaker/reset

_register(GuardDefinition(
    guard_id="htf_candle_filter",
    setting_key="pine_htf_candle_filter_enabled",
    name="HTF Candle Filter",
    description="Blocks entries near candle boundaries (HTF opens + hourly close)",
    user_description="Protects against whipsaws near candle boundaries. Blocks entries before HTF candle opens and optionally in the last 10 minutes of each hour.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("pine_htf_candle_block_minutes", "Block Minutes Before", "int", 5, 1, 14, "min"),
        ThresholdDef("pine_block_before_hourly_close", "Block Before Hourly Close", "bool", True, None, None, ""),
    ],
))

_register(GuardDefinition(
    guard_id="middle_zone_filter",
    setting_key="pine_block_middle_zone",
    name="Middle Zone Filter",
    description="Blocks trades on intermediate zones when a better zone exists",
    user_description="Prevents entering on a zone when a stronger, trade-ready zone exists further in the same direction (active, swept liquidity, fresh <24h, unused).",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[],
))

_register(GuardDefinition(
    guard_id="one_candle_liq_filter",
    setting_key="pine_block_one_candle_liq",
    name="1-Candle Liquidity Filter",
    description="Blocks single-candle liquidity without strong departure",
    user_description="Filters out weak trade setups where the liquidity formation is only 1 candle long and doesn't have a strong move away from the zone.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("pine_one_candle_liq_min_departure", "Min Departure Score", "float", 40.0, 0.0, 100.0, ""),
    ],
))

# ── Scheduling & Market (convenience) ────────────────────

_register(GuardDefinition(
    guard_id="holiday_guard",
    setting_key="enable_holiday_guard",
    name="Market Holiday Filter",
    description="Blocks US index trades on exchange holidays",
    user_description="Prevents NAS100/US30/SPX500 trades on days when the stock market is closed (Good Friday, Thanksgiving, etc.).",
    tier="convenience",
    group="scheduling",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("holiday_block_early_close", "Block Early Close Days", "bool", False, None, None, ""),
    ],
))


_register(GuardDefinition(
    guard_id="mtm_guardian",
    setting_key="mtm_guardian_enabled",
    name="Real-Time Balance Check",
    description="Checks broker balance via MetaAPI before each trade",
    user_description="Verifies your actual broker balance before each trade. Catches cases where the database balance is out of sync.",
    tier="convenience",
    group="capital_protection",
    value_type="bool",
    default=True,
))


# ══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_guard(guard_id: str) -> Optional[GuardDefinition]:
    return GUARD_REGISTRY.get(guard_id)


def get_all_guards() -> list[GuardDefinition]:
    return list(GUARD_REGISTRY.values())


def get_guards_by_group() -> dict[str, list[GuardDefinition]]:
    groups: dict[str, list[GuardDefinition]] = {}
    for g in GUARD_REGISTRY.values():
        groups.setdefault(g.group, []).append(g)
    return groups


def get_guards_by_tier(tier: str) -> list[GuardDefinition]:
    return [g for g in GUARD_REGISTRY.values() if g.tier == tier]


GROUP_LABELS = {
    "capital_protection": "Capital Protection",
    "trade_quality": "Trade Quality",
    "scheduling": "Scheduling & Market",
}

TIER_LABELS = {
    "critical": "Critical",
    "important": "Important",
    "convenience": "Convenience",
}
