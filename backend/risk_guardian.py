"""
Risk Guardian - The Internal Auditor for Prop Firm Capital Preservation.

This module implements the "Funded Account Guardian" risk management layer
that rejects trades BEFORE they happen, protecting capital above all else.

DOCTRINE:
1. Capital Preservation > Profit (Rule #1 of Prop Firms)
2. No single trade should blow the account
3. Self-healing, self-cleaning operation

RULES ENFORCED:
1. DAILY LOSS LIMIT: If daily loss > MAX_DAILY_LOSS (4%), HARD REJECT all signals
2. EQUITY PROTECTOR: If total drawdown > 8%, engage "Kill Switch" (disable worker)
3. ANTI-GAMBLING: Reject any trade where risk_amount > 1% of equity

Author: Trinity Engine v2.0
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# CONFIGURATION CONSTANTS (Prop Firm Standards)
# ══════════════════════════════════════════════════════════

DEFAULT_MAX_DAILY_LOSS_PCT = 4.0       # 4% daily loss = account freeze
DEFAULT_MAX_DRAWDOWN_PCT = 8.0          # 8% total drawdown = kill switch
DEFAULT_MAX_RISK_PER_TRADE_PCT = 1.0    # Max 1% risk per trade (anti-gambling)
DEFAULT_STARTING_EQUITY = 10_000.0      # Default funded account size


class RiskRejectionReason(str, Enum):
    """Reasons for rejecting a trade based on risk rules."""
    DAILY_LOSS_LIMIT = "daily_loss_limit_exceeded"
    EQUITY_DRAWDOWN = "equity_drawdown_exceeded"
    RISK_TOO_HIGH = "risk_per_trade_exceeded"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    INVALID_RISK_PARAMS = "invalid_risk_parameters"


class RiskCheckResult(BaseModel):
    """Result of a risk check from the Risk Guardian."""
    passed: bool = Field(description="Whether the trade passed all risk checks")
    rejection_reason: Optional[RiskRejectionReason] = Field(
        default=None, description="Reason for rejection if passed=False"
    )
    rejection_message: Optional[str] = Field(
        default=None, description="Human-readable rejection message"
    )
    risk_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Current risk metrics for logging"
    )

    class Config:
        use_enum_values = True


class TradeRiskParams(BaseModel):
    """Risk parameters extracted from a trade signal."""
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trade direction (buy/sell)")
    entry_price: float = Field(gt=0, description="Entry price")
    stop_loss: float = Field(gt=0, description="Stop loss price")
    position_size: float = Field(gt=0, description="Position size in lots")
    risk_amount_usd: Optional[float] = Field(
        default=None, description="Pre-calculated risk in USD (if provided)"
    )

    @property
    def calculated_risk_pips(self) -> float:
        """Calculate risk in pips based on entry and stop loss."""
        return abs(self.entry_price - self.stop_loss)


class RiskGuardian:
    """
    The Internal Auditor - Rejects trades before they happen.

    Implements prop firm risk management rules to protect funded accounts
    from catastrophic losses and rule violations.

    Usage:
        guardian = RiskGuardian(
            starting_equity=100_000,
            max_daily_loss_pct=4.0,
            max_drawdown_pct=8.0,
            max_risk_per_trade_pct=1.0,
        )

        result = guardian.check(trade_params, current_equity, daily_pnl)
        if not result.passed:
            logger.warning(f"Trade rejected: {result.rejection_message}")
    """

    def __init__(
        self,
        starting_equity: float = DEFAULT_STARTING_EQUITY,
        max_daily_loss_pct: float = DEFAULT_MAX_DAILY_LOSS_PCT,
        max_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN_PCT,
        max_risk_per_trade_pct: float = DEFAULT_MAX_RISK_PER_TRADE_PCT,
    ):
        """
        Initialize Risk Guardian.

        Args:
            starting_equity: Initial funded account balance in USD
            max_daily_loss_pct: Maximum daily loss as percentage (4.0 = 4%)
            max_drawdown_pct: Maximum total drawdown percentage (8.0 = 8%)
            max_risk_per_trade_pct: Maximum risk per trade as percentage (1.0 = 1%)
        """
        self.starting_equity = starting_equity
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_risk_per_trade_pct = max_risk_per_trade_pct

        # Kill switch state
        self._kill_switch_active = False
        self._kill_switch_reason: Optional[str] = None
        self._kill_switch_timestamp: Optional[datetime] = None

        # Daily tracking
        self._daily_start_equity = starting_equity
        self._current_date = date.today()
        self._daily_pnl = 0.0

        logger.info(
            f"RiskGuardian initialized: equity=${starting_equity:,.2f}, "
            f"max_daily_loss={max_daily_loss_pct}%, max_drawdown={max_drawdown_pct}%, "
            f"max_risk_per_trade={max_risk_per_trade_pct}%"
        )

    # ══════════════════════════════════════════════════════════
    # KILL SWITCH MANAGEMENT
    # ══════════════════════════════════════════════════════════

    def engage_kill_switch(self, reason: str) -> None:
        """
        Engage the kill switch - disable all trading.

        This is the nuclear option for capital preservation.
        Once engaged, ALL trades are rejected until manually reset.

        Args:
            reason: Reason for engaging kill switch
        """
        self._kill_switch_active = True
        self._kill_switch_reason = reason
        self._kill_switch_timestamp = datetime.utcnow()

        logger.critical(
            f"KILL SWITCH ENGAGED: {reason} at {self._kill_switch_timestamp.isoformat()}"
        )

    def reset_kill_switch(self) -> None:
        """
        Reset the kill switch - re-enable trading.

        Should only be called after manual review and risk assessment.
        """
        if self._kill_switch_active:
            logger.warning(
                f"KILL SWITCH RESET: Was engaged at {self._kill_switch_timestamp} "
                f"for reason: {self._kill_switch_reason}"
            )
            self._kill_switch_active = False
            self._kill_switch_reason = None
            self._kill_switch_timestamp = None

    @property
    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is currently active."""
        return self._kill_switch_active

    # ══════════════════════════════════════════════════════════
    # DAILY TRACKING
    # ══════════════════════════════════════════════════════════

    def reset_daily(self, current_equity: float) -> None:
        """
        Reset daily tracking at start of trading day.

        Args:
            current_equity: Current account equity to use as daily start
        """
        self._daily_start_equity = current_equity
        self._daily_pnl = 0.0
        self._current_date = date.today()

        logger.info(f"RiskGuardian daily reset: start_equity=${current_equity:,.2f}")

    def record_trade_pnl(self, pnl: float) -> None:
        """
        Record a completed trade's P&L.

        Args:
            pnl: Trade profit/loss in USD
        """
        self._daily_pnl += pnl
        logger.info(f"RiskGuardian P&L recorded: ${pnl:,.2f}, daily_pnl=${self._daily_pnl:,.2f}")

    def _check_day_rollover(self) -> None:
        """Check if we've rolled into a new trading day."""
        today = date.today()
        if today != self._current_date:
            logger.info(f"New trading day detected: {today}")
            # Note: Don't reset here - let external caller manage equity updates
            self._current_date = today

    # ══════════════════════════════════════════════════════════
    # RISK CALCULATION HELPERS
    # ══════════════════════════════════════════════════════════

    def calculate_risk_usd(
        self,
        entry_price: float,
        stop_loss: float,
        position_size_lots: float,
        symbol: str,
    ) -> float:
        """
        Calculate risk in USD for a trade.

        Uses symbol-specific pip values to calculate exact risk.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            position_size_lots: Position size in lots
            symbol: Trading symbol

        Returns:
            Risk amount in USD
        """
        from backend.market_adapter import MarketAdapter

        adapter = MarketAdapter()
        pip_value = adapter.get_pip_value(symbol, position_size_lots)
        sl_pips = adapter.price_to_pips(symbol, abs(entry_price - stop_loss))

        return sl_pips * pip_value

    # ══════════════════════════════════════════════════════════
    # MAIN CHECK METHOD
    # ══════════════════════════════════════════════════════════

    def check(
        self,
        trade_params: Optional[TradeRiskParams] = None,
        current_equity: Optional[float] = None,
        daily_pnl: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> RiskCheckResult:
        """
        Run all risk checks for a trade signal.

        Checks performed (in order):
        1. Kill Switch: If active, reject immediately
        2. Daily Loss Limit: If daily loss > 4%, hard reject
        3. Equity Protector: If drawdown > 8%, engage kill switch
        4. Anti-Gambling: If trade risk > 1% equity, reject

        Args:
            trade_params: Parsed trade parameters (or extract from data)
            current_equity: Current account equity in USD
            daily_pnl: Today's P&L in USD (negative = loss)
            data: Raw trade data dict (used if trade_params not provided)

        Returns:
            RiskCheckResult with pass/fail status and details
        """
        self._check_day_rollover()

        # Use provided values or defaults
        equity = current_equity or self.starting_equity
        pnl = daily_pnl if daily_pnl is not None else self._daily_pnl

        # Build risk metrics for logging
        risk_metrics = {
            "starting_equity": self.starting_equity,
            "current_equity": equity,
            "daily_start_equity": self._daily_start_equity,
            "daily_pnl": pnl,
            "daily_loss_pct": abs(pnl / self._daily_start_equity * 100) if pnl < 0 else 0,
            "total_drawdown_pct": (self.starting_equity - equity) / self.starting_equity * 100,
            "kill_switch_active": self._kill_switch_active,
        }

        # ══════════════════════════════════════════════════════════
        # CHECK 1: Kill Switch
        # ══════════════════════════════════════════════════════════

        if self._kill_switch_active:
            return RiskCheckResult(
                passed=False,
                rejection_reason=RiskRejectionReason.KILL_SWITCH_ACTIVE,
                rejection_message=(
                    f"KILL SWITCH ACTIVE since {self._kill_switch_timestamp}: "
                    f"{self._kill_switch_reason}"
                ),
                risk_metrics=risk_metrics,
            )

        # ══════════════════════════════════════════════════════════
        # CHECK 2: Daily Loss Limit (4%)
        # ══════════════════════════════════════════════════════════

        daily_loss_limit = self._daily_start_equity * (self.max_daily_loss_pct / 100)

        if pnl < 0 and abs(pnl) >= daily_loss_limit:
            return RiskCheckResult(
                passed=False,
                rejection_reason=RiskRejectionReason.DAILY_LOSS_LIMIT,
                rejection_message=(
                    f"DAILY LOSS LIMIT: Loss ${abs(pnl):,.2f} >= {self.max_daily_loss_pct}% "
                    f"(${daily_loss_limit:,.2f}). ALL TRADES BLOCKED until next day."
                ),
                risk_metrics=risk_metrics,
            )

        # ══════════════════════════════════════════════════════════
        # CHECK 3: Equity Protector (8% Drawdown -> Kill Switch)
        # ══════════════════════════════════════════════════════════

        total_drawdown = self.starting_equity - equity
        drawdown_pct = (total_drawdown / self.starting_equity) * 100
        max_drawdown_amount = self.starting_equity * (self.max_drawdown_pct / 100)

        if total_drawdown >= max_drawdown_amount:
            # ENGAGE KILL SWITCH
            self.engage_kill_switch(
                f"Total drawdown {drawdown_pct:.2f}% (${total_drawdown:,.2f}) "
                f"exceeds {self.max_drawdown_pct}% limit"
            )

            return RiskCheckResult(
                passed=False,
                rejection_reason=RiskRejectionReason.EQUITY_DRAWDOWN,
                rejection_message=(
                    f"EQUITY PROTECTOR: Drawdown {drawdown_pct:.2f}% >= {self.max_drawdown_pct}%. "
                    f"KILL SWITCH ENGAGED. Manual reset required."
                ),
                risk_metrics=risk_metrics,
            )

        # ══════════════════════════════════════════════════════════
        # CHECK 4: Anti-Gambling (Max 1% Risk Per Trade)
        # ══════════════════════════════════════════════════════════

        # Extract trade parameters if not provided
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
            except Exception as e:
                logger.warning(f"Failed to parse trade params: {e}")
                trade_params = None

        if trade_params and trade_params.entry_price > 0 and trade_params.stop_loss > 0:
            # Calculate risk for this trade
            try:
                risk_usd = trade_params.risk_amount_usd
                if risk_usd is None:
                    risk_usd = self.calculate_risk_usd(
                        trade_params.entry_price,
                        trade_params.stop_loss,
                        trade_params.position_size,
                        trade_params.symbol,
                    )

                risk_pct = (risk_usd / equity) * 100
                max_risk_usd = equity * (self.max_risk_per_trade_pct / 100)

                risk_metrics["trade_risk_usd"] = risk_usd
                risk_metrics["trade_risk_pct"] = risk_pct
                risk_metrics["max_risk_usd"] = max_risk_usd

                if risk_usd > max_risk_usd:
                    return RiskCheckResult(
                        passed=False,
                        rejection_reason=RiskRejectionReason.RISK_TOO_HIGH,
                        rejection_message=(
                            f"ANTI-GAMBLING: Trade risk ${risk_usd:,.2f} ({risk_pct:.2f}%) "
                            f"> {self.max_risk_per_trade_pct}% max (${max_risk_usd:,.2f})"
                        ),
                        risk_metrics=risk_metrics,
                    )

            except Exception as e:
                logger.warning(f"Risk calculation error (allowing trade): {e}")
                risk_metrics["risk_calc_error"] = str(e)

        # ══════════════════════════════════════════════════════════
        # ALL CHECKS PASSED
        # ══════════════════════════════════════════════════════════

        logger.info(
            f"RiskGuardian PASSED: equity=${equity:,.2f}, "
            f"daily_pnl=${pnl:,.2f}, drawdown={drawdown_pct:.2f}%"
        )

        return RiskCheckResult(passed=True, risk_metrics=risk_metrics)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current Risk Guardian status for monitoring.

        Returns:
            Status dictionary with all risk metrics
        """
        return {
            "kill_switch_active": self._kill_switch_active,
            "kill_switch_reason": self._kill_switch_reason,
            "kill_switch_timestamp": (
                self._kill_switch_timestamp.isoformat()
                if self._kill_switch_timestamp else None
            ),
            "starting_equity": self.starting_equity,
            "daily_start_equity": self._daily_start_equity,
            "daily_pnl": self._daily_pnl,
            "current_date": self._current_date.isoformat(),
            "limits": {
                "max_daily_loss_pct": self.max_daily_loss_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
                "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            }
        }


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_risk_guardian_from_settings() -> RiskGuardian:
    """
    Factory function to create RiskGuardian from config settings.

    Returns:
        RiskGuardian instance configured from environment
    """
    from backend.config import get_settings

    settings = get_settings()

    # Get Trinity Engine settings (with fallbacks to defaults)
    max_daily_loss = getattr(settings, "trinity_max_daily_loss_pct", DEFAULT_MAX_DAILY_LOSS_PCT)
    max_drawdown = getattr(settings, "trinity_max_drawdown_pct", DEFAULT_MAX_DRAWDOWN_PCT)
    max_risk_per_trade = getattr(settings, "trinity_max_risk_per_trade_pct", DEFAULT_MAX_RISK_PER_TRADE_PCT)

    return RiskGuardian(
        starting_equity=settings.account_balance,
        max_daily_loss_pct=max_daily_loss,
        max_drawdown_pct=max_drawdown,
        max_risk_per_trade_pct=max_risk_per_trade,
    )
