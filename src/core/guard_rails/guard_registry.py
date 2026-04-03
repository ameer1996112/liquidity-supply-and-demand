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
    setting_key="pine_max_lot_size",
    name="Max Position Size",
    description="Rejects trades exceeding maximum lot size",
    user_description="Blocks any trade that tries to open a position larger than this limit. Prevents oversized trades from signal errors.",
    tier="critical",
    group="capital_protection",
    value_type="float",
    default=10.0,
    min_value=0.01,
    max_value=100.0,
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
    guard_id="ai_filter",
    setting_key="ai_filter_enabled",
    name="AI Quality Filter",
    description="ML ensemble evaluates trade quality before execution",
    user_description="AI analyzes each trade signal and blocks low-quality setups. Can run in shadow mode (log only, never block) for testing.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("ai_shadow_mode", "Shadow Mode (log only)", "bool", False, None, None, ""),
    ],
))

_register(GuardDefinition(
    guard_id="daily_trade_limit",
    setting_key="pine_daily_trade_slots",
    name="Daily Trade Limit",
    description="Adaptive daily trade limit based on recent performance",
    user_description="Limits how many trades you can take per day. Automatically adjusts based on your recent win rate — fewer slots after losing streaks.",
    tier="important",
    group="trade_quality",
    value_type="int",
    default=2,
    min_value=1,
    max_value=10,
    unit="trades/day",
))

_register(GuardDefinition(
    guard_id="spread_gate",
    setting_key="spread_gate_enabled",
    name="Spread Gate",
    description="Blocks trades when bid-ask spread is too wide",
    user_description="Blocks trades when the broker's spread is abnormally wide (low liquidity, news events). Prevents entering at bad prices.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
))

_register(GuardDefinition(
    guard_id="circuit_breaker",
    setting_key="circuit_breaker_enabled",
    name="Circuit Breaker",
    description="Stops execution after repeated broker API failures",
    user_description="Automatically pauses trading if the broker connection keeps failing. Prevents repeated failed orders.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
))

_register(GuardDefinition(
    guard_id="htf_candle_filter",
    setting_key="pine_htf_candle_filter_enabled",
    name="HTF Candle Filter",
    description="Blocks entries near higher-timeframe candle opens",
    user_description="Avoids entering trades in the last few minutes before a 15-minute candle closes, when price can spike unpredictably.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("pine_htf_candle_block_minutes", "Block Minutes Before", "int", 5, 1, 14, "min"),
    ],
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
    guard_id="dead_zone",
    setting_key="pine_block_dead_zone",
    name="Dead Zone Filter",
    description="Blocks entries at xx:50-xx:00 (candle boundary)",
    user_description="Avoids entering trades in the last 10 minutes of each hour, when price often whipsaws around the candle close.",
    tier="convenience",
    group="scheduling",
    value_type="bool",
    default=False,
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
