"""
Risk Engine - Prop firm capital preservation logic.
Pure domain: no DB/API calls. Used by worker and guard_rails.
"""

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

DEFAULT_MAX_DAILY_LOSS_PCT = 4.0
DEFAULT_MAX_DRAWDOWN_PCT = 8.0
DEFAULT_MAX_RISK_PER_TRADE_PCT = 1.0
DEFAULT_STARTING_EQUITY = 10_000.0
DEFAULT_MIN_LOT_SIZE = 0.01
DEFAULT_LOT_STEP = 0.01
DEFAULT_STOP_LOSS_BUFFER_PIPS = 1.0
PASS_EVAL_MIN_RISK_PCT = 0.25
PASS_EVAL_MAX_RISK_PCT = 0.75

PAIR_PERFORMANCE_MULTIPLIERS = {
    "strong": 1.05,
    "neutral": 1.00,
    "weak": 0.75,
    "very_weak": 0.50,
}

ACCOUNT_SAFETY_MULTIPLIERS = {
    "normal": 1.00,
    "caution": 0.75,
    "defensive": 0.50,
    "survival": 0.25,
    "lockout": 0.00,
}

FREQUENCY_MULTIPLIERS = {
    0: 1.00,
    1: 0.85,
    2: 0.70,
    3: 0.50,
}


class RiskRejectionReason(str, Enum):
    DAILY_LOSS_LIMIT = "daily_loss_limit_exceeded"
    EQUITY_DRAWDOWN = "equity_drawdown_exceeded"
    RISK_TOO_HIGH = "risk_per_trade_exceeded"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    INVALID_RISK_PARAMS = "invalid_risk_parameters"


class RiskCheckResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    passed: bool = Field(description="Whether the trade passed all risk checks")
    rejection_reason: Optional[RiskRejectionReason] = Field(default=None)
    rejection_message: Optional[str] = Field(default=None)
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)


class TradeRiskParams(BaseModel):
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trade direction (buy/sell)")
    entry_price: float = Field(gt=0, description="Entry price")
    stop_loss: float = Field(gt=0, description="Stop loss price")
    position_size: float = Field(gt=0, description="Position size in lots")
    risk_amount_usd: Optional[float] = Field(default=None)

    @property
    def calculated_risk_pips(self) -> float:
        return abs(self.entry_price - self.stop_loss)


