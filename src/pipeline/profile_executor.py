"""
src/pipeline/profile_executor.py

Single-account execution unit.

Called by trade_processor.py once per matched broker profile, either
directly (single account) or inside a ThreadPoolExecutor (multi-account).

Responsibilities:
  1. Per-profile idempotency check (Redis SETNX → DB fallback)
  2. Per-account guard chain (account_guards.run_account_guards)
  3. Half-risk enforcement for the 2nd daily trade
  4. Dispatch to logic.process_trade
  5. Record trade in pine_streak intraday budget
  6. Persist execution_failed row on exception
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import get_settings
from config.logging_config import get_logger
from src.pipeline.idempotency import claim_trade_key, exists_trade_key
from src.pipeline.account_guards import run_account_guards
from src.pipeline.account_state import get_account_daily_trade_count
from src.pipeline.audit import save_result

logger = get_logger("trinity.pipeline.profile_executor")


def execute_for_profile(
    payload: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    ai_result: Dict[str, Any],
    dry_run: bool,
    s,
    current_equity_global: float,
    correlation_manager=None,
) -> None:
    """Run guards then execute *logic.process_trade* for one broker profile.

    This function is the atomic unit of execution per account.  It must be
    entirely self-contained so it can be dispatched to a thread without
    shared mutable state.
    """
    from src.services.trade_events import log_guard_decision, log_event
    from src import logic

    profile_id = profile.get("id") if profile else None
    account_name = (profile.get("name") if profile else None) or "default"
    symbol = payload.get("symbol", "UNKNOWN")
    win_prob = float(ai_result.get("rf_prob", 0.0))
    trade_key = (payload.get("trade_key") or "").strip()

    # ── 1. Idempotency (Redis → DB) ───────────────────────────────────────────
    if trade_key:
        if not claim_trade_key(trade_key, profile_id):
            logger.info(
                "Idempotency (Redis): (trade_key=%s, profile=%s) already claimed, skipping",
                trade_key, account_name,
            )
            return
        if exists_trade_key(trade_key, profile_id):
            logger.info(
                "Idempotency (DB): (trade_key=%s, profile=%s) exists, skipping",
                trade_key, account_name,
            )
            return

    # ── 2. Apply per-account PropGuard risk multiplier (pre-guard) ───────────
    acct_multiplier_key = f"_risk_multiplier_{account_name}"
    if acct_multiplier_key in payload:
        payload["_risk_multiplier"] = payload[acct_multiplier_key]

    # ── 3. Per-account guards ─────────────────────────────────────────────────
    rejection = run_account_guards(
        payload, profile, s, current_equity_global,
        correlation_manager=correlation_manager,
    )
    if rejection:
        save_result(
            payload, "risk_rejected", rejection, 0.0,
            broker_profile_id=profile_id, account_name=account_name,
        )
        log_guard_decision("account_guard", "rejected", rejection, symbol)
        logger.warning("ACCOUNT GUARD BLOCKED [%s]: %s", account_name, rejection)
        return

    # ── 4. Re-apply PropGuard multiplier (may have been set by guard above) ──
    if acct_multiplier_key in payload:
        payload["_risk_multiplier"] = payload[acct_multiplier_key]
    approved_pair_multiplier = float(payload.get("_approved_pair_risk_multiplier", 1.0))
    if approved_pair_multiplier < 1.0:
        current_mult = float(payload.get("_risk_multiplier", 1.0))
        payload["_risk_multiplier"] = current_mult * approved_pair_multiplier
        logger.info(
            "ApprovedPairsGuard [%s]: multiplier %.2f → %.2f",
            account_name, current_mult, payload["_risk_multiplier"],
        )

    # ── 5. Half-risk for 2nd daily trade ─────────────────────────────────────
    max_daily = getattr(s, "pine_max_trades_per_day", 0)
    if max_daily >= 2:
        try:
            acct_today_count = get_account_daily_trade_count(profile)
            if acct_today_count == 1:   # this trade will be the 2nd
                current_mult = float(payload.get("_risk_multiplier", 1.0))
                payload["_risk_multiplier"] = current_mult * 0.5
                logger.info(
                    "Half-risk [%s]: 2nd trade of day — multiplier %.2f → %.2f",
                    account_name, current_mult, payload["_risk_multiplier"],
                )
        except Exception as e:
            logger.warning("Half-risk daily count failed for %s: %s (fail-open)", account_name, e)

    # ── 6. Execute ────────────────────────────────────────────────────────────
    try:
        if dry_run:
            logger.info(
                "DRY_RUN [%s]: LIVE_TRADING=false — saving alert + notify only", account_name
            )
        log_event(
            None, "execution_started", "worker",
            {"symbol": symbol, "dry_run": dry_run, "profile": account_name},
        )
        logic.process_trade(payload, dry_run=dry_run, ai_result=ai_result, profile=profile)
        logger.info("logic.process_trade completed for profile %s", account_name)

        # Record in intraday streak tracker
        try:
            from src.services.pine_streak import record_trade_result as _record_streak
            from src.adapters.redis_queue import get_redis
            _risk_pct = float(payload.get("risk_percent", get_settings().risk_percent))
            _record_streak(get_redis(), pnl=0.0, risk_pct=_risk_pct)
        except Exception as _streak_err:
            logger.debug("pine_streak record failed (non-fatal): %s", _streak_err)

    except Exception as exec_err:
        logger.error("logic.process_trade failed for %s: %s", account_name, exec_err)
        log_event(
            None, "execution_failed", "worker",
            {"symbol": symbol, "error": str(exec_err)[:200], "profile": account_name},
        )
        save_result(
            payload,
            "execution_failed",
            f"logic.process_trade: {str(exec_err)[:80]}",
            win_prob,
            ai_reasoning=ai_result,
            broker_profile_id=profile_id,
            account_name=account_name,
        )
