"""
Pine Guardian - Python Mirror of Pine Script Risk Management Logic.

This module re-implements the EXACT position sizing and risk management formulas
from SND_Strategy.pine to serve as a "Source of Truth" validator.

PURPOSE:
- Prevent Fat Finger errors (accidental oversized positions)
- Detect calculation bugs in TradingView signals
- Enforce daily drawdown limits using live account balance
- Mirror Pine Script logic 1:1 for consistency

PINE SCRIPT SOURCE OF TRUTH:
- Position Sizing: calc_pos_size_units() lines 1006-1068
- Daily Limits: max_daily_loss_pct, max_trades_per_day lines 375-376, 315
- Contract Sizes: FOREX_LOT_SIZE, GOLD_LOT_SIZE, etc. lines 98-101
- Risk Reduction: 2nd trade uses 50% risk lines 3884-3885

Author: Pine Guardian System
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Literal, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# CONTRACT SIZE CONSTANTS (Mirror of SND_Utils.pine lines 16-19)
# ══════════════════════════════════════════════════════════

FOREX_LOT_SIZE = 100_000.0    # 100,000 units per lot
GOLD_LOT_SIZE = 100.0         # 100 oz per lot
SILVER_LOT_SIZE = 5_000.0     # 5,000 oz per lot
CRYPTO_LOT_SIZE = 1.0         # 1 unit per lot
INDEX_LOT_SIZE = 1.0          # 1 contract per lot

# Fallback exchange rate for USDJPY
USDJPY_FALLBACK = 150.0

# Position size limits (from SND_Strategy.pine lines 272-273)
MIN_POSITION_SIZE_UNITS_FOREX = 1_000
MIN_POSITION_SIZE_UNITS_PRECIOUS = 1
MAX_POSITION_SIZE_LOTS = 10.0

# Risk management limits (from SND_Strategy.pine lines 375-376, 315)
DEFAULT_RISK_PER_TRADE_PCT = 0.5
DEFAULT_MAX_DAILY_LOSS_PCT = 2.0
DEFAULT_MAX_DAILY_PROFIT_PCT = 5.0
DEFAULT_MAX_TRADES_PER_DAY = 2

# Variance threshold for position size validation
POSITION_SIZE_VARIANCE_THRESHOLD = 0.05  # 5%


class RejectionReason(str, Enum):
    """Reasons for rejecting a trade signal."""
    POSITION_SIZE_MISMATCH = "position_size_mismatch"
    DAILY_LOSS_LIMIT_EXCEEDED = "daily_loss_limit_exceeded"
    DAILY_PROFIT_TARGET_REACHED = "daily_profit_target_reached"
    MAX_TRADES_EXCEEDED = "max_trades_exceeded"
    INVALID_STOP_LOSS = "invalid_stop_loss"
    INVALID_ENTRY = "invalid_entry"
    POSITION_TOO_LARGE = "position_too_large"
    POSITION_TOO_SMALL = "position_too_small"


@dataclass
class ValidationResult:
    """Result of Pine Guardian validation."""
    is_valid: bool
    rejection_reason: Optional[RejectionReason] = None
    rejection_message: Optional[str] = None
    calculated_lots: Optional[float] = None
    requested_lots: Optional[float] = None
    variance_percent: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class PineGuardian:
    """
    Python mirror of Pine Script risk management logic.

    Validates incoming trade signals against the exact formulas used in
    SND_Strategy.pine to catch calculation errors and enforce risk limits.

    Usage:
        guardian = PineGuardian(
            account_balance=50000.0,
            risk_per_trade_pct=0.5,
            max_daily_loss_pct=2.0,
            max_trades_per_day=2,
        )

        result = guardian.validate_signal(signal_data, current_balance=50000.0)
        if not result.is_valid:
            logger.warning(f"Signal rejected: {result.rejection_message}")
    """

    def __init__(
        self,
        account_balance: float = 50_000.0,
        risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
        max_daily_loss_pct: float = DEFAULT_MAX_DAILY_LOSS_PCT,
        max_daily_profit_pct: float = DEFAULT_MAX_DAILY_PROFIT_PCT,
        max_trades_per_day: int = DEFAULT_MAX_TRADES_PER_DAY,
        variance_threshold: float = POSITION_SIZE_VARIANCE_THRESHOLD,
        usdjpy_rate: float = USDJPY_FALLBACK,
    ):
        """
        Initialize Pine Guardian.

        Args:
            account_balance: Trading account balance in USD
            risk_per_trade_pct: Risk percentage per trade (0.5 = 0.5%)
            max_daily_loss_pct: Maximum daily loss percentage (2.0 = 2%)
            max_daily_profit_pct: Daily profit target percentage (5.0 = 5%)
            max_trades_per_day: Maximum trades allowed per day
            variance_threshold: Max allowed variance between calculated and requested size (0.05 = 5%)
            usdjpy_rate: Current USDJPY rate for JPY pair calculations
        """
        self.account_balance = account_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_daily_profit_pct = max_daily_profit_pct
        self.max_trades_per_day = max_trades_per_day
        self.variance_threshold = variance_threshold
        self.usdjpy_rate = usdjpy_rate

        # Daily tracking (reset externally or via reset_daily())
        self.daily_start_equity = account_balance
        self.daily_pnl = 0.0
        self.current_day_trades = 0

        logger.info(
            f"PineGuardian initialized: balance=${account_balance}, "
            f"risk={risk_per_trade_pct}%, max_loss={max_daily_loss_pct}%, "
            f"max_trades={max_trades_per_day}"
        )

    def reset_daily(self, current_equity: float) -> None:
        """
        Reset daily tracking counters.

        Call this at the start of each trading day.

        Args:
            current_equity: Current account equity to use as daily start
        """
        self.daily_start_equity = current_equity
        self.daily_pnl = 0.0
        self.current_day_trades = 0
        logger.info(f"PineGuardian daily reset: start_equity=${current_equity}")

    def record_trade(self, pnl: float) -> None:
        """
        Record a completed trade for daily tracking.

        Args:
            pnl: Profit/loss of the trade in USD
        """
        self.daily_pnl += pnl
        self.current_day_trades += 1
        logger.info(
            f"PineGuardian trade recorded: pnl=${pnl:.2f}, "
            f"daily_pnl=${self.daily_pnl:.2f}, trades={self.current_day_trades}"
        )

    # ══════════════════════════════════════════════════════════
    # SYMBOL DETECTION (Mirror of SND_Utils.pine)
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def get_pip_size(symbol: str) -> float:
        """
        Get pip size for a symbol.

        Mirrors: SND_Utils.pine get_auto_pip_size() lines 32-52

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAUUSD", "USDJPY")

        Returns:
            Pip size for the symbol
        """
        symbol_upper = symbol.upper()

        # Indices: 1 pip = 1 point
        if any(x in symbol_upper for x in ["NAS", "US100", "NDX", "SPX", "US500", "SPY", "US30", "DJI"]):
            return 1.0

        # JPY pairs: pip = 0.01
        if "JPY" in symbol_upper:
            return 0.01

        # Gold/Silver: pip = 0.01 (10c = 10 pips, $1 = 100 pips)
        if any(x in symbol_upper for x in ["XAU", "GOLD", "XAG", "SILVER"]):
            return 0.01

        # Crypto: pip = 1.0
        if any(x in symbol_upper for x in ["BTC", "ETH"]):
            return 1.0

        # Standard forex pairs: pip = 0.0001
        return 0.0001

    @staticmethod
    def get_contract_size(symbol: str) -> Tuple[float, int]:
        """
        Get contract size and minimum units for a symbol.

        Mirrors: SND_Strategy.pine validate_position_size() lines 1202-1218

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (contract_size, min_units)
        """
        symbol_upper = symbol.upper()

        if any(x in symbol_upper for x in ["XAU", "GOLD"]):
            return GOLD_LOT_SIZE, MIN_POSITION_SIZE_UNITS_PRECIOUS

        if any(x in symbol_upper for x in ["XAG", "SILVER"]):
            return SILVER_LOT_SIZE, MIN_POSITION_SIZE_UNITS_PRECIOUS

        if any(x in symbol_upper for x in ["BTC", "ETH"]):
            return CRYPTO_LOT_SIZE, MIN_POSITION_SIZE_UNITS_PRECIOUS

        if any(x in symbol_upper for x in ["NAS", "US100", "NDX", "SPX", "US500", "SPY", "US30", "DJI"]):
            return INDEX_LOT_SIZE, MIN_POSITION_SIZE_UNITS_PRECIOUS

        # Default: Forex
        return FOREX_LOT_SIZE, MIN_POSITION_SIZE_UNITS_FOREX

    @staticmethod
    def is_jpy_pair(symbol: str) -> bool:
        """Check if symbol is a JPY pair."""
        return "JPY" in symbol.upper()

    @staticmethod
    def is_usd_quote(symbol: str) -> bool:
        """Check if symbol has USD as quote currency (ends with USD)."""
        return symbol.upper().endswith("USD")

    # ══════════════════════════════════════════════════════════
    # POSITION SIZE CALCULATION (Mirror of SND_Strategy.pine)
    # ══════════════════════════════════════════════════════════

    def calc_pos_size_units(
        self,
        entry: float,
        stop: float,
        balance: float,
        risk_pct: float,
        symbol: str,
    ) -> float:
        """
        Calculate position size in UNITS.

        This is an EXACT mirror of calc_pos_size_units() from SND_Strategy.pine
        lines 1006-1068.

        Formula for USD quote pairs (XAUUSD, EURUSD):
            position_units = risk_usd / price_distance

        Formula for JPY pairs:
            position_units = (risk_usd * usdjpy_rate) / price_distance

        Formula for cross pairs:
            position_units = risk_usd / (price_distance * quote_usd_rate)

        Args:
            entry: Entry price
            stop: Stop loss price
            balance: Account balance in USD
            risk_pct: Risk percentage (0.5 = 0.5%)
            symbol: Trading symbol

        Returns:
            Position size in units
        """
        # Step 1: Calculate risk amount in USD
        risk_usd = balance * (risk_pct / 100.0)

        # Step 2: Calculate SL distance (always positive)
        sl_distance = abs(entry - stop)

        # Step 3: Minimum 2 pip distance to prevent oversized positions
        # Mirror of SND_Strategy.pine lines 1013-1021
        pip_size = self.get_pip_size(symbol)
        min_distance = pip_size * 2.0
        effective_distance = max(sl_distance, min_distance)

        # Step 4: Calculate position units based on quote currency
        if self.is_usd_quote(symbol):
            # USD quote pairs: units = risk_usd / effective_distance
            # Example XAUUSD: $50 risk / $4.56 distance = 10.96 units
            position_units = risk_usd / effective_distance

        elif self.is_jpy_pair(symbol):
            # JPY pairs: (risk_usd * usdjpy_rate) / effective_distance
            position_units = (risk_usd * self.usdjpy_rate) / effective_distance

        else:
            # Cross pairs: Need quote currency to USD rate
            # For simplicity, using entry price as proxy (imperfect but matches Pine Script behavior)
            # position_units = risk_usd / (effective_distance * quote_usd_rate)
            quote_usd_rate = 1.0  # Default fallback
            position_units = risk_usd / (effective_distance * quote_usd_rate)

        # Step 5: Round to whole units
        position_units = round(position_units)

        # Step 6: Ensure minimum valid
        if position_units <= 0:
            position_units = 1.0

        return position_units

    def calc_pos_size_lots(
        self,
        entry: float,
        stop: float,
        balance: float,
        risk_pct: float,
        symbol: str,
    ) -> float:
        """
        Calculate position size in LOTS.

        Converts units to lots using symbol-specific contract size.

        Args:
            entry: Entry price
            stop: Stop loss price
            balance: Account balance in USD
            risk_pct: Risk percentage (0.5 = 0.5%)
            symbol: Trading symbol

        Returns:
            Position size in lots (rounded to 0.001)
        """
        units = self.calc_pos_size_units(entry, stop, balance, risk_pct, symbol)
        contract_size, _ = self.get_contract_size(symbol)

        lots = units / contract_size

        # Round to 0.001 (3 decimal places)
        lots = round(lots * 1000) / 1000

        # Minimum 0.001 lots
        return max(lots, 0.001)

    # ══════════════════════════════════════════════════════════
    # RISK REDUCTION LOGIC (Mirror of SND_Strategy.pine line 3884-3885)
    # ══════════════════════════════════════════════════════════

    def get_effective_risk_pct(self) -> float:
        """
        Get effective risk percentage considering 2nd trade reduction.

        Mirrors: SND_Strategy.pine lines 3884-3885

        If current_day_trades == 1 and max_trades_per_day == 2:
            risk_pct := risk_pct * 0.5

        Returns:
            Effective risk percentage for next trade
        """
        risk_pct = self.risk_per_trade_pct

        # 2nd trade uses 50% risk when max is 2 trades/day
        if self.current_day_trades == 1 and self.max_trades_per_day == 2:
            risk_pct = risk_pct * 0.5
            logger.debug(f"2nd trade risk reduction applied: {risk_pct}%")

        return risk_pct

    # ══════════════════════════════════════════════════════════
    # DAILY LIMIT CHECKS (Mirror of SND_Strategy.pine lines 2699-2725)
    # ══════════════════════════════════════════════════════════

    def check_daily_loss_limit(self, current_equity: float) -> bool:
        """
        Check if daily loss limit has been exceeded.

        Mirrors: SND_Strategy.pine lines 2711-2718

        Args:
            current_equity: Current account equity

        Returns:
            True if within limit, False if exceeded
        """
        daily_pnl = current_equity - self.daily_start_equity
        loss_limit = self.daily_start_equity * (self.max_daily_loss_pct / 100.0)

        # Block when loss_pct >= max_loss (at 2% boundary: block)
        return daily_pnl > -loss_limit

    def check_daily_profit_target(self, current_equity: float) -> bool:
        """
        Check if daily profit target has been reached.

        Mirrors: SND_Strategy.pine lines 2719-2723

        Args:
            current_equity: Current account equity

        Returns:
            True if target not reached, False if reached
        """
        daily_pnl = current_equity - self.daily_start_equity
        profit_limit = self.daily_start_equity * (self.max_daily_profit_pct / 100.0)

        return daily_pnl < profit_limit

    def check_max_trades(self) -> bool:
        """
        Check if maximum daily trades has been reached.

        Mirrors: SND_Strategy.pine line 2725

        Returns:
            True if can trade, False if limit reached
        """
        return self.current_day_trades < self.max_trades_per_day

    # ══════════════════════════════════════════════════════════
    # MAIN VALIDATION METHOD
    # ══════════════════════════════════════════════════════════

    def validate_signal(
        self,
        signal_data: Dict[str, Any],
        current_balance: Optional[float] = None,
    ) -> ValidationResult:
        """
        Validate a trade signal against Pine Script risk management rules.

        This is the main entry point for signal validation.

        Steps:
        1. Check daily limits (loss, profit, trade count)
        2. Re-calculate position size using Pine Script formula
        3. Compare with requested size - reject if variance > threshold
        4. Validate position is within min/max limits

        Args:
            signal_data: Raw trade signal from TradingView webhook
                Required keys: symbol, entry, sl, size (lots)
            current_balance: Current account balance (uses stored if None)

        Returns:
            ValidationResult with is_valid, rejection reason, and details
        """
        balance = current_balance or self.account_balance

        # Extract signal data
        symbol = str(signal_data.get("symbol", "")).upper()
        entry = float(signal_data.get("entry", 0))
        stop_loss = float(signal_data.get("sl", 0))
        requested_lots = float(signal_data.get("size", 0))

        # Basic validation
        if not symbol:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.INVALID_ENTRY,
                rejection_message="Missing symbol in signal",
            )

        if entry <= 0:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.INVALID_ENTRY,
                rejection_message=f"Invalid entry price: {entry}",
            )

        if stop_loss <= 0:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.INVALID_STOP_LOSS,
                rejection_message=f"Invalid stop loss: {stop_loss}",
            )

        # ══════════════════════════════════════════════════════════
        # STEP 1: Daily Limit Checks
        # ══════════════════════════════════════════════════════════

        if not self.check_daily_loss_limit(balance):
            loss_pct = ((self.daily_start_equity - balance) / self.daily_start_equity) * 100
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.DAILY_LOSS_LIMIT_EXCEEDED,
                rejection_message=f"Daily loss limit exceeded: {loss_pct:.2f}% > {self.max_daily_loss_pct}%",
                details={
                    "daily_start_equity": self.daily_start_equity,
                    "current_balance": balance,
                    "loss_pct": loss_pct,
                    "max_loss_pct": self.max_daily_loss_pct,
                }
            )

        if not self.check_daily_profit_target(balance):
            profit_pct = ((balance - self.daily_start_equity) / self.daily_start_equity) * 100
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.DAILY_PROFIT_TARGET_REACHED,
                rejection_message=f"Daily profit target reached: {profit_pct:.2f}% >= {self.max_daily_profit_pct}%",
                details={
                    "daily_start_equity": self.daily_start_equity,
                    "current_balance": balance,
                    "profit_pct": profit_pct,
                    "max_profit_pct": self.max_daily_profit_pct,
                }
            )

        if not self.check_max_trades():
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.MAX_TRADES_EXCEEDED,
                rejection_message=f"Max daily trades reached: {self.current_day_trades}/{self.max_trades_per_day}",
                details={
                    "current_trades": self.current_day_trades,
                    "max_trades": self.max_trades_per_day,
                }
            )

        # ══════════════════════════════════════════════════════════
        # STEP 1b: Hard Max Position Size (before variance/mismatch)
        # ══════════════════════════════════════════════════════════

        if requested_lots > MAX_POSITION_SIZE_LOTS:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.POSITION_TOO_LARGE,
                rejection_message=f"Position too large: {requested_lots:.3f} lots > {MAX_POSITION_SIZE_LOTS} max",
                requested_lots=requested_lots,
            )

        # ══════════════════════════════════════════════════════════
        # STEP 2: Re-Calculate Position Size
        # ══════════════════════════════════════════════════════════

        # Get effective risk (may be reduced for 2nd trade)
        effective_risk_pct = self.get_effective_risk_pct()

        # Calculate expected position size using Pine Script formula
        calculated_lots = self.calc_pos_size_lots(
            entry=entry,
            stop=stop_loss,
            balance=balance,
            risk_pct=effective_risk_pct,
            symbol=symbol,
        )

        # ══════════════════════════════════════════════════════════
        # STEP 3: Compare with Requested Size
        # ══════════════════════════════════════════════════════════

        if calculated_lots > 0:
            variance = abs(requested_lots - calculated_lots) / calculated_lots
        else:
            variance = 1.0  # 100% variance if calculated is 0

        if variance > self.variance_threshold:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.POSITION_SIZE_MISMATCH,
                rejection_message=(
                    f"Position size mismatch: requested {requested_lots:.3f} lots vs "
                    f"calculated {calculated_lots:.3f} lots ({variance*100:.1f}% variance > {self.variance_threshold*100}% threshold)"
                ),
                calculated_lots=calculated_lots,
                requested_lots=requested_lots,
                variance_percent=variance * 100,
                details={
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "balance": balance,
                    "risk_pct": effective_risk_pct,
                    "symbol": symbol,
                    "pip_size": self.get_pip_size(symbol),
                    "contract_size": self.get_contract_size(symbol)[0],
                    "sl_pips": abs(entry - stop_loss) / self.get_pip_size(symbol),
                }
            )

        # ══════════════════════════════════════════════════════════
        # STEP 4: Position Size Min Limit (max checked in STEP 1b)
        # ══════════════════════════════════════════════════════════

        contract_size, min_units = self.get_contract_size(symbol)
        min_lots = min_units / contract_size

        if requested_lots < min_lots:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.POSITION_TOO_SMALL,
                rejection_message=f"Position too small: {requested_lots:.3f} lots < {min_lots:.3f} min",
                calculated_lots=calculated_lots,
                requested_lots=requested_lots,
            )

        # ══════════════════════════════════════════════════════════
        # VALID SIGNAL
        # ══════════════════════════════════════════════════════════

        logger.info(
            f"PineGuardian APPROVED: {symbol} {requested_lots:.3f} lots "
            f"(calculated: {calculated_lots:.3f}, variance: {variance*100:.1f}%)"
        )

        return ValidationResult(
            is_valid=True,
            calculated_lots=calculated_lots,
            requested_lots=requested_lots,
            variance_percent=variance * 100,
            details={
                "entry": entry,
                "stop_loss": stop_loss,
                "balance": balance,
                "risk_pct": effective_risk_pct,
                "symbol": symbol,
                "daily_trades": self.current_day_trades,
            }
        )


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_pine_guardian_from_settings() -> PineGuardian:
    """
    Factory function to create PineGuardian from config settings.

    Returns:
        PineGuardian instance configured from environment
    """
    from config import get_settings

    settings = get_settings()

    return PineGuardian(
        account_balance=settings.account_balance,
        risk_per_trade_pct=settings.risk_percent,
        max_daily_loss_pct=DEFAULT_MAX_DAILY_LOSS_PCT,
        max_daily_profit_pct=DEFAULT_MAX_DAILY_PROFIT_PCT,
        max_trades_per_day=DEFAULT_MAX_TRADES_PER_DAY,
    )
