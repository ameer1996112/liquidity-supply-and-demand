"""
Risk Engine - Prop firm capital preservation logic.
Pure domain: no DB/API calls. Used by worker and guard_rails.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_MAX_DAILY_LOSS_PCT = 4.0
DEFAULT_MAX_DRAWDOWN_PCT = 8.0
DEFAULT_MAX_RISK_PER_TRADE_PCT = 1.0
DEFAULT_STARTING_EQUITY = 10_000.0


class RiskRejectionReason(str, Enum):
    DAILY_LOSS_LIMIT = "daily_loss_limit_exceeded"
    EQUITY_DRAWDOWN = "equity_drawdown_exceeded"
    RISK_TOO_HIGH = "risk_per_trade_exceeded"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    INVALID_RISK_PARAMS = "invalid_risk_parameters"


class RiskCheckResult(BaseModel):
    passed: bool = Field(description="Whether the trade passed all risk checks")
    rejection_reason: Optional[RiskRejectionReason] = Field(default=None)
    rejection_message: Optional[str] = Field(default=None)
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


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


def calculate_max_position_size(
    payload: Dict[str, Any],
    account_balance: float,
    risk_percent: float,
) -> float:
    """
    Maximum allowed lot size from account balance and risk %.
    Pure calculation; no settings import. Returns cap (e.g. min(calculated, 5.0)).
    """
    try:
        entry = float(payload.get("entry", 0))
        sl = float(payload.get("sl", 0))
        symbol = payload.get("symbol", "UNKNOWN")
        if entry == 0 or sl == 0:
            return 1.0
        max_risk_usd = account_balance * (risk_percent / 100.0)
        sl_distance = abs(entry - sl)
        if "JPY" in symbol:
            pip_size = 0.01
            pip_value_per_lot = 1000.0
        elif "XAU" in symbol or "GOLD" in symbol:
            pip_size = 0.01
            pip_value_per_lot = 100.0
        else:
            pip_size = 0.0001
            pip_value_per_lot = 10.0
        sl_pips = sl_distance / pip_size
        if sl_pips > 0:
            max_lots = max_risk_usd / (sl_pips * pip_value_per_lot)
            return min(max_lots, 5.0)
        return 1.0
    except Exception as e:
        logger.warning(f"Max size calculation error: {e}")
        return 1.0


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
