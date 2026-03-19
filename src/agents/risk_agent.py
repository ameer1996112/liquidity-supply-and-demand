"""
Risk Agent — The Shield

Enforces pre-trade hard rules using live Supabase state.

Check 1 — Daily Drawdown Kill Switch
    Sum today's closed-trade P&L (UTC).
    If total loss ≥ DAILY_DRAWDOWN_LIMIT (default -$450) → vote NO.

Check 2 — Currency Exposure Cap
    Count active/executed trades whose symbol contains either the base or
    quote currency of the incoming signal.
    If count ≥ MAX_CURRENCY_EXPOSURE (default 2) → vote NO.

Input:  symbol string (e.g. "GBPJPY")
Output: {"vote": "YES"|"NO", "reason": str}
"""

import logging
import os
from datetime import date, datetime

logger = logging.getLogger(__name__)

DAILY_DRAWDOWN_LIMIT = float(os.environ.get("DAILY_DRAWDOWN_LIMIT", "-450.0"))
MAX_CURRENCY_EXPOSURE = int(os.environ.get("MAX_CURRENCY_EXPOSURE", "2"))


class RiskAgent:
    """Enforces risk rules before a trade reaches execution."""

    def __init__(self, supabase_client=None):
        self._sb = supabase_client

    def evaluate(self, symbol: str) -> dict:
        """
        Run all hard risk checks for the incoming signal.

        Returns:
            {"vote": "YES"|"NO", "reason": str}
        """
        drawdown = self._check_drawdown()
        if drawdown["blocked"]:
            return {"vote": "NO", "reason": drawdown["reason"]}

        exposure = self._check_exposure(symbol)
        if exposure["blocked"]:
            return {"vote": "NO", "reason": exposure["reason"]}

        return {
            "vote":   "YES",
            "reason": (
                f"All clear | PnL today=${drawdown['today_pnl']:.2f} | Exposure OK"
            ),
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _check_drawdown(self) -> dict:
        if not self._sb:
            return {"blocked": False, "reason": "No DB (fail-open)", "today_pnl": 0.0}
        try:
            today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
            resp = (
                self._sb.table("trading_signals")
                .select("pnl_usd")
                .in_("status", ["CLOSED", "closed"])
                .gte("created_at", today_start)
                .execute()
            )
            today_pnl = sum(float(r.get("pnl_usd") or 0) for r in (resp.data or []))
            
            # Dynamic Limit Calculation
            env_val = os.environ.get("DAILY_DRAWDOWN_LIMIT")
            if env_val is not None and env_val != "-450.0":
                daily_limit = float(env_val)
            else:
                from config import get_settings
                s = get_settings()
                daily_limit = -(s.account_balance * (s.trinity_max_daily_loss_pct / 100.0))

            blocked = today_pnl <= daily_limit
            reason = (
                f"Daily drawdown hit: ${today_pnl:.2f} ≤ ${daily_limit:.2f}"
                if blocked else
                f"Drawdown OK: ${today_pnl:.2f} / ${abs(daily_limit):.2f} limit"
            )
            logger.info("[RISK] Drawdown: pnl=$%.2f limit=$%.2f blocked=%s", today_pnl, daily_limit, blocked)
            return {"blocked": blocked, "reason": reason, "today_pnl": today_pnl}
        except Exception as exc:
            logger.error("[RISK] Drawdown check error (fail-open): %s", exc)
            return {"blocked": False, "reason": f"Drawdown check error (fail-open): {exc}", "today_pnl": 0.0}

    def _check_exposure(self, symbol: str) -> dict:
        if not self._sb:
            return {"blocked": False, "reason": "No DB (fail-open)"}
        try:
            currencies = self._extract_currencies(symbol)
            for currency in currencies:
                resp = (
                    self._sb.table("trading_signals")
                    .select("id")
                    .in_("status", ["active", "executed"])
                    .ilike("symbol", f"%{currency}%")
                    .execute()
                )
                count = len(resp.data or [])
                if count >= MAX_CURRENCY_EXPOSURE:
                    reason = (
                        f"{currency} Exposure > {MAX_CURRENCY_EXPOSURE - 1}%: "
                        f"{count} open trades (max {MAX_CURRENCY_EXPOSURE})"
                    )
                    logger.info("[RISK] Exposure BLOCKED: %s", reason)
                    return {"blocked": True, "reason": reason}
            return {"blocked": False, "reason": "Exposure within limits"}
        except Exception as exc:
            logger.error("[RISK] Exposure check error (fail-open): %s", exc)
            return {"blocked": False, "reason": f"Exposure check error (fail-open): {exc}"}

    @staticmethod
    def _extract_currencies(symbol: str) -> list:
        """EURUSD → ['EUR', 'USD'] | GBPJPY → ['GBP', 'JPY'] | NQ → ['NQ']"""
        s = symbol.upper().replace("/", "").replace(".", "")
        if len(s) >= 6:
            return [s[:3], s[3:6]]
        return [s]
