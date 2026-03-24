"""
Pine Streak Tracker — Redis-backed daily profitable-streak counter.

Tracks the number of consecutive profitable trading days before today.
Streak is incremented when the day ends profitably (called by worker after
day-close or by an end-of-day job). Reset on a losing day.

Redis keys:
  pine:daily_streak        → INT — current streak days (consecutive profitable days BEFORE today)
  pine:streak_last_date    → str — ISO date of the last day that was evaluated (YYYY-MM-DD)
  pine:today_trades        → JSON — {wins: N, losses: N, risk_deployed_pct: F} for today

All keys use no TTL (persistent until explicitly cleared or overwritten).
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

STREAK_KEY = "pine:daily_streak"
STREAK_DATE_KEY = "pine:streak_last_date"
TODAY_TRADES_KEY = "pine:today_trades"


# ══════════════════════════════════════════════════════════
# STREAK READ / WRITE
# ══════════════════════════════════════════════════════════

def get_streak_days(redis_client) -> int:
    """
    Read current consecutive profitable-day streak from Redis.

    Returns:
        Number of consecutive profitable days before today (0 if no streak).
    """
    try:
        val = redis_client.get(STREAK_KEY)
        return int(val) if val is not None else 0
    except Exception as e:
        logger.warning("pine_streak: get_streak_days failed: %s (returning 0)", e)
        return 0


def set_streak_days(redis_client, days: int) -> None:
    """Write streak to Redis."""
    try:
        redis_client.set(STREAK_KEY, str(days))
    except Exception as e:
        logger.warning("pine_streak: set_streak_days failed: %s", e)


def increment_streak(redis_client) -> int:
    """Increment streak by 1 (called after profitable day). Returns new value."""
    try:
        new_val = redis_client.incr(STREAK_KEY)
        return int(new_val)
    except Exception as e:
        logger.warning("pine_streak: increment_streak failed: %s", e)
        return get_streak_days(redis_client)


def reset_streak(redis_client) -> None:
    """Reset streak to 0 (called after a losing day or missed day)."""
    try:
        redis_client.set(STREAK_KEY, "0")
        logger.info("pine_streak: streak reset to 0")
    except Exception as e:
        logger.warning("pine_streak: reset_streak failed: %s", e)


# ══════════════════════════════════════════════════════════
# TODAY'S TRADE SUMMARY (intraday state)
# ══════════════════════════════════════════════════════════

def get_today_summary(redis_client) -> Tuple[int, int, float]:
    """
    Read today's win/loss/risk_deployed state from Redis.

    Returns:
        Tuple of (wins, losses, risk_deployed_pct)
    """
    try:
        raw = redis_client.get(TODAY_TRADES_KEY)
        if raw:
            data = json.loads(raw)
            return (
                int(data.get("wins", 0)),
                int(data.get("losses", 0)),
                float(data.get("risk_deployed_pct", 0.0)),
            )
    except Exception as e:
        logger.warning("pine_streak: get_today_summary failed: %s", e)
    return 0, 0, 0.0


def record_trade_result(redis_client, pnl: float, risk_pct: float) -> None:
    """
    Record a trade result for today's intraday state.

    Args:
        redis_client: Redis client
        pnl: Trade P&L in USD
        risk_pct: Risk % deployed for this trade
    """
    try:
        wins, losses, risk_deployed = get_today_summary(redis_client)
        if pnl > 0:
            wins += 1
        else:
            losses += 1
        risk_deployed += risk_pct
        data = {"wins": wins, "losses": losses, "risk_deployed_pct": risk_deployed}
        redis_client.set(TODAY_TRADES_KEY, json.dumps(data))
        logger.debug(
            "pine_streak: trade recorded — wins=%d losses=%d risk=%.2f%%",
            wins, losses, risk_deployed,
        )
    except Exception as e:
        logger.warning("pine_streak: record_trade_result failed: %s", e)


def reset_today_summary(redis_client) -> None:
    """Clear today's intraday state (call at start of new trading day)."""
    try:
        redis_client.delete(TODAY_TRADES_KEY)
        logger.info("pine_streak: today summary cleared")
    except Exception as e:
        logger.warning("pine_streak: reset_today_summary failed: %s", e)


# ══════════════════════════════════════════════════════════
# END-OF-DAY ROLLUP
# ══════════════════════════════════════════════════════════

def rollup_day(redis_client, today_str: Optional[str] = None) -> None:
    """
    Called at end of each trading day to update the streak.

    Logic:
    - If today_wins > 0 and today_losses == 0: profitable day → streak +1
    - If today_wins > 0 and today_losses > 0: mixed day → streak ±0 (neutral, keep)
    - If today_losses > 0 and today_wins == 0: losing day → reset streak
    - If no trades today: neutral (streak unchanged)

    Also marks today's date so we don't double-rollup.

    Args:
        redis_client: Redis client
        today_str: ISO date string YYYY-MM-DD (defaults to UTC today)
    """
    if today_str is None:
        today_str = date.today().isoformat()

    try:
        last_date = redis_client.get(STREAK_DATE_KEY)
        if last_date and last_date.decode() == today_str:
            logger.debug("pine_streak: rollup already done for %s — skipping", today_str)
            return
    except Exception:
        pass

    wins, losses, _ = get_today_summary(redis_client)

    if wins > 0 and losses == 0:
        new_streak = increment_streak(redis_client)
        logger.info(
            "pine_streak: profitable day (%d wins) — streak → %d", wins, new_streak
        )
    elif losses > 0 and wins == 0:
        reset_streak(redis_client)
        logger.info(
            "pine_streak: losing day (%d losses) — streak reset to 0", losses
        )
    elif wins > 0 and losses > 0:
        streak = get_streak_days(redis_client)
        logger.info(
            "pine_streak: mixed day (W%d L%d) — streak stays at %d", wins, losses, streak
        )
    else:
        logger.info("pine_streak: no trades today — streak unchanged")

    # Mark today as rolled up + clear intraday state
    try:
        redis_client.set(STREAK_DATE_KEY, today_str)
        reset_today_summary(redis_client)
    except Exception as e:
        logger.warning("pine_streak: rollup bookkeeping failed: %s", e)


# ══════════════════════════════════════════════════════════
# GUARD INTEGRATION HELPER
# ══════════════════════════════════════════════════════════

def build_pine_guardian_state(redis_client, settings) -> dict:
    """
    Build the state dict needed to call PineGuardian.validate_signal().

    Returns a dict with:
        - streak_days: int
        - wins: int
        - losses: int
        - consecutive_losses: int (approximated from today's trade order)
        - risk_deployed_pct: float
        - utc_hour: int
    """
    streak_days = get_streak_days(redis_client)
    wins, losses, risk_deployed_pct = get_today_summary(redis_client)
    utc_hour = datetime.now(timezone.utc).hour
    return {
        "streak_days": streak_days,
        "wins": wins,
        "losses": losses,
        "risk_deployed_pct": risk_deployed_pct,
        "utc_hour": utc_hour,
    }
