"""
src/core/safety.py — Global Trade Safety Guards
================================================
All global-scope guards for the trade pipeline live here.
Guard functions return None on PASS, or a string rejection reason on BLOCK.

FAIL-CLOSE POLICY (BUG-02, BUG-03 fixes):
  Every guard that cannot validate a LIVE trade due to missing data REJECTS it.
  Only PAPER/DRY_RUN trades are allowed through when data is absent.

Guards exported:
  - check_env_kill_switch(s)              → str | None   [BUG-05 fix]
  - check_size_guard(payload, s, symbol)  → str | None
  - check_max_lot_guard(payload, s)       → str | None
  - check_flip_timing(payload)            → str | None   [BUG-02 fix]
  - check_futures_entry_model(payload)    → str | None   [BUG-03 fix]
  - run_global_guards(payload, s)         → str | None   (runs all in order)
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("trinity.worker.safety")

# ─────────────────────────────────────────────────────────────────────────────
# Futures symbols — Mangoe rules apply (BOC / Dir Close preferred)
# ─────────────────────────────────────────────────────────────────────────────
_FUTURES_SYMBOLS = frozenset(
    {"CL", "NQ", "GC", "ES", "YM", "RTY", "XAUUSD", "XAU", "GOLD", "USOIL", "UKOIL"}
)


def _is_futures_symbol(symbol: str) -> bool:
    """Return True when the symbol follows Mangoe Futures rules."""
    if not symbol:
        return False
    u = symbol.upper().strip()
    if u in _FUTURES_SYMBOLS:
        return True
    for prefix in ("CL", "NQ", "GC", "ES", "YM", "RTY", "XAU"):
        if u.startswith(prefix) or u.startswith(prefix + ".") or u.startswith(prefix + " "):
            return True
    if "XAU" in u or "GOLD" in u:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# BUG-05 FIX: ENV Kill-Switch — must be the very first guard called
# ─────────────────────────────────────────────────────────────────────────────
def check_env_kill_switch(s) -> Optional[str]:
    """
    Check the ENV-level trading kill-switch.

    This is the cheapest, fastest guard — zero I/O, zero DB calls.
    Must be called as the FIRST guard in process_trade before any other work.

    Returns:
        None if trading is allowed, rejection string if kill-switch is active.
    """
    if getattr(s, "trading_kill_switch", False):
        return "Trading kill-switch is ON (env)"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Size Guard
# ─────────────────────────────────────────────────────────────────────────────
def check_size_guard(
    payload: Dict[str, Any],
    s,
    symbol: str,
) -> Optional[str]:
    """
    Validate that the position size is positive and non-zero.

    Provides a detailed diagnostic of WHY the size is zero (SL too wide,
    missing prices, etc.) to help operators fix Pine Script inputs quickly.

    Returns:
        None if size is valid, rejection string otherwise.
    """
    size = payload.get("size")
    if isinstance(size, (int, float)) and float(size) > 0:
        return None  # PASS

    entry = float(payload.get("entry", 0))
    sl = float(payload.get("sl", 0))
    sl_distance = abs(entry - sl) if entry and sl else 0
    account_balance = float(payload.get("account_balance", getattr(s, "account_balance", 10000)))
    risk_pct = float(payload.get("risk_percent", getattr(s, "risk_percent", 1.0)))

    reason = f"Position size must be positive (got size={size}). "

    if sl_distance > 0:
        pip_size = 0.01 if "JPY" in symbol.upper() else 0.0001
        sl_pips = sl_distance / pip_size
        pip_value = 10.0
        min_lot = 0.01
        min_risk_needed = min_lot * sl_pips * pip_value
        min_balance_needed = min_risk_needed / (risk_pct / 100)
        reason += (
            f"Stop loss TOO WIDE for account size. "
            f"SL distance={sl_distance:.5f} ({sl_pips:.1f} pips), "
            f"Balance=${account_balance:.2f}, Risk={risk_pct}%. "
            f"Min balance needed for 0.01 lots: ~${min_balance_needed:.0f}."
        )
    else:
        reason += "Missing entry/SL prices. Check TradingView webhook payload."

    return reason


def check_max_lot_guard(payload: Dict[str, Any], s) -> Optional[str]:
    """
    Reject trades where Pine sent an absurdly large lot size.

    This catches cases where Pine's initial_capital doesn't match the real
    account balance, producing multi-lot orders on a small account.

    Returns:
        None if size is within bounds, rejection string otherwise.
    """
    size = float(payload.get("size", 0))
    max_lot_size = getattr(s, "max_lot_size", 10.0)
    if size <= max_lot_size:
        return None  # PASS
    return (
        f"Position size {size} lots exceeds max_lot_size={max_lot_size}. "
        f"Check TradingView Pine initial_capital vs actual account balance."
    )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-02 FIX: Flip Timing Guard — FAIL-CLOSED on LIVE
# ─────────────────────────────────────────────────────────────────────────────
def check_flip_timing(payload: Dict[str, Any]) -> Optional[str]:
    """
    Validate FLIP entry timing: bar_time minutes must be on a 5-min boundary.

    Falls back to signal_time when bar_time is absent (Pine sends signal_time
    but not bar_time).  If neither field is present the guard is fail-open
    because the strategy timeframe already constrains FLIP boundaries.

    Returns:
        None if timing is valid (or not a FLIP entry),
        rejection string if timing is invalid.
    """
    entry_model = str(payload.get("entry_model", "")).strip()
    if not entry_model or "flip" not in entry_model.lower():
        return None  # Not a FLIP entry — guard doesn't apply

    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    bar_time = payload.get("bar_time") or payload.get("signal_time")

    if not bar_time:
        # Pine does not send bar_time — signal_time is the fallback.
        # If neither is present, allow the trade (fail-open) since the
        # strategy timeframe already constrains when FLIP entries fire.
        logger.info(
            "FLIP entry on %s: bar_time/signal_time both missing — allowing (fail-open). "
            "Strategy timeframe controls FLIP boundaries.",
            run_mode,
        )
        return None

    if not isinstance(bar_time, str):
        if run_mode == "LIVE":
            logger.error(
                "FLIP entry on LIVE: bar_time is %s, not a string — REJECTED",
                type(bar_time),
            )
            return f"FLIP entry rejected: bar_time must be a string (got {type(bar_time).__name__}) on LIVE"
        logger.warning("FLIP timing: bar_time is not a string (%s) — skipping for %s", type(bar_time), run_mode)
        return None

    try:
        from dateutil.parser import parse as _parse_dt
        dt = _parse_dt(bar_time)
        if dt.minute % 5 != 0:
            return (
                f"FLIP entry rejected: bar_time {bar_time} has minute={dt.minute}, "
                f"which is not on a 5-min boundary (0, 5, 10, 15, ...)"
            )
        return None  # PASS — on a valid 5-min boundary
    except Exception as e:
        if run_mode == "LIVE":
            logger.error("FLIP timing parse error on LIVE: %s — REJECTED (fail-closed)", e)
            return f"FLIP entry rejected: bar_time '{bar_time}' could not be parsed on LIVE — {e}"
        logger.warning("FLIP timing parse error on %s: %s — allowing (non-LIVE)", run_mode, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BUG-03 FIX: Futures Entry Model Guard — FAIL-CLOSED on LIVE
# ─────────────────────────────────────────────────────────────────────────────
def check_futures_entry_model(payload: Dict[str, Any]) -> Optional[str]:
    """
    Enforce Mangoe Futures entry rules:
      - BOC or Directional Close are preferred entry models.
      - FLIP entries require bar_time on a 5-min boundary.
      - Missing entry_model on a Futures symbol is REJECTED on LIVE (BUG-03 fix).

    Previously, a missing entry_model silently passed for Futures. Fixed.

    Returns:
        None if entry model is valid (or not a Futures symbol),
        rejection string if rules are violated.
    """
    symbol = (payload.get("symbol") or "").strip()
    if not _is_futures_symbol(symbol):
        return None  # Not a Futures symbol — guard doesn't apply

    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    entry_model = str(payload.get("entry_model", "")).strip().lower()

    # BUG-03 fix: missing entry_model on Futures is forbidden on LIVE
    if not entry_model:
        if run_mode == "LIVE":
            logger.error(
                "Futures (%s) on LIVE: entry_model missing — REJECTED (fail-closed). "
                "Pine must send entry_model in the webhook payload for Futures.",
                symbol,
            )
            return (
                f"Futures ({symbol}) entry rejected: entry_model is required on LIVE accounts. "
                f"Use 'BOC', 'directional', or 'flip' with valid bar_time."
            )
        logger.warning("Futures (%s) on %s: entry_model missing — allowing (non-LIVE)", symbol, run_mode)
        return None

    # BOC / Directional Close / Break of Candle — always allowed
    if any(x in entry_model for x in ("boc", "break", "directional", "dir_close", "dir close")):
        return None

    # FLIP: delegate to the timing guard (which is already fail-closed on LIVE)
    if "flip" in entry_model:
        timing_reason = check_flip_timing(payload)
        if timing_reason:
            return f"Futures (Mangoe): {timing_reason}"
        return None

    # OTHER / AUTO — allow (e.g., undocumented entry types from Pine)
    logger.debug("Futures (%s): unrecognised entry_model='%s' — allowing", symbol, entry_model)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator: run all global guards in the correct priority order
# ─────────────────────────────────────────────────────────────────────────────
def run_global_guards(payload: Dict[str, Any], s) -> Optional[str]:
    """
    Run all global pre-execution guards in priority order.

    Priority is strictly: kill-switch → size → lot → futures-entry.
    The ENV kill-switch is intentionally NOT called here because it must fire
    before this function (i.e., before symbol/size parsing).
    Call `check_env_kill_switch(s)` first, then call this.

    Returns:
        None if all guards pass, or the first rejection reason string.
    """
    symbol = payload.get("symbol", "UNKNOWN")

    # 1. Size guard (must have a valid lot size)
    reason = check_size_guard(payload, s, symbol)
    if reason:
        logger.warning("SIZE GUARD rejected [%s]: %s", symbol, reason[:200])
        return reason

    # 2. Max lot size cap
    reason = check_max_lot_guard(payload, s)
    if reason:
        logger.warning("MAX LOT GUARD rejected [%s]: %s", symbol, reason)
        return reason

    # 3. Futures entry model (FLIP timing is checked inside)
    reason = check_futures_entry_model(payload)
    if reason:
        logger.warning("FUTURES ENTRY MODEL rejected [%s]: %s", symbol, reason)
        return reason

    return None  # All global guards passed
