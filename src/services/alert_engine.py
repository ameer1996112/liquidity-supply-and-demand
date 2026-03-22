"""AlertEngine -- periodic evaluation of alert rules, creates trading_alerts."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ALERTS_TABLE_MISSING_MSG = "Could not find the table"
_PGRST205 = "PGRST205"


def _is_table_missing(exc: BaseException) -> bool:
    """True if the exception indicates alert_rules or trading_alerts table is missing."""
    msg = str(exc)
    if _ALERTS_TABLE_MISSING_MSG in msg or _PGRST205 in msg:
        return True
    if getattr(exc, "args", None) and len(exc.args) > 0:
        first = exc.args[0]
        if isinstance(first, dict) and (
            first.get("code") == _PGRST205
            or _ALERTS_TABLE_MISSING_MSG in str(first.get("message", ""))
        ):
            return True
        if _ALERTS_TABLE_MISSING_MSG in str(first) or _PGRST205 in str(first):
            return True
    return False


class AlertEngine:
    """Evaluates alert rules and inserts alerts into trading_alerts table."""

    def __init__(self, supabase_client, alert_service=None) -> None:
        self.supabase = supabase_client
        self._alert_service = alert_service  # Optional AlertService for Discord/Telegram fanout

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
            if _is_table_missing(exc):
                logger.debug(
                    "AlertEngine: alert_rules table not found (run migrations/005_alert_rules.sql): %s",
                    exc,
                )
            else:
                logger.error("AlertEngine: failed to fetch rules: %s", exc)
            return

        for rule in rules:
            try:
                rule_type = rule.get("rule_type", "")
                condition = rule.get("condition", {})
                severity = rule.get("severity", "warning")
                cooldown_minutes = int(rule.get("cooldown_minutes", 60))

                handler = {
                    "consecutive_losses": self._check_consecutive_losses,
                    "drawdown_pct": self._check_drawdown_threshold,
                    "dlq_count": self._check_dlq_spike,
                    "position_age_hours": self._check_position_age,
                }.get(rule_type)

                if handler:
                    handler(condition, severity, cooldown_minutes)
            except Exception as exc:
                logger.error("AlertEngine: rule %s failed: %s", rule.get("id"), exc)

        # Cleanup resolved position_age alerts
        self._cleanup_resolved_alerts()

    # ── Alert creation with deduplication ────────────────────

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        signal_id: Optional[int] = None,
        dedupe_minutes: int = 60,
    ) -> None:
        """Insert alert into trading_alerts with deduplication and optional AlertService fanout."""
        # Delegate to AlertService if available (handles Discord/Telegram fanout)
        if self._alert_service is not None:
            try:
                self._alert_service.create_alert(
                    alert_type=alert_type,
                    severity=severity,
                    title=title,
                    message=message,
                    metadata=metadata,
                    signal_id=signal_id,
                    dedupe_minutes=dedupe_minutes,
                )
            except Exception as exc:
                logger.error("AlertEngine: AlertService.create_alert failed: %s", exc)
            return

        # Fallback: direct insert with deduplication (no external notifications)
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=dedupe_minutes)).isoformat()
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
            if _is_table_missing(exc):
                logger.debug(
                    "AlertEngine: trading_alerts table not found (run migrations/004_trading_alerts.sql): %s",
                    exc,
                )
            else:
                logger.error("AlertEngine: failed to create alert: %s", exc)

    def _cleanup_resolved_alerts(self) -> None:
        """
        Auto-acknowledges alerts when their condition is no longer true
        (e.g. 'position_age' alerts when the corresponding trade is closed).
        """
        try:
            # 1. Fetch unacknowledged position_age alerts
            resp = (
                self.supabase.table("trading_alerts")
                .select("id, signal_id")
                .eq("alert_type", "position_age")
                .is_("acknowledged_at", "null")
                .execute()
            )
            alerts = resp.data or []
            if not alerts:
                return

            # Note: filtering out alerts without a signal_id
            signal_ids = [a["signal_id"] for a in alerts if a.get("signal_id")]
            if not signal_ids:
                return

            # 2. Check the status of these signals
            signals_resp = (
                self.supabase.table("trading_signals")
                .select("id, status")
                .in_("id", signal_ids)
                .execute()
            )
            signals = signals_resp.data or []
            closed_signal_ids = {s["id"] for s in signals if s.get("status") in ("closed", "rejected", "execution_failed", "filtered")}

            # 3. Mark the corresponding alerts as acknowledged
            alerts_to_close = [a["id"] for a in alerts if a.get("signal_id") in closed_signal_ids]
            
            if alerts_to_close:
                self.supabase.table("trading_alerts").update(
                    {"acknowledged_at": datetime.now(timezone.utc).isoformat()}
                ).in_("id", alerts_to_close).execute()
                
                logger.info(f"Auto-resolved {len(alerts_to_close)} position_age alerts because trades are closed.")
                
        except Exception as exc:
            if _is_table_missing(exc):
                return
            logger.error("AlertEngine: failed to cleanup resolved alerts: %s", exc)

    # ── Rule checks ──────────────────────────────────────────

    def _check_consecutive_losses(self, condition: dict, severity: str, cooldown_minutes: int = 60) -> None:
        threshold = int(condition.get("threshold", 3))
        run_mode = condition.get("run_mode", "LIVE")  # Default to LIVE only
        # Only look at trades from the last N days (default 7) to avoid
        # triggering on historical losses when markets are closed (weekends/holidays).
        lookback_days = int(condition.get("lookback_days", 7))
        lookback_cutoff = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
        ).isoformat()

        query = (
            self.supabase.table("trading_signals")
            .select("pnl_usd, pnl, outcome, run_mode, closed_at, created_at")
            .in_("status", ["CLOSED", "closed"])
            .gte("created_at", lookback_cutoff)
            .order("created_at", desc=True)
            .limit(threshold + 5)  # Fetch extra to account for filtering
        )

        # Filter by run_mode if specified
        if run_mode:
            query = query.eq("run_mode", run_mode.upper())

        resp = query.execute()
        trades = resp.data or []

        consecutive = 0
        for t in trades:
            # Use pnl_usd or pnl as fallback
            pnl = float(t.get("pnl_usd") or t.get("pnl") or 0)
            outcome = (t.get("outcome") or "").lower()

            # Count as loss if PnL < 0 OR outcome explicitly marked as "loss"
            if pnl < 0 or outcome == "loss":
                consecutive += 1
                if consecutive >= threshold:
                    break  # Stop counting once threshold reached
            else:
                break  # Stop on first win

        if consecutive >= threshold:
            mode_label = f" ({run_mode})" if run_mode else ""
            self._create_alert(
                "consecutive_losses",
                severity,
                f"{consecutive} Consecutive Losses{mode_label}",
                f"Last {consecutive} closed {run_mode or 'all'} trades were losses. Consider pausing.",
                {"consecutive_count": consecutive, "run_mode": run_mode},
                dedupe_minutes=cooldown_minutes,
            )


    def _check_drawdown_threshold(self, condition: dict, severity: str, cooldown_minutes: int = 60) -> None:
        from config import get_settings

        s = get_settings()
        threshold = float(condition.get("threshold", 6))
        run_mode = condition.get("run_mode", "LIVE")  # Default to LIVE only

        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        query = (
            self.supabase.table("trading_signals")
            .select("pnl_usd, pnl")
            .in_("status", ["CLOSED", "closed"])
            .gte("created_at", today_start)
        )

        # Filter by run_mode if specified
        if run_mode:
            query = query.eq("run_mode", run_mode.upper())

        resp = query.execute()
        daily_pnl = sum(float(t.get("pnl_usd") or t.get("pnl") or 0) for t in (resp.data or []))

        if s.account_balance > 0 and daily_pnl < 0:
            drawdown_pct = abs(daily_pnl / s.account_balance * 100)
            if drawdown_pct >= threshold:
                mode_label = f" ({run_mode})" if run_mode else ""
                self._create_alert(
                    "drawdown_breach",
                    severity,
                    f"Drawdown {drawdown_pct:.1f}% Exceeded{mode_label}",
                    f"Daily {run_mode or 'all'} drawdown {drawdown_pct:.1f}% >= {threshold}% limit.",
                    {"drawdown_pct": round(drawdown_pct, 2), "daily_pnl": round(daily_pnl, 2), "run_mode": run_mode},
                    dedupe_minutes=cooldown_minutes,
                )

    def _check_dlq_spike(self, condition: dict, severity: str, cooldown_minutes: int = 60) -> None:
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
                    dedupe_minutes=cooldown_minutes,
                )
        except Exception:
            pass

    def _check_position_age(self, condition: dict, severity: str, cooldown_minutes: int = 120) -> None:
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
                dedupe_minutes=cooldown_minutes,
            )