def _normalize_symbol_overrides(symbol_overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    overrides = dict(symbol_overrides or {})
    overrides["enabled"] = bool(overrides.get("enabled", True))
    overrides["min_lot_size"] = float(overrides.get("min_lot_size") or DEFAULT_MIN_LOT_SIZE)
    overrides["lot_step"] = float(overrides.get("lot_step") or DEFAULT_LOT_STEP)
    overrides["stop_loss_buffer_pips"] = float(
        overrides.get("stop_loss_buffer_pips") or DEFAULT_STOP_LOSS_BUFFER_PIPS
    )
    return overrides


def calculate_effective_risk_percent(
    *,
    base_risk_percent: float,
    mode: str,
    pair_performance_state: str = "neutral",
    same_day_trade_count: int = 0,
    account_safety_state: str = "normal",
) -> float:
    """Return the effective per-trade risk after pass-eval multipliers and clamps."""
    normalized_mode = str(mode or "NORMAL").upper()
    if normalized_mode != "PASS_EVAL":
        return float(base_risk_percent)

    performance_multiplier = PAIR_PERFORMANCE_MULTIPLIERS.get(
        str(pair_performance_state or "neutral").lower(), 1.0
    )
    frequency_multiplier = FREQUENCY_MULTIPLIERS.get(max(int(same_day_trade_count or 0), 0), 0.25)
    safety_multiplier = ACCOUNT_SAFETY_MULTIPLIERS.get(
        str(account_safety_state or "normal").lower(), 1.0
    )

    effective = float(base_risk_percent) * performance_multiplier * frequency_multiplier * safety_multiplier
    if safety_multiplier <= 0.0:
        return 0.0
    return max(PASS_EVAL_MIN_RISK_PCT, min(PASS_EVAL_MAX_RISK_PCT, effective))


def calculate_max_position_size(
    payload: Dict[str, Any],
    account_balance: float,
    risk_percent: float,
    risk_multiplier: float = 1.0,
    symbol_overrides: Optional[Dict[str, Any]] = None,
) -> float:
    """Maximum allowed lot size from account balance and risk %, with scaling.

    Args:
        payload: Trade payload with at least ``symbol``, ``entry`` and ``sl``.
        account_balance: Account equity in USD.
        risk_percent: Base risk per trade (e.g. ``1.0`` for 1%).
        risk_multiplier: Additional scaling factor (0-1 defensive, >1 aggressive).
        symbol_overrides: Per-symbol pip/risk values from ``symbol_risk_rules`` table.

    Returns:
        Capped maximum lot size after applying the risk multiplier.
    """
    try:
        entry = float(payload.get("entry", 0))
        sl = float(payload.get("sl", 0))
        symbol = payload.get("symbol", "UNKNOWN")
        side = payload.get("side", "buy").lower()
        if entry == 0 or sl == 0:
            return 1.0

        overrides = _normalize_symbol_overrides(symbol_overrides)
        if symbol_overrides and not overrides.get("enabled", True):
            logger.warning("Position sizing blocked for disabled symbol rule: %s", symbol)
            return 0.0

        # Per-symbol overrides from DB (if provided and enabled)
        if symbol_overrides and overrides.get("enabled", True):
            pip_size = float(overrides.get("pip_size", 0.0001))
            pip_value_per_lot = float(overrides.get("pip_value_per_lot", 10.0))
            risk_percent = float(overrides.get("risk_percent", risk_percent))
            max_lot_cap = float(overrides.get("max_lot_size", 10.0))
            min_lot_size = float(overrides.get("min_lot_size", DEFAULT_MIN_LOT_SIZE))
            lot_step = float(overrides.get("lot_step", DEFAULT_LOT_STEP))
            sl_buffer_pips = float(overrides.get("stop_loss_buffer_pips", DEFAULT_STOP_LOSS_BUFFER_PIPS))
        else:
            # Hardcoded fallback for unknown symbols
            # IMPORTANT: Check indices and crypto FIRST before forex
            if any(idx in symbol.upper() for idx in ["NAS100", "US30", "SPX", "UK100", "GER", "FRA", "JPN225", "AUS200"]):
                pip_size = 1.0  # 1 point = 1 pip for indices
                pip_value_per_lot = 1.0  # $1 per point per lot (most US indices)
            elif any(crypto in symbol.upper() for crypto in ["BTC", "ETH", "BCH", "LTC", "XRP", "ADA", "SOL", "DOGE"]):
                pip_size = 1.0  # 1 point = 1 pip for crypto
                pip_value_per_lot = 1.0  # $1 per point per lot
            elif "JPY" in symbol:
                pip_size = 0.01
                # ✅ DYNAMIC pip value calculation for JPY pairs (Migration 026)
                # Formula: pip_value = (pip_size / exchange_rate) * lot_size
                # Example: NZDJPY @ 93.918 → (0.01 / 93.918) * 100,000 = $10.65/lot
                if entry > 0:
                    pip_value_per_lot = (pip_size / entry) * 100000
                    logger.debug(
                        f"JPY pair {symbol}: Dynamic pip_value=${pip_value_per_lot:.2f}/lot "
                        f"(entry={entry:.5f})"
                    )
                else:
                    # Fallback to USDJPY approximation if entry price unavailable
                    pip_value_per_lot = 1000.0
                    logger.warning(
                        f"JPY pair {symbol}: Using static pip_value=1000.0 (no entry price). "
                        "This may cause position sizing errors!"
                    )
            elif "XAU" in symbol or "GOLD" in symbol or "XAG" in symbol or "SILVER" in symbol:
                pip_size = 0.01
                pip_value_per_lot = 100.0
            else:
                pip_size = 0.0001
                pip_value_per_lot = 10.0

            # Get max_lot_cap and sl_buffer from settings
            try:
                from config import get_settings  # type: ignore
                s = get_settings()
                max_lot_cap = float(getattr(s, "max_lot_size", 10.0))
                sl_buffer_pips = float(getattr(s, "stop_loss_buffer_pips", 1.0))
            except Exception:
                max_lot_cap = 10.0
                sl_buffer_pips = 1.0
            min_lot_size = DEFAULT_MIN_LOT_SIZE
            lot_step = DEFAULT_LOT_STEP

        # Apply stop loss buffer (Pine: adds 1 pip safety margin beyond zone)
        # For buy: SL is below entry, so subtract buffer (more conservative)
        # For sell: SL is above entry, so add buffer (more conservative)
        sl_buffer = sl_buffer_pips * pip_size
        if side == "buy":
            sl_adjusted = sl - sl_buffer
        else:
            sl_adjusted = sl + sl_buffer

        effective_risk_percent = calculate_effective_risk_percent(
            base_risk_percent=risk_percent,
            mode=str(payload.get("_risk_mode", "NORMAL")),
            pair_performance_state=str(payload.get("_pair_performance_state", "neutral")),
            same_day_trade_count=int(payload.get("_same_day_trade_count", 0)),
            account_safety_state=str(payload.get("_account_safety_state", "normal")),
        )
        if effective_risk_percent <= 0:
            logger.warning("Position sizing blocked for %s due to pass-eval lockout", symbol)
            return 0.0

        # Base risk in USD from percentage
        max_risk_usd = account_balance * (effective_risk_percent / 100.0)

        # Optional volatility targeting via ATR
        use_vol_targeting = False
        try:
            from config import get_settings  # type: ignore

            s = get_settings()
            use_vol_targeting = bool(getattr(s, "volatility_targeting", False))
        except Exception:
            use_vol_targeting = False

        atr = payload.get("atr")
        if use_vol_targeting and atr is not None:
            try:
                atr_val = float(atr)
            except (TypeError, ValueError):
                atr_val = 0.0

            if atr_val > 0:
                base_max_lots = max_risk_usd / (atr_val * pip_value_per_lot)
                scaled_max_lots = base_max_lots * max(risk_multiplier, 0.0)
                final_atr_lots = min(max(scaled_max_lots, 0.0), max_lot_cap)
                logger.info(
                    "💰 Risk Calculation: Bal=$%.2f | Risk=%.2f%% ($%.2f) | SL_Dist=ATR(%.4f) | Calc_Lots=%.2f",
                    account_balance, effective_risk_percent, max_risk_usd, atr_val, final_atr_lots,
                )
                return final_atr_lots

        # Fallback: distance-to-stop based sizing (using adjusted SL with buffer)
        sl_distance = abs(entry - sl_adjusted)
        sl_pips = sl_distance / pip_size

        if sl_pips > 0:
            base_max_lots = max_risk_usd / (sl_pips * pip_value_per_lot)
            scaled_max_lots = base_max_lots * max(risk_multiplier, 0.0)

            # ✅ Enforce minimum lot size (v5.1 - Zero Size Bug Fix)
            # If calculated size is below minimum, return 0.0 to signal rejection
            # (Caller should provide clear error message about stop loss being too wide)
            if scaled_max_lots < min_lot_size:
                logger.warning(
                    "Calculated lot size %.4f below minimum %.2f for %s "
                    "(risk=$%.2f, sl_pips=%.2f, pip_value=%.2f). "
                    "Stop loss may be too wide for account size.",
                    scaled_max_lots, min_lot_size, symbol,
                    max_risk_usd, sl_pips, pip_value_per_lot
                )
                logger.info(
                    "💰 Risk Calculation: Bal=$%.2f | Risk=%.2f%% ($%.2f) | SL_Dist=%.5f | Calc_Lots=0.00 (rejected: below min)",
                    account_balance, effective_risk_percent, max_risk_usd, sl_distance,
                )
                return 0.0  # Signal rejection to caller

            # Cap at max and round to lot step
            final_lots = min(scaled_max_lots, max_lot_cap)

            # Round to lot step (e.g., 0.01 for forex)
            final_lots = round(final_lots / lot_step) * lot_step

            # Ensure we didn't round below minimum
            final_lots = max(min_lot_size, final_lots)

            logger.info(
                "💰 Risk Calculation: Bal=$%.2f | Risk=%.2f%% ($%.2f) | SL_Dist=%.5f | Calc_Lots=%.2f",
                account_balance, effective_risk_percent, max_risk_usd, sl_distance, final_lots,
            )
            logger.info(
                "Position sizing: %s | base=%.4f | scaled=%.4f | final=%.2f lots "
                "(min=%.2f, max=%.2f, step=%.2f)",
                symbol, base_max_lots, scaled_max_lots, final_lots,
                min_lot_size, max_lot_cap, lot_step
            )

            return final_lots

        return 1.0
    except Exception as e:
        logger.warning(f"Max size calculation error: {e}")
        return 1.0


def calculate_position_size_with_spread(
    payload: Dict[str, Any],
    account_balance: float,
    risk_percent: float,
    spread: float = 0.0,
    broker_spec: Optional[Dict[str, Any]] = None,
    risk_multiplier: float = 1.0,
    symbol_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculate position size accounting for broker spread and contract specs.

    This is the **single source of truth** for position sizing.  Pine sends a
    signal (entry/sl/tp); the backend recalculates lots using live broker data.

    Args:
        payload: Trade payload with ``symbol``, ``entry``, ``sl``, ``side``.
        account_balance: Live account balance from broker.
        risk_percent: Risk per trade (e.g. 0.5 for 0.5%).
        spread: Current spread in price terms (ask - bid).
        broker_spec: MetaAPI symbol specification (contractSize, minVolume, volumeStep, etc.).
        risk_multiplier: PropGuard / time-based scaling factor.
        symbol_overrides: Per-symbol overrides from ``symbol_risk_rules`` table.

    Returns:
        Dict with ``lots``, ``risk_usd``, ``sl_pips``, ``spread_pips``,
        ``effective_sl_pips``, ``pip_value_per_lot``, ``rejected`` (bool),
        ``rejection_reason`` (str or None).
    """
    try:
        entry = float(payload.get("entry", 0))
        sl = float(payload.get("sl", 0))
        symbol = payload.get("symbol", "UNKNOWN")

        overrides = _normalize_symbol_overrides(symbol_overrides)

        if entry == 0 or sl == 0:
            return {
                "lots": 0.0, "risk_usd": 0.0, "sl_pips": 0.0, "spread_pips": 0.0,
                "effective_sl_pips": 0.0, "pip_value_per_lot": 0.0,
                "rejected": True, "rejection_reason": "Missing entry or SL price",
            }

        # ── Determine pip_size and pip_value_per_lot ──
        # Priority: broker_spec > symbol_overrides > hardcoded fallback
        min_lot = 0.01
        lot_step = 0.01
        max_lot_cap = 10.0

        if symbol_overrides is not None and not overrides.get("enabled", True):
            return {
                "lots": 0.0, "risk_usd": 0.0, "sl_pips": 0.0, "spread_pips": 0.0,
                "effective_sl_pips": 0.0, "pip_value_per_lot": 0.0,
                "rejected": True, "rejection_reason": "symbol_disabled",
            }

        if broker_spec:
            # Use real broker data
            contract_size = float(broker_spec.get("contractSize", 100000))
            digits = int(broker_spec.get("digits", 5))
            min_lot = float(broker_spec.get("minVolume", 0.01))
            lot_step = float(broker_spec.get("volumeStep", 0.01))
            max_lot_cap_broker = float(broker_spec.get("maxVolume", 1000))

            # Derive pip_size from digits
            # Forex 5-digit: pip = 0.0001, 3-digit (JPY): pip = 0.01
            # Gold 2-digit: pip = 0.01, Index 1-digit: pip = 1.0
            if digits >= 5:
                pip_size = 10 ** -(digits - 1)  # 5 digits → 0.0001
            elif digits >= 3:
                pip_size = 10 ** -(digits - 1)  # 3 digits → 0.01
            else:
                pip_size = 10 ** -digits  # 2 digits → 0.01, 1 digit → 0.1

            # pip_value_per_lot depends on quote currency
            # For USD-quoted pairs: pip_value = pip_size * contract_size
            # For non-USD-quoted: pip_value = (pip_size * contract_size) / current_price
            sym_upper = symbol.upper()
            if "JPY" in sym_upper:
                pip_size = 0.01
                pip_value_per_lot = (pip_size / entry) * contract_size if entry > 0 else 10.0
            elif any(x in sym_upper for x in ["XAU", "GOLD", "XAG", "SILVER"]):
                pip_size = 0.01
                pip_value_per_lot = pip_size * contract_size
            elif any(x in sym_upper for x in ["NAS", "US30", "SPX", "US100", "US500", "GER", "UK100"]):
                pip_size = 1.0
                pip_value_per_lot = 1.0 * contract_size  # $1 per point × contract
            elif any(x in sym_upper for x in ["BTC", "ETH"]):
                pip_size = 1.0
                pip_value_per_lot = 1.0 * contract_size
            elif sym_upper.endswith("USD") or "USD" in sym_upper[3:]:
                # USD is quote currency: EURUSD, GBPUSD, etc.
                pip_size = 0.0001
                pip_value_per_lot = pip_size * contract_size  # = $10 per pip for 100k lot
            else:
                # USD is base or neither: USDCAD, EURGBP, etc.
                pip_size = 0.0001
                pip_value_per_lot = (pip_size * contract_size) / entry if entry > 0 else 10.0

            try:
                from config import get_settings
                s = get_settings()
                max_lot_cap = min(float(getattr(s, "max_lot_size", 10.0)), max_lot_cap_broker)
            except Exception:
                max_lot_cap = min(10.0, max_lot_cap_broker)

        elif symbol_overrides and overrides.get("enabled", True):
            # DB overrides
            pip_size = float(overrides.get("pip_size", 0.0001))
            pip_value_per_lot = float(overrides.get("pip_value_per_lot", 10.0))
            risk_percent = float(overrides.get("risk_percent", risk_percent))
            max_lot_cap = float(overrides.get("max_lot_size", 10.0))
            min_lot = float(overrides.get("min_lot_size", DEFAULT_MIN_LOT_SIZE))
            lot_step = float(overrides.get("lot_step", DEFAULT_LOT_STEP))
        else:
            # Hardcoded fallback (same as calculate_max_position_size)
            sym_upper = symbol.upper()
            if any(idx in sym_upper for idx in ["NAS100", "US30", "SPX", "UK100", "GER", "FRA", "JPN225", "AUS200"]):
                pip_size = 1.0
                pip_value_per_lot = 1.0
            elif any(crypto in sym_upper for crypto in ["BTC", "ETH", "BCH", "LTC", "XRP", "ADA", "SOL", "DOGE"]):
                pip_size = 1.0
                pip_value_per_lot = 1.0
            elif "JPY" in sym_upper:
                pip_size = 0.01
                pip_value_per_lot = (pip_size / entry) * 100000 if entry > 0 else 10.0
            elif "XAU" in sym_upper or "GOLD" in sym_upper or "XAG" in sym_upper:
                pip_size = 0.01
                pip_value_per_lot = 100.0
            else:
                pip_size = 0.0001
                pip_value_per_lot = 10.0
            try:
                from config import get_settings
                s = get_settings()
                max_lot_cap = float(getattr(s, "max_lot_size", 10.0))
            except Exception:
                max_lot_cap = 10.0

        # ── SL distance + spread compensation ──
        sl_distance = abs(entry - sl)
        spread_in_pips = spread / pip_size if pip_size > 0 else 0.0
        sl_pips = sl_distance / pip_size

        # Add spread to effective SL distance (spread widens your actual risk)
        effective_sl_distance = sl_distance + spread
        effective_sl_pips = effective_sl_distance / pip_size

        # Also add SL buffer (1 pip safety margin)
        try:
            from config import get_settings
            default_buffer = float(getattr(get_settings(), "stop_loss_buffer_pips", DEFAULT_STOP_LOSS_BUFFER_PIPS))
        except Exception:
            default_buffer = DEFAULT_STOP_LOSS_BUFFER_PIPS
        sl_buffer_pips = float(overrides.get("stop_loss_buffer_pips", default_buffer))
        effective_sl_pips += sl_buffer_pips

        effective_risk_percent = calculate_effective_risk_percent(
            base_risk_percent=risk_percent,
            mode=str(payload.get("_risk_mode", "NORMAL")),
            pair_performance_state=str(payload.get("_pair_performance_state", "neutral")),
            same_day_trade_count=int(payload.get("_same_day_trade_count", 0)),
            account_safety_state=str(payload.get("_account_safety_state", "normal")),
        )
        if effective_risk_percent <= 0:
            return {
                "lots": 0.0, "risk_usd": 0.0, "target_risk_usd": 0.0,
                "sl_pips": sl_pips, "spread_pips": spread_in_pips,
                "effective_sl_pips": effective_sl_pips, "pip_value_per_lot": pip_value_per_lot,
                "effective_risk_percent": 0.0,
                "rejected": True, "rejection_reason": "pass_eval_lockout",
            }

        # ── Calculate risk and lots ──
        max_risk_usd = account_balance * (effective_risk_percent / 100.0)

        if effective_sl_pips <= 0 or pip_value_per_lot <= 0:
            return {
                "lots": 0.0, "risk_usd": max_risk_usd, "sl_pips": sl_pips,
                "spread_pips": spread_in_pips, "effective_sl_pips": effective_sl_pips,
                "pip_value_per_lot": pip_value_per_lot,
                "rejected": True, "rejection_reason": "Invalid SL distance or pip value",
            }

        base_lots = max_risk_usd / (effective_sl_pips * pip_value_per_lot)
        scaled_lots = base_lots * max(risk_multiplier, 0.0)

        if scaled_lots < min_lot:
            logger.warning(
                "Position size %.4f below minimum %.2f for %s "
                "(risk=$%.2f, eff_sl=%.2f pips, pip_value=%.2f). SL too wide for account.",
                scaled_lots, min_lot, symbol, max_risk_usd, effective_sl_pips, pip_value_per_lot,
            )
            return {
                "lots": 0.0, "risk_usd": max_risk_usd, "sl_pips": sl_pips,
                "spread_pips": spread_in_pips, "effective_sl_pips": effective_sl_pips,
                "pip_value_per_lot": pip_value_per_lot,
                "rejected": True,
                "rejection_reason": f"Size {scaled_lots:.4f} below min {min_lot} — SL too wide",
            }

        # Cap and round
        final_lots = min(scaled_lots, max_lot_cap)
        final_lots = round(final_lots / lot_step) * lot_step
        final_lots = max(min_lot, final_lots)

        # Actual risk with this lot size
        actual_risk_usd = final_lots * effective_sl_pips * pip_value_per_lot

        logger.info(
            "📐 Position Sizing [%s]: Balance=$%.2f | Risk=%.2f%% ($%.2f target) | "
            "SL=%.1f pips + %.1f spread + %.1f buffer = %.1f effective | "
            "Pip value=$%.2f | Lots=%.2f | Actual risk=$%.2f",
            symbol, account_balance, effective_risk_percent, max_risk_usd,
            sl_pips, spread_in_pips, sl_buffer_pips, effective_sl_pips,
            pip_value_per_lot, final_lots, actual_risk_usd,
        )

        return {
            "lots": round(final_lots, 2),
            "risk_usd": round(actual_risk_usd, 2),
            "target_risk_usd": round(max_risk_usd, 2),
            "effective_risk_percent": round(effective_risk_percent, 4),
            "sl_pips": round(sl_pips, 1),
            "spread_pips": round(spread_in_pips, 1),
            "effective_sl_pips": round(effective_sl_pips, 1),
            "pip_value_per_lot": round(pip_value_per_lot, 4),
            "rejected": False,
            "rejection_reason": None,
        }

    except Exception as e:
        logger.error("calculate_position_size_with_spread error: %s", e)
        return {
            "lots": 0.0, "risk_usd": 0.0, "sl_pips": 0.0, "spread_pips": 0.0,
            "effective_sl_pips": 0.0, "pip_value_per_lot": 0.0,
            "rejected": True, "rejection_reason": f"Calculation error: {e}",
        }


class RiskGuardian:
    """Prop firm risk rules: kill switch, daily loss limit, drawdown, anti-gambling."""

    def __init__(
        self,
        starting_equity: float = DEFAULT_STARTING_EQUITY,
        max_daily_loss_pct: float = DEFAULT_MAX_DAILY_LOSS_PCT,
        max_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN_PCT,
        max_risk_per_trade_pct: float = DEFAULT_MAX_RISK_PER_TRADE_PCT,
    ):
        self.starting_equity = starting_equity
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self._kill_switch_active = False
        self._kill_switch_reason: Optional[str] = None
        self._kill_switch_timestamp: Optional[datetime] = None
        self._daily_start_equity = starting_equity
        self._current_date = date.today()
        self._daily_pnl = 0.0

    def engage_kill_switch(self, reason: str) -> None:
        self._kill_switch_active = True
        self._kill_switch_reason = reason
        self._kill_switch_timestamp = datetime.utcnow()

    def reset_kill_switch(self) -> None:
        self._kill_switch_active = False
        self._kill_switch_reason = None
        self._kill_switch_timestamp = None

    @property
    def is_kill_switch_active(self) -> bool:
        return self._kill_switch_active

    def reset_daily(self, current_equity: float) -> None:
        self._daily_start_equity = current_equity
        self._daily_pnl = 0.0
        self._current_date = date.today()

    def record_trade_pnl(self, pnl: float) -> None:
        self._daily_pnl += pnl

    def _check_day_rollover(self) -> None:
        today = date.today()
        if today != self._current_date:
            self._current_date = today

    def calculate_risk_usd(
        self,
        entry_price: float,
        stop_loss: float,
        position_size_lots: float,
        symbol: str,
        get_pip_value_fn=None,
        price_to_pips_fn=None,
    ) -> float:
        """Requires get_pip_value_fn(symbol, lots) and price_to_pips_fn(symbol, distance)."""
        if get_pip_value_fn is None or price_to_pips_fn is None:
            # Fallback: rough estimate
            pip_size = 0.01 if "JPY" in symbol.upper() else 0.0001
            pv = 10.0 if "JPY" not in symbol.upper() else 1000.0 / 150.0
            sl_pips = abs(entry_price - stop_loss) / pip_size
            return sl_pips * pv * position_size_lots
        pip_value = get_pip_value_fn(symbol, position_size_lots)
        sl_pips = price_to_pips_fn(symbol, abs(entry_price - stop_loss))
        return sl_pips * pip_value

    def check(
        self,
        trade_params: Optional[TradeRiskParams] = None,
        current_equity: Optional[float] = None,
        daily_pnl: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> RiskCheckResult:
        self._check_day_rollover()
        equity = current_equity or self.starting_equity
        pnl = daily_pnl if daily_pnl is not None else self._daily_pnl
        risk_metrics = {
            "starting_equity": self.starting_equity,
            "current_equity": equity,
            "daily_start_equity": self._daily_start_equity,
            "daily_pnl": pnl,
            "daily_loss_pct": abs(pnl / self._daily_start_equity * 100) if pnl < 0 else 0,
            "total_drawdown_pct": (self.starting_equity - equity) / self.starting_equity * 100,
            "kill_switch_active": self._kill_switch_active,
        }
        if self._kill_switch_active:
            return RiskCheckResult(
                passed=False,
                rejection_reason=RiskRejectionReason.KILL_SWITCH_ACTIVE,
                rejection_message=f"KILL SWITCH ACTIVE: {self._kill_switch_reason}",
                risk_metrics=risk_metrics,
            )
        daily_loss_limit = self._daily_start_equity * (self.max_daily_loss_pct / 100)
        if pnl < 0 and abs(pnl) >= daily_loss_limit:
            return RiskCheckResult(
                passed=False,
                rejection_reason=RiskRejectionReason.DAILY_LOSS_LIMIT,
                rejection_message=f"DAILY LOSS LIMIT: ${abs(pnl):,.2f} >= {self.max_daily_loss_pct}%",
                risk_metrics=risk_metrics,
            )
        total_drawdown = self.starting_equity - equity
        max_drawdown_amount = self.starting_equity * (self.max_drawdown_pct / 100)
        if total_drawdown >= max_drawdown_amount:
            self.engage_kill_switch(f"Drawdown {total_drawdown:.2f} >= {self.max_drawdown_pct}%")
            return RiskCheckResult(
                passed=False,
                rejection_reason=RiskRejectionReason.EQUITY_DRAWDOWN,
                rejection_message="EQUITY PROTECTOR: Kill switch engaged.",
                risk_metrics=risk_metrics,
            )
        if trade_params is None and data:
            try:
                trade_params = TradeRiskParams(
                    symbol=str(data.get("symbol", "UNKNOWN")),
                    side=str(data.get("side", "buy")),
                    entry_price=float(data.get("entry", 0)),
                    stop_loss=float(data.get("sl", 0)),
                    position_size=float(data.get("size", 0)),
                    risk_amount_usd=data.get("risk_usd"),
                )
            except Exception:
                trade_params = None
        if trade_params and trade_params.entry_price > 0 and trade_params.stop_loss > 0:
            try:
                risk_usd = trade_params.risk_amount_usd
                if risk_usd is None:
                    risk_usd = self.calculate_risk_usd(
                        trade_params.entry_price,
                        trade_params.stop_loss,
                        trade_params.position_size,
                        trade_params.symbol,
                    )
                max_risk_usd = equity * (self.max_risk_per_trade_pct / 100)
                risk_metrics["trade_risk_usd"] = risk_usd
                risk_metrics["trade_risk_pct"] = (risk_usd / equity) * 100
                risk_metrics["max_risk_usd"] = max_risk_usd
                if risk_usd > max_risk_usd:
                    return RiskCheckResult(
                        passed=False,
                        rejection_reason=RiskRejectionReason.RISK_TOO_HIGH,
                        rejection_message=f"Trade risk ${risk_usd:,.2f} > {self.max_risk_per_trade_pct}% max",
                        risk_metrics=risk_metrics,
                    )
            except Exception as e:
                risk_metrics["risk_calc_error"] = str(e)
        return RiskCheckResult(passed=True, risk_metrics=risk_metrics)

    def get_status(self) -> Dict[str, Any]:
        return {
            "kill_switch_active": self._kill_switch_active,
            "kill_switch_reason": self._kill_switch_reason,
            "kill_switch_timestamp": (
                self._kill_switch_timestamp.isoformat() if self._kill_switch_timestamp else None
            ),
            "starting_equity": self.starting_equity,
            "daily_start_equity": self._daily_start_equity,
            "daily_pnl": self._daily_pnl,
            "current_date": self._current_date.isoformat(),
            "limits": {
                "max_daily_loss_pct": self.max_daily_loss_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
                "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            },
        }
