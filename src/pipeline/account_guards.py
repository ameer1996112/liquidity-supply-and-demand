"""
src/pipeline/account_guards.py

Per-account guard chain.

Guards run in order and return the first rejection reason. All are
fail-closed for LIVE accounts (missing dependency → trade blocked).
PAPER/DRY_RUN accounts use fail-open semantics for all dependency errors.

Guard execution order:
  1. Per-account Redis kill-switch  (BUG-06 fix: fail-closed on LIVE)
  2. MTM Guardian                   (fail-closed on LIVE)
  3. MetaAPI circuit breaker        (LIVE only, fail-closed)
  4. Adaptive daily trade limit     (fail-closed on LIVE)
  5. PropGuard                      (drawdown / daily-loss / position risk)
  6. Correlation guard              (bucket full / correlated pairs)
  7. Consistency Analyzer           (evaluation mode only)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import get_settings
from config.logging_config import get_logger
from src.core.guard_rails.prop_guard import check_safety, check_signal_guards
from src.pipeline.account_state import (
    get_account_daily_pnl,
    get_account_daily_trade_count,
    get_account_positions_from_db,
)
from src.services.account_guard_settings import load_account_guard_overrides

logger = get_logger("trinity.pipeline.account_guards")


def _account_override(overrides: Dict[str, Any], key: str, fallback: Any) -> Any:
    return overrides.get(key, fallback)


def run_account_guards(
    payload: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    s,
    current_equity_global: float,
    correlation_manager=None,
) -> Optional[str]:
    """Run per-account guards.

    Returns None if all guards pass, or a rejection reason string if any block.
    Stamps ``payload["_risk_multiplier_<account_name>"]`` on PropGuard pass.
    """
    symbol = payload.get("symbol", "UNKNOWN")
    side = payload.get("side", "buy")
    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    profile_id = profile.get("id") if profile else None
    account_name = (profile.get("name") if profile else None) or "default"
    profile_risk_pct = (
        float(profile.get("risk_pct", s.risk_percent)) if profile else s.risk_percent
    )
    overrides = load_account_guard_overrides(str(profile_id or account_name))

    # ── 1. Per-account Redis kill-switch ─────────────────────────────────────
    try:
        from src.adapters.redis_queue import get_redis as _get_redis
        acct_kill_key = (
            f"trading:kill_switch:{account_name}"
            if account_name != "default"
            else "trading:kill_switch"
        )
        if _get_redis().get(acct_kill_key) == "1":
            return f"Kill switch ON for account {account_name}"
    except Exception as e:
        if run_mode == "LIVE":
            logger.critical(
                "Kill switch check failed for %s in LIVE mode: %s — blocking (fail-closed)",
                account_name, e,
            )
            return f"Kill switch dependency unavailable for account {account_name} — blocked for safety"
        logger.warning(
            "Kill switch check failed for %s: %s (non-LIVE, continuing)", account_name, e
        )

    # ── 2. MTM Guardian ───────────────────────────────────────────────────────
    sb = _get_sb()
    mtm_enabled = bool(
        _account_override(overrides, "mtm_guardian_enabled", getattr(s, "mtm_guardian_enabled", True))
    )
    if mtm_enabled and not sb and run_mode == "LIVE":
        return f"MTM Guardian dependency unavailable for account {account_name} — blocked for safety"
    if sb and mtm_enabled:
        try:
            from src.services.mtm_guardian import MTMGuardian
            from src.adapters.redis_queue import get_redis as _get_redis
            acct_balance = float(payload.get("account_balance", s.account_balance))
            mtm_guardian = MTMGuardian(sb, s, starting_balance=acct_balance)
            mtm_kill, mtm_reason = mtm_guardian.check_kill_switch(
                account_name=account_name,
                broker_profile_id=profile_id,
            )
            if mtm_kill:
                try:
                    kill_key = (
                        f"trading:kill_switch:{account_name}"
                        if account_name != "default"
                        else "trading:kill_switch"
                    )
                    _get_redis().set(kill_key, "1")
                    logger.critical("MTM KILL SWITCH ENGAGED for %s: %s", account_name, mtm_reason)
                except Exception:
                    pass
                return mtm_reason
        except Exception as e:
            if run_mode == "LIVE":
                logger.critical(
                    "MTM Guardian failed for %s in LIVE mode: %s — blocking (fail-closed)",
                    account_name, e,
                )
                return f"MTM Guardian dependency unavailable for account {account_name} — blocked for safety"
            logger.error("MTM Guardian failed for %s: %s (non-LIVE, continuing)", account_name, e)

    # ── 3. Per-account circuit breaker (LIVE only) ────────────────────────────
    if run_mode == "LIVE":
        try:
            from src.core.circuit_breaker import is_metaapi_circuit_open
            if is_metaapi_circuit_open(account_name=account_name):
                return f"Circuit breaker open for account {account_name}"
        except Exception as e:
            logger.critical(
                "Circuit breaker check failed for %s in LIVE mode: %s — blocking (fail-closed)",
                account_name, e,
            )
            return f"Circuit breaker dependency unavailable for account {account_name} — blocked for safety"

    # ── 4. Adaptive daily trade limit ─────────────────────────────────────────
    try:
        from src.core.guard_rails.pine_guardian import create_pine_guardian_from_settings
        from src.services.pine_streak import get_streak_days, get_today_summary
        from src.adapters.redis_queue import get_redis as _get_redis_for_limit
        import datetime as _dt_mod

        _redis = _get_redis_for_limit()
        _guardian = create_pine_guardian_from_settings()
        _guardian.adaptive_enabled = bool(
            _account_override(overrides, "pine_adaptive_enabled", _guardian.adaptive_enabled)
        )
        _guardian.max_trades_per_day = int(
            _account_override(overrides, "pine_max_trades_per_day", _guardian.max_trades_per_day)
        )
        _guardian.daily_risk_budget_pct = float(
            _account_override(overrides, "pine_daily_risk_budget_pct", _guardian.daily_risk_budget_pct)
        )

        if _guardian.adaptive_enabled:
            _wins, _losses, _risk_deployed = get_today_summary(_redis, account_name)
            _guardian.daily_wins = _wins
            _guardian.daily_losses = _losses
            _guardian.daily_risk_deployed_pct = _risk_deployed
            _guardian.consecutive_losses = _losses if _wins == 0 else 0
            _guardian.current_day_trades = _wins + _losses

            _streak_days = get_streak_days(_redis, account_name)
            _utc_hour = _dt_mod.datetime.now(_dt_mod.timezone.utc).hour

            if not _guardian.check_max_trades(streak_days=_streak_days, utc_hour=_utc_hour):
                _state = _guardian.compute_effective_limit(_streak_days, _utc_hour)
                return (
                    f"Adaptive trade limit ({account_name}): "
                    f"{_state.current_session_trades}/{_state.effective_limit} "
                    f"[{_state.session.value} | base={_state.session_base} "
                    f"intraday={_state.intraday_adj:+d} streak={_state.streak_bonus:+d}]"
                )
            if not _guardian.check_risk_budget():
                return (
                    f"Daily risk budget exhausted ({account_name}): "
                    f"{_guardian.daily_risk_deployed_pct:.2f}% >= {_guardian.daily_risk_budget_pct:.2f}%"
                )
        else:
            static_max_trades = int(_account_override(overrides, "pine_max_trades_per_day", getattr(s, "pine_max_trades_per_day", 0)))
            if static_max_trades <= 0:
                static_max_trades = 0
            if static_max_trades > 0:
                today_count = get_account_daily_trade_count(profile)
                if today_count >= static_max_trades:
                    return (
                        f"Daily trade limit reached ({account_name}): "
                        f"{today_count}/{static_max_trades} trades today"
                    )
    except Exception as e:
        if run_mode == "LIVE":
            logger.critical(
                "Adaptive trade limit failed for %s in LIVE mode: %s — blocking (fail-closed)",
                account_name, e,
            )
            return f"Adaptive trade limit dependency unavailable for account {account_name} — blocked for safety"
        logger.warning(
            "Adaptive trade limit failed for %s: %s (non-LIVE, continuing)", account_name, e
        )

    _profile_eval_mode = (profile or {}).get("evaluation_mode")
    _global_eval_mode = getattr(s, "evaluation_mode", False)
    _eval_mode = _profile_eval_mode if _profile_eval_mode is not None else _global_eval_mode

    # ── 5. Evaluation signal guards ──────────────────────────────────────────
    try:
        signal_allowed, signal_reason = check_signal_guards(
            payload,
            sb,
            profile=profile,
            fail_closed=(run_mode == "LIVE"),
        )
        if not signal_allowed:
            return f"SignalGuard ({account_name}): {signal_reason}"
    except Exception as e:
        if run_mode == "LIVE":
            logger.critical(
                "Signal guard failed for %s in LIVE mode: %s — blocking (fail-closed)",
                account_name, e,
            )
            return f"Signal guard dependency unavailable for account {account_name} — blocked for safety"
        logger.warning("Signal guard failed for %s: %s (non-LIVE, continuing)", account_name, e)

    # ── 6. PropGuard ─────────────────────────────────────────────────────────
    acct_balance = float(payload.get("account_balance", s.account_balance))
    daily_pnl = get_account_daily_pnl(profile)
    current_equity = acct_balance + daily_pnl

    allowed, risk_multiplier, risk_label = check_safety(
        current_equity, acct_balance, daily_pnl,
        account_name=account_name,
        kill_threshold_override=float(
            _account_override(overrides, "trinity_max_daily_loss_pct", getattr(s, "trinity_max_daily_loss_pct", 4.0))
        ),
        risk_pct_override=profile_risk_pct,
    )
    if not allowed:
        return f"PropGuard ({account_name}): {risk_label}"
    logger.info("PropGuard [%s]: %s (multiplier=%.2f)", account_name, risk_label, risk_multiplier)
    payload[f"_risk_multiplier_{account_name}"] = risk_multiplier

    # ── 7. Correlation Guard ──────────────────────────────────────────────────
    active_positions = get_account_positions_from_db(profile)
    max_pos = int(
        _account_override(
            overrides,
            "trinity_max_positions",
            (profile.get("max_positions") if profile else None) or s.trinity_max_positions,
        )
    )

    if correlation_manager:
        try:
            corr_result = correlation_manager.check(
                symbol=symbol, side=side, active_positions=active_positions
            )
            if not corr_result.passed:
                return f"Correlation ({account_name}): {corr_result.rejection_message}"
            logger.info(
                "Correlation [%s]: %s/%s active — PASSED",
                account_name, len(active_positions), max_pos,
            )
        except Exception as e:
            logger.error("Correlation guard crashed for %s: %s", account_name, e)
            return f"Correlation error ({account_name}): {str(e)[:50]}"
    elif len(active_positions) >= max_pos:
        return f"Bucket Full ({account_name}): {len(active_positions)}/{max_pos}"

    # ── 8. Consistency Analyzer (evaluation mode only) ────────────────────────
    _profile_consistency = (profile or {}).get("consistency_enabled")
    _global_consistency = getattr(s, "consistency_enabled", True)
    _run_consistency = _profile_consistency if _profile_consistency is not None else _global_consistency
    if _run_consistency and _eval_mode and not sb and run_mode == "LIVE":
        return f"Consistency dependency unavailable for account {account_name} — blocked for safety"
    if _run_consistency and _eval_mode and sb:
        try:
            from src.services.consistency_analyzer import ConsistencyAnalyzer
            consistency = ConsistencyAnalyzer(sb, s)
            entry = float(payload.get("entry", 0))
            tp = float(payload.get("tp", 0))
            size = float(payload.get("size", 0))
            if entry > 0 and tp > 0:
                if "JPY" in symbol:
                    pip_size, pip_value = 0.01, 1000.0
                elif "XAU" in symbol or "GOLD" in symbol:
                    pip_size, pip_value = 0.01, 100.0
                else:
                    pip_size, pip_value = 0.0001, 10.0
                tp_pips = abs(tp - entry) / pip_size
                expected_profit = tp_pips * pip_value * size
                allowed, reason, risk_mult = consistency.check_trade_consistency_risk(
                    expected_profit,
                    account_name=account_name,
                    broker_profile_id=profile_id,
                )
                if not allowed:
                    return f"Consistency ({account_name}): {reason}"
                if risk_mult < 1.0:
                    payload[f"_consistency_risk_multiplier_{account_name}"] = risk_mult
        except Exception as e:
            logger.error("Consistency analyzer crashed for %s: %s", account_name, e)

    return None  # All per-account guards passed


def _get_sb():
    try:
        import src.adapters.supabase as _m
        return _m.supabase
    except Exception:
        return None
