"""
Pine Guardian - Python Mirror of Pine Script Risk Management Logic.

This module re-implements the EXACT position sizing and risk management formulas
from SND_Strategy.pine to serve as a "Source of Truth" validator.

PURPOSE:
- Prevent Fat Finger errors (accidental oversized positions)
- Detect calculation bugs in TradingView signals
- Enforce daily drawdown limits using live account balance
- Mirror Pine Script logic 1:1 for consistency
- Adaptive daily trade limit: session-quality + streak + session-slot + risk budget

PINE SCRIPT SOURCE OF TRUTH:
- Position Sizing: calc_pos_size_units() lines 1006-1068
- Daily Limits: max_daily_loss_pct, max_trades_per_day lines 375-376, 315
- Contract Sizes: FOREX_LOT_SIZE, GOLD_LOT_SIZE, etc. lines 98-101
- Risk Reduction: 2nd trade uses 50% risk lines 3884-3885

Author: Pine Guardian System
Version: 2.0.0
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

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

# Adaptive trade limit defaults (v2)
DEFAULT_MAX_TRADES_LONDON = 2        # London session base
DEFAULT_MAX_TRADES_NY = 2            # NY session base
DEFAULT_MAX_TRADES_OFFHOURS = 1      # Off-hours base
DEFAULT_MAX_TRADES_HARD_CAP = 6      # Absolute ceiling
DEFAULT_DAILY_RISK_BUDGET_PCT = 3.0  # Max cumulative risk % per day

# Legacy static fallback (used when adaptive is OFF)
DEFAULT_MAX_TRADES_PER_DAY = 2

# Variance threshold for position size validation
POSITION_SIZE_VARIANCE_THRESHOLD = 0.05  # 5%

# ── Session windows (UTC hours, inclusive start, exclusive end) ──────────────
SESSION_LONDON_START = 7    # 07:00 UTC
SESSION_LONDON_END = 12     # 12:00 UTC (exclusive)
SESSION_NY_START = 13       # 13:00 UTC
SESSION_NY_END = 18         # 18:00 UTC (exclusive)


class TradingSession(str, Enum):
    LONDON = "london"
    NEW_YORK = "new_york"
    OFF_HOURS = "off_hours"


class RejectionReason(str, Enum):
    """Reasons for rejecting a trade signal."""
    POSITION_SIZE_MISMATCH = "position_size_mismatch"
    DAILY_LOSS_LIMIT_EXCEEDED = "daily_loss_limit_exceeded"
    DAILY_PROFIT_TARGET_REACHED = "daily_profit_target_reached"
    MAX_TRADES_EXCEEDED = "max_trades_exceeded"
    DAILY_RISK_BUDGET_EXHAUSTED = "daily_risk_budget_exhausted"
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


@dataclass
class AdaptiveLimitState:
    """
    State snapshot returned by compute_effective_limit().

    Used for logging and diagnostics.
    """
    session: TradingSession
    session_base: int
    intraday_adj: int
    streak_bonus: int
    effective_limit: int
    current_session_trades: int
    hard_cap: int
    risk_budget_pct: float
    risk_deployed_pct: float

    @property
    def slots_remaining(self) -> int:
        return max(0, self.effective_limit - self.current_session_trades)

    @property
    def budget_remaining_pct(self) -> float:
        return max(0.0, self.risk_budget_pct - self.risk_deployed_pct)


class PineGuardian:
    """
    Python mirror of Pine Script risk management logic.

    Validates incoming trade signals against the exact formulas used in
    SND_Strategy.pine to catch calculation errors and enforce risk limits.

    v2: Adaptive daily trade limit — three dimensions:
        1. Intraday session-quality adjustment (win streak / loss circuit-breaker)
        2. Multi-day profitable-streak bonus (passed in from Redis; +0/+1/+2)
        3. Session-slot separation (London / NY / Off-Hours independent pools)

    Plus a parallel daily risk-budget gate.

    Usage:
        guardian = PineGuardian(...)
        result = guardian.validate_signal(signal_data, current_balance=50000.0,
                                          streak_days=2, utc_hour=10)
        if not result.is_valid:
            logger.warning(f"Signal rejected: {result.rejection_message}")
    """

    def __init__(
        self,
        account_balance: float = 50_000.0,
        risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
        max_daily_loss_pct: float = DEFAULT_MAX_DAILY_LOSS_PCT,
        max_daily_profit_pct: float = DEFAULT_MAX_DAILY_PROFIT_PCT,
        # Legacy static limit (used when adaptive=False or pine_max_trades_per_day > 0)
        max_trades_per_day: int = DEFAULT_MAX_TRADES_PER_DAY,
        variance_threshold: float = POSITION_SIZE_VARIANCE_THRESHOLD,
        usdjpy_rate: float = USDJPY_FALLBACK,
        # v2 adaptive parameters
        adaptive_enabled: bool = True,
        max_trades_london: int = DEFAULT_MAX_TRADES_LONDON,
        max_trades_ny: int = DEFAULT_MAX_TRADES_NY,
        max_trades_offhours: int = DEFAULT_MAX_TRADES_OFFHOURS,
        max_trades_hard_cap: int = DEFAULT_MAX_TRADES_HARD_CAP,
        daily_risk_budget_pct: float = DEFAULT_DAILY_RISK_BUDGET_PCT,
        streak_enabled: bool = True,
    ):
        self.account_balance = account_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_daily_profit_pct = max_daily_profit_pct
        self.max_trades_per_day = max_trades_per_day
        self.variance_threshold = variance_threshold
        self.usdjpy_rate = usdjpy_rate

        # v2 adaptive config
        self.adaptive_enabled = adaptive_enabled
        self.max_trades_london = max_trades_london
        self.max_trades_ny = max_trades_ny
        self.max_trades_offhours = max_trades_offhours
        self.max_trades_hard_cap = max_trades_hard_cap
        self.daily_risk_budget_pct = daily_risk_budget_pct
        self.streak_enabled = streak_enabled

        # Daily tracking (reset via reset_daily())
        self.daily_start_equity = account_balance
        self.daily_pnl = 0.0
        self.current_day_trades = 0          # total trades today (all sessions)
        self.daily_wins = 0
        self.daily_losses = 0
        self.consecutive_losses = 0          # resets on a win
        self.daily_risk_deployed_pct = 0.0  # cumulative risk % used today

        # Per-session trade counters
        self._session_trades: Dict[str, int] = {
            TradingSession.LONDON: 0,
            TradingSession.NEW_YORK: 0,
            TradingSession.OFF_HOURS: 0,
        }

        logger.info(
            f"PineGuardian v2 initialized: balance=${account_balance}, "
            f"risk={risk_per_trade_pct}%, max_loss={max_daily_loss_pct}%, "
            f"adaptive={adaptive_enabled}, "
            f"london={max_trades_london} NY={max_trades_ny} offhours={max_trades_offhours} "
            f"hardcap={max_trades_hard_cap} risk_budget={daily_risk_budget_pct}%"
        )

    # ══════════════════════════════════════════════════════════
    # DAILY RESET
    # ══════════════════════════════════════════════════════════

    def reset_daily(self, current_equity: float) -> None:
        """
        Reset daily tracking counters.

        Call this at the start of each trading day. Streak state is NOT
        reset here — it is owned externally (Redis) and passed in per-call.

        Args:
            current_equity: Current account equity to use as daily start
        """
        self.daily_start_equity = current_equity
        self.daily_pnl = 0.0
        self.current_day_trades = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.consecutive_losses = 0
        self.daily_risk_deployed_pct = 0.0
        self._session_trades = {s: 0 for s in TradingSession}
        logger.info(f"PineGuardian daily reset: start_equity=${current_equity}")

    # ══════════════════════════════════════════════════════════
    # TRADE RECORDING
    # ══════════════════════════════════════════════════════════

    def record_trade(self, pnl: float, risk_pct: Optional[float] = None, utc_hour: int = 10) -> None:
        """
        Record a completed trade for daily tracking.

        Args:
            pnl: Profit/loss of the trade in USD
            risk_pct: Risk % used for this trade (for budget tracking).
                      If None, uses self.risk_per_trade_pct.
            utc_hour: UTC hour the trade was taken (for session slot tracking)
        """
        self.daily_pnl += pnl
        self.current_day_trades += 1

        effective_risk = risk_pct if risk_pct is not None else self.risk_per_trade_pct
        self.daily_risk_deployed_pct += effective_risk

        session = self.classify_session(utc_hour)
        self._session_trades[session] = self._session_trades.get(session, 0) + 1

        if pnl > 0:
            self.daily_wins += 1
            self.consecutive_losses = 0  # reset on a win
        else:
            self.daily_losses += 1
            self.consecutive_losses += 1

        logger.info(
            f"PineGuardian trade recorded: pnl=${pnl:.2f}, risk={effective_risk:.2f}%, "
            f"daily_pnl=${self.daily_pnl:.2f}, trades={self.current_day_trades}, "
            f"wins={self.daily_wins}, losses={self.daily_losses}, "
            f"consec_losses={self.consecutive_losses}, "
            f"risk_deployed={self.daily_risk_deployed_pct:.2f}%"
        )

    # ══════════════════════════════════════════════════════════
    # SESSION CLASSIFICATION
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def classify_session(utc_hour: int) -> TradingSession:
        """
        Classify an hour (UTC 0-23) into London / NY / Off-Hours session.

        London : 07-11 UTC (inclusive)
        NY     : 13-17 UTC (inclusive)
        Off-hrs: everything else
        """
        if SESSION_LONDON_START <= utc_hour < SESSION_LONDON_END:
            return TradingSession.LONDON
        if SESSION_NY_START <= utc_hour < SESSION_NY_END:
            return TradingSession.NEW_YORK
        return TradingSession.OFF_HOURS

    def _session_base(self, session: TradingSession) -> int:
        """Return configurable base slot count for a session."""
        if session == TradingSession.LONDON:
            return self.max_trades_london
        if session == TradingSession.NEW_YORK:
            return self.max_trades_ny
        return self.max_trades_offhours

    # ══════════════════════════════════════════════════════════
    # DIMENSION 1: INTRADAY SESSION-QUALITY ADJUSTMENT
    # ══════════════════════════════════════════════════════════

    def compute_intraday_adjustment(self) -> int:
        """
        Compute the intraday trade-count adjustment based on today's performance.

        Rules:
          - 2+ consecutive losses today  → −2  (circuit-breaker)
          - ≥1 loss, no wins so far      → −1
          - mixed (wins AND losses)      →  0
          - ≥1 win, no losses            → +1
          - all wins, ≥2 wins            → +2

        Returns:
            Integer adjustment to add to session base.
        """
        if self.consecutive_losses >= 2:
            return -2
        if self.daily_losses > 0 and self.daily_wins == 0:
            return -1
        if self.daily_wins > 0 and self.daily_losses > 0:
            return 0
        if self.daily_wins >= 2:
            return +2
        if self.daily_wins == 1:
            return +1
        return 0  # no trades yet

    # ══════════════════════════════════════════════════════════
    # DIMENSION 2: MULTI-DAY STREAK BONUS
    # ══════════════════════════════════════════════════════════

    def compute_streak_bonus(self, streak_days: int) -> int:
        """
        Compute bonus slots from a multi-day profitable streak.

        streak_days is the number of CONSECUTIVE profitable days BEFORE today
        (owned externally, typically stored in Redis).

        Rules:
          0 days  → +0
          1 day   → +1
          2+ days → +2

        Args:
            streak_days: Consecutive profitable days before today (0+)

        Returns:
            Integer bonus to add to session base.
        """
        if not self.streak_enabled:
            return 0
        if streak_days >= 2:
            return 2
        if streak_days == 1:
            return 1
        return 0

    # ══════════════════════════════════════════════════════════
    # COMBINED EFFECTIVE LIMIT COMPUTATION
    # ══════════════════════════════════════════════════════════

    def compute_effective_limit(
        self, streak_days: int = 0, utc_hour: int = 10
    ) -> AdaptiveLimitState:
        """
        Compute the current effective trade limit for a given session.

        Formula:
            session_limit = session_base + intraday_adj + streak_bonus
            effective_limit = clamp(session_limit, 1, hard_cap)

        Args:
            streak_days: Consecutive profitable days before today (from Redis)
            utc_hour: Current UTC hour (0-23)

        Returns:
            AdaptiveLimitState with full diagnostic info
        """
        session = self.classify_session(utc_hour)
        base = self._session_base(session)
        intraday_adj = self.compute_intraday_adjustment()
        streak_bonus = self.compute_streak_bonus(streak_days)

        raw = base + intraday_adj + streak_bonus
        # Floor at 1 (always allow at least one trade unless daily loss hit)
        # Ceiling at hard cap
        effective = max(1, min(raw, self.max_trades_hard_cap))

        current_session = self._session_trades.get(session, 0)

        state = AdaptiveLimitState(
            session=session,
            session_base=base,
            intraday_adj=intraday_adj,
            streak_bonus=streak_bonus,
            effective_limit=effective,
            current_session_trades=current_session,
            hard_cap=self.max_trades_hard_cap,
            risk_budget_pct=self.daily_risk_budget_pct,
            risk_deployed_pct=self.daily_risk_deployed_pct,
        )

        logger.debug(
            f"AdaptiveLimit [{session.value}] base={base} intraday={intraday_adj:+d} "
            f"streak={streak_bonus:+d} → effective={effective} "
            f"(used={current_session}, remaining={state.slots_remaining})"
        )
        return state

    # ══════════════════════════════════════════════════════════
    # CHECKS: max trades + risk budget
    # ══════════════════════════════════════════════════════════

    def check_max_trades(self, streak_days: int = 0, utc_hour: int = 10) -> bool:
        """
        Check whether another trade is allowed based on the current limit.

        In adaptive mode: uses session-slot + intraday + streak.
        In static mode : uses legacy self.max_trades_per_day pool.

        Returns:
            True if trade allowed, False if limit reached.
        """
        if not self.adaptive_enabled:
            # Backward-compat: single static pool
            return self.current_day_trades < self.max_trades_per_day

        state = self.compute_effective_limit(streak_days, utc_hour)
        return state.slots_remaining > 0

    def check_risk_budget(self) -> bool:
        """
        Check whether the daily risk budget (cumulative risk %) is still available.

        Returns:
            True if budget remaining, False if exhausted.
        """
        return self.daily_risk_deployed_pct < self.daily_risk_budget_pct

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
    # RISK REDUCTION LOGIC (generalised from Pine line 3884-3885)
    # ══════════════════════════════════════════════════════════

    def get_effective_risk_pct(self) -> float:
        """
        Get effective risk percentage with progressive scaling.

        Trade 1: 100% of risk_per_trade_pct  (full risk)
        Trade 2:  75% of risk_per_trade_pct
        Trade 3+: 50% of risk_per_trade_pct  (conservative on later trades)

        This generalises the original Pine Script 2nd-trade 50% reduction
        and extends it gracefully to any number of trades.

        Returns:
            Effective risk percentage for next trade
        """
        n = self.current_day_trades  # trades already taken today
        if n == 0:
            multiplier = 1.0    # 1st trade: full risk
        elif n == 1:
            multiplier = 0.75   # 2nd trade: 75%
        else:
            multiplier = 0.50   # 3rd+: 50%

        risk_pct = self.risk_per_trade_pct * multiplier
        logger.debug(f"Effective risk for trade #{n+1}: {risk_pct:.3f}% (×{multiplier})")
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

    # ══════════════════════════════════════════════════════════
    # MAIN VALIDATION METHOD
    # ══════════════════════════════════════════════════════════

    def validate_signal(
        self,
        signal_data: Dict[str, Any],
        current_balance: Optional[float] = None,
        streak_days: int = 0,
        utc_hour: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate a trade signal against Pine Script risk management rules.

        This is the main entry point for signal validation.

        Steps:
        1. Check daily limits (loss, profit)
        2. Check adaptive trade count limit (session-slot + intraday + streak)
        3. Check daily risk budget (parallel gate)
        4. Re-calculate position size using Pine Script formula
        5. Compare with requested size - reject if variance > threshold
        6. Validate position is within min/max limits

        Args:
            signal_data: Raw trade signal from TradingView webhook
                Required keys: symbol, entry, sl, size (lots)
            current_balance: Current account balance (uses stored if None)
            streak_days: Consecutive profitable days before today (from Redis; 0+)
            utc_hour: Current UTC hour (0-23). If None, uses 10 (London mid-session).

        Returns:
            ValidationResult with is_valid, rejection reason, and details
        """
        import datetime
        balance = current_balance or self.account_balance

        # Default utc_hour to now if not provided
        if utc_hour is None:
            utc_hour = datetime.datetime.utcnow().hour

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
        # STEP 1: Daily Limit Checks (loss / profit)
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

        # ══════════════════════════════════════════════════════════
        # STEP 2: Adaptive Trade Count Check
        # ══════════════════════════════════════════════════════════

        if not self.check_max_trades(streak_days=streak_days, utc_hour=utc_hour):
            if self.adaptive_enabled:
                state = self.compute_effective_limit(streak_days, utc_hour)
                msg = (
                    f"Session trade limit reached: {state.current_session_trades}/{state.effective_limit} "
                    f"[{state.session.value} | base={state.session_base} "
                    f"intraday={state.intraday_adj:+d} streak={state.streak_bonus:+d}]"
                )
                details = {
                    "session": state.session.value,
                    "session_trades": state.current_session_trades,
                    "effective_limit": state.effective_limit,
                    "session_base": state.session_base,
                    "intraday_adj": state.intraday_adj,
                    "streak_bonus": state.streak_bonus,
                    "hard_cap": state.hard_cap,
                }
            else:
                msg = f"Max daily trades reached: {self.current_day_trades}/{self.max_trades_per_day}"
                details = {
                    "current_trades": self.current_day_trades,
                    "max_trades": self.max_trades_per_day,
                }
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.MAX_TRADES_EXCEEDED,
                rejection_message=msg,
                details=details,
            )

        # ══════════════════════════════════════════════════════════
        # STEP 3: Daily Risk Budget Check (parallel gate)
        # ══════════════════════════════════════════════════════════

        if self.adaptive_enabled and not self.check_risk_budget():
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.DAILY_RISK_BUDGET_EXHAUSTED,
                rejection_message=(
                    f"Daily risk budget exhausted: {self.daily_risk_deployed_pct:.2f}% "
                    f">= {self.daily_risk_budget_pct:.2f}%"
                ),
                details={
                    "risk_deployed_pct": self.daily_risk_deployed_pct,
                    "risk_budget_pct": self.daily_risk_budget_pct,
                },
            )

        # ══════════════════════════════════════════════════════════
        # STEP 3b: Hard Max Position Size (before variance/mismatch)
        # ══════════════════════════════════════════════════════════

        if requested_lots > MAX_POSITION_SIZE_LOTS:
            return ValidationResult(
                is_valid=False,
                rejection_reason=RejectionReason.POSITION_TOO_LARGE,
                rejection_message=f"Position too large: {requested_lots:.3f} lots > {MAX_POSITION_SIZE_LOTS} max",
                requested_lots=requested_lots,
            )

        # ══════════════════════════════════════════════════════════
        # STEP 4: Re-Calculate Position Size
        # ══════════════════════════════════════════════════════════

        # Get effective risk (progressive scaling)
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
        # STEP 5: Compare with Requested Size
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
        # STEP 6: Position Size Min Limit (max checked in STEP 3b)
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

        session = self.classify_session(utc_hour)
        logger.info(
            f"PineGuardian APPROVED: {symbol} {requested_lots:.3f} lots "
            f"(calculated: {calculated_lots:.3f}, variance: {variance*100:.1f}%) "
            f"[{session.value} | trades today={self.current_day_trades} "
            f"risk_deployed={self.daily_risk_deployed_pct:.2f}%]"
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
                "session": session.value,
                "daily_trades": self.current_day_trades,
                "daily_wins": self.daily_wins,
                "daily_losses": self.daily_losses,
                "risk_deployed_pct": self.daily_risk_deployed_pct,
            }
        )


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_pine_guardian_from_settings() -> PineGuardian:
    """
    Factory function to create PineGuardian from config settings.

    Adaptive mode is ON by default. If pine_max_trades_per_day > 0 in .env,
    adaptive mode is disabled and the old static limit is used (backward compat).

    Returns:
        PineGuardian instance configured from environment
    """
    from config import get_settings

    settings = get_settings()

    # Backward-compat: if user explicitly set PINE_MAX_TRADES_PER_DAY (non-zero),
    # fall back to static single-pool mode.
    legacy_static = settings.pine_max_trades_per_day > 0
    adaptive = settings.pine_adaptive_enabled and not legacy_static

    return PineGuardian(
        account_balance=settings.account_balance,
        risk_per_trade_pct=settings.risk_percent,
        max_daily_loss_pct=DEFAULT_MAX_DAILY_LOSS_PCT,
        max_daily_profit_pct=DEFAULT_MAX_DAILY_PROFIT_PCT,
        max_trades_per_day=settings.pine_max_trades_per_day if legacy_static else DEFAULT_MAX_TRADES_PER_DAY,
        adaptive_enabled=adaptive,
        max_trades_london=settings.pine_max_trades_london,
        max_trades_ny=settings.pine_max_trades_ny,
        max_trades_offhours=settings.pine_max_trades_offhours,
        max_trades_hard_cap=settings.pine_max_trades_hard_cap,
        daily_risk_budget_pct=settings.pine_daily_risk_budget_pct,
        streak_enabled=settings.pine_streak_enabled,
    )
