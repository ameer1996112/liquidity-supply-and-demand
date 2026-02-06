"""AlertEngine -- periodic evaluation of alert rules, creates trading_alerts."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AlertEngine:
    """Evaluates alert rules and inserts alerts into trading_alerts table."""

    def __init__(self, supabase_client) -> None:
        self.supabase = supabase_client

    def evaluate_all(self) -> None:
        """Run all enabled alert rules."""
        if not self.supabase:
            return

        try:
            rules_resp = (
                self.supabase.table("alert_rules")
                .select("*")
                .eq("enabled", True)
                .execute()
            )
            rules = rules_resp.data or []
        except Exception as exc:
            logger.error("AlertEngine: failed to fetch rules: %s", exc)
            return

        for rule in rules:
            try:
                rule_type = rule.get("rule_type", "")
                condition = rule.get("condition", {})
                severity = rule.get("severity", "warning")

                handler = {
                    "consecutive_losses": self._check_consecutive_losses,
                    "drawdown_pct": self._check_drawdown_threshold,
                    "dlq_count": self._check_dlq_spike,
                    "position_age_hours": self._check_position_age,
                }.get(rule_type)

                if handler:
                    handler(condition, severity)
            except Exception as exc:
                logger.error("AlertEngine: rule %s failed: %s", rule.get("id"), exc)

    # ── Alert creation with deduplication ────────────────────

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        signal_id: Optional[int] = None,
    ) -> None:
        """Insert alert into trading_alerts. Deduplicates by checking last 5 minutes."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            existing = (
                self.supabase.table("trading_alerts")
                .select("id")
                .eq("alert_type", alert_type)
                .gte("created_at", cutoff)
                .limit(1)
                .execute()
            )
            if existing.data:
                return  # Skip duplicate

            row: Dict[str, Any] = {
                "alert_type": alert_type,
                "severity": severity,
                "title": title,
                "message": message,
                "metadata": metadata or {},
            }
            if signal_id is not None:
                row["signal_id"] = signal_id

            self.supabase.table("trading_alerts").insert(row).execute()
            logger.info("Alert created: [%s] %s", severity, title)
        except Exception as exc:
            logger.error("AlertEngine: failed to create alert: %s", exc)

    # ── Rule checks ──────────────────────────────────────────

    def _check_consecutive_losses(self, condition: dict, severity: str) -> None:
        threshold = int(condition.get("threshold", 3))

        resp = (
            self.supabase.table("trading_signals")
            .select("pnl_usd, outcome")
            .eq("status", "closed")
            .order("created_at", desc=True)
            .limit(threshold + 2)
            .execute()
        )
        trades = resp.data or []

        consecutive = 0
        for t in trades:
            pnl = float(t.get("pnl_usd") or 0)
            outcome = (t.get("outcome") or "").lower()
            if pnl < 0 or outcome == "loss":
                consecutive += 1
            else:
                break

        if consecutive >= threshold:
            self._create_alert(
                "consecutive_losses",
                severity,
                f"{consecutive} Consecutive Losses",
                f"Last {consecutive} closed trades were losses. Consider pausing.",
                {"consecutive_count": consecutive},
            )

    def _check_drawdown_threshold(self, condition: dict, severity: str) -> None:
        from config import get_settings

        s = get_settings()
        threshold = float(condition.get("threshold", 6))

        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        resp = (
            self.supabase.table("trading_signals")
            .select("pnl_usd")
            .eq("status", "closed")
            .gte("created_at", today_start)
            .execute()
        )
        daily_pnl = sum(float(t.get("pnl_usd") or 0) for t in (resp.data or []))

        if s.account_balance > 0 and daily_pnl < 0:
            drawdown_pct = abs(daily_pnl / s.account_balance * 100)
            if drawdown_pct >= threshold:
                self._create_alert(
                    "drawdown_breach",
                    severity,
                    f"Drawdown {drawdown_pct:.1f}% Exceeded Threshold",
                    f"Daily drawdown {drawdown_pct:.1f}% >= {threshold}% limit.",
                    {"drawdown_pct": round(drawdown_pct, 2), "daily_pnl": round(daily_pnl, 2)},
                )

    def _check_dlq_spike(self, condition: dict, severity: str) -> None:
        threshold = int(condition.get("threshold", 1))
        try:
            from src.adapters.redis_queue import get_redis, DEAD_LETTER_QUEUE

            r = get_redis()
            dlq_count = r.llen(DEAD_LETTER_QUEUE)
            if dlq_count >= threshold:
                self._create_alert(
                    "dlq_spike",
                    severity,
                    f"{dlq_count} Dead Letters in Queue",
                    f"DLQ has {dlq_count} failed items. Check for processing errors.",
                    {"dlq_count": dlq_count},
                )
        except Exception:
            pass

    def _check_position_age(self, condition: dict, severity: str) -> None:
        threshold_hours = int(condition.get("threshold", 24))
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=threshold_hours)).isoformat()

        resp = (
            self.supabase.table("trading_signals")
            .select("id, symbol, created_at")
            .in_("status", ["active", "executed"])
            .lte("created_at", cutoff)
            .execute()
        )
        for trade in resp.data or []:
            self._create_alert(
                "position_age",
                severity,
                f"{trade['symbol']} Open > {threshold_hours}h",
                f"Trade #{trade['id']} ({trade['symbol']}) has been open for over {threshold_hours} hours.",
                {"signal_id": trade["id"], "symbol": trade["symbol"]},
                signal_id=trade["id"],
            )
