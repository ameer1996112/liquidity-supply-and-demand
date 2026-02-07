"""
Trade Executor (Consumer) - Orchestrator.
Guards: kill-switch, idempotency, risk, correlation, ML. On pass: logic.process_trade.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env from project root
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

from config import get_settings
from src.adapters.redis_queue import QUEUE_NAME, get_redis, push_dead_letter, reset_redis_client
from src.ai.brain import ensemble_decision, get_prediction, load_brain
from src.core.risk_engine import calculate_max_position_size as _calculate_max_position_size_impl
from src.core.guard_rails.correlation import (
    create_correlation_manager_from_settings,
    get_active_positions_from_db,
)
from src.core.guard_rails.prop_guard import check_safety
from src.services.trade_events import log_event, log_guard_decision
from src import logic
from src.services.watchdog import TradeWatchdog

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("TRINITY_WORKER")

MAX_OPEN_POSITIONS = 3
ML_MIN_CONFIDENCE = 0.50

supabase = None
correlation_manager = None


def init_connections():
    global supabase, correlation_manager
    r = get_redis()
    s = get_settings()
    key = (s.supabase_service_role_key or s.supabase_key).strip()
    if s.supabase_url and key:
        from supabase import create_client
        supabase = create_client(s.supabase_url, key)
        logger.info("Supabase connected")
    else:
        logger.warning("Supabase credentials missing - logging disabled")

    try:
        correlation_manager = create_correlation_manager_from_settings()
        logger.info("CorrelationManager initialized")
    except Exception as exc:
        logger.warning("CorrelationManager init failed (fallback to simple count): %s", exc)


def _exists_trade_key(trade_key: str, broker_profile_id: Optional[int] = None) -> bool:
    """True if a row already exists for this trade_key (and optional broker_profile_id)."""
    if not trade_key or not str(trade_key).strip() or not supabase:
        return False
    try:
        q = supabase.table("trading_signals").select("id").eq("trade_key", trade_key.strip()).limit(1)
        if broker_profile_id is not None:
            q = q.eq("broker_profile_id", broker_profile_id)
        else:
            q = q.is_("broker_profile_id", "null")
        r = q.execute()
        return len(r.data) > 0
    except Exception as e:
        logger.warning("Idempotency check failed: %s", e)
        return False


def _lookup_symbol_overrides(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch per-symbol risk rules from Supabase (if available)."""
    if not supabase or not symbol:
        return None
    try:
        r = (
            supabase.table("symbol_risk_rules")
            .select("*")
            .eq("symbol", symbol.upper())
            .limit(1)
            .execute()
        )
        if r.data:
            return r.data[0]
    except Exception as e:
        logger.warning("symbol_risk_rules lookup failed for %s: %s", symbol, e)
    return None


def _max_position_size(payload: Dict[str, Any]) -> float:
    s = get_settings()
    symbol = payload.get("symbol", "UNKNOWN")
    symbol_overrides = _lookup_symbol_overrides(symbol)
    if symbol_overrides:
        logger.info(
            "Symbol overrides for %s: pip_size=%s pip_value=%s max_lot=%s",
            symbol,
            symbol_overrides.get("pip_size"),
            symbol_overrides.get("pip_value_per_lot"),
            symbol_overrides.get("max_lot_size"),
        )
        payload["_symbol_overrides"] = symbol_overrides
    risk_multiplier = float(payload.get("_risk_multiplier", 1.0))
    return _calculate_max_position_size_impl(
        payload,
        account_balance=float(payload.get("account_balance", s.account_balance)),
        risk_percent=float(payload.get("risk_percent", s.risk_percent)),
        risk_multiplier=risk_multiplier,
        symbol_overrides=symbol_overrides,
    )


# Single-arg API for tests and callers that pass balance/risk via payload or settings
def calculate_max_position_size(payload: Dict[str, Any]) -> float:
    """Max allowed lot size for payload (uses settings for balance/risk)."""
    return _max_position_size(payload)


def _payload_zone_and_metrics(payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract zone and metric fields from payload (including F: prefixed) for DB and ai_reasoning.
    So filtered signals still show Zone Analysis and score breakdown in the inspector.
    """
    def _f(k: str, default=None):
        return payload.get(k) if payload.get(k) is not None else payload.get(f"F:{k}", default)

    # Top-level columns for trading_signals (only keys that exist in schema - no zone_grade column)
    schema_zone_metrics = (
        "zone_id", "zone_type", "zone_top", "zone_bottom", "zone_size_pips",
        "entry_model", "score", "freshness", "session", "atr_ratio", "trend", "htf_trend",
        "rsi", "rvol", "adx", "touch_count", "base_quality", "departure_strength",
        "liquidity_distance", "liquidity_spread", "return_strength",
    )
    columns = {}
    for key in schema_zone_metrics:
        val = _f(key)
        if val is not None:
            columns[key] = val
    for key in ("liq_swept", "target_swept", "caused_sweep", "is_accuracy"):
        if payload.get(key) is not None:
            columns[key] = bool(payload[key])

    # ai_reasoning shape for Signal Inspector (zone_grade lives only in JSON, not a DB column)
    reason = {
        "zone_id": columns.get("zone_id"),
        "zone_type": columns.get("zone_type"),
        "zone_grade": payload.get("zone_grade") or payload.get("grade"),
        "zone_score": columns.get("score"),
        "entry_model": columns.get("entry_model"),
        "liquidity_swept": columns.get("liq_swept"),
        "target_swept": columns.get("target_swept"),
        "caused_sweep": columns.get("caused_sweep"),
        "is_accuracy": columns.get("is_accuracy"),
        "session": columns.get("session"),
        "trend": columns.get("trend"),
        "htf_trend": columns.get("htf_trend"),
        "rsi": columns.get("rsi"),
        "rvol": columns.get("rvol"),
        "adx": columns.get("adx"),
        "atr_ratio": columns.get("atr_ratio"),
        "base_quality": columns.get("base_quality"),
        "departure_strength": columns.get("departure_strength"),
        "return_strength": columns.get("return_strength"),
        "liquidity_distance": columns.get("liquidity_distance"),
        "liquidity_spread": columns.get("liquidity_spread"),
    }
    # Drop None values so frontend doesn't show empty rows
    reason = {k: v for k, v in reason.items() if v is not None}
    return columns, reason


def save_result(
    payload: Dict[str, Any],
    status: str,
    note: str,
    prob: float,
    ai_reasoning: Optional[Dict[str, Any]] = None,
    broker_profile_id: Optional[int] = None,
):
    if not supabase:
        logger.warning("Supabase unavailable - result not saved: %s", status)
        return
    data = {
        "symbol": payload.get("symbol", "UNKNOWN"),
        "side": payload.get("side", "buy"),
        "size": float(payload.get("size", 0.01)),
        "entry": float(payload.get("entry", 0)) if payload.get("entry") else None,
        "sl": float(payload.get("sl", 0)) if payload.get("sl") else None,
        "tp": float(payload.get("tp", 0)) if payload.get("tp") else None,
        "status": status,
        "notes": note,
        "ml_win_probability": prob,
        "run_mode": payload.get("run_mode", "PAPER"),
    }
    tk = (payload.get("trade_key") or "").strip()
    if tk:
        data["trade_key"] = tk
    if broker_profile_id is not None:
        data["broker_profile_id"] = broker_profile_id

    # Zone + metrics so filtered signals show Zone Analysis and score breakdown in UI
    extra_columns, zone_reason = _payload_zone_and_metrics(payload)
    data.update(extra_columns)

    # ai_reasoning: merge zone/metrics with optional caller-provided (e.g. ensemble)
    merged_reason = {**zone_reason}
    if ai_reasoning:
        merged_reason.update(ai_reasoning)
    if merged_reason:
        merged_reason.setdefault("decision", status)
        merged_reason.setdefault("reason", note)
        data["ai_reasoning"] = json.dumps(merged_reason)

    try:
        supabase.table("trading_signals").insert(data).execute()
        logger.info("Saved: %s | %s", status, note)
    except Exception as e:
        logger.error("DB write failed: %s", e)


def _build_ml_rejection_reasoning(payload: Dict, win_prob: float, features_used: Dict, note: str) -> Dict[str, Any]:
    reasoning = {
        "decision": "rejected",
        "confidence": round(win_prob, 4),
        "threshold": ML_MIN_CONFIDENCE,
        "reason": note,
    }
    for k in ("zone_id", "zone_type", "zone_grade", "entry_model", "score"):
        if payload.get(k) is not None:
            reasoning[k if k != "score" else "zone_score"] = payload[k]
    if features_used:
        reasoning["features_used"] = {k: float(v) if isinstance(v, (int, float)) else v for k, v in features_used.items() if v is not None}
    return reasoning


def _validate_flip_timing(payload: Dict[str, Any]) -> Optional[str]:
    """Validate FLIP entry timing: bar_time minutes must be at 15-min boundary (00/15/30/45).

    Returns None if valid or not a FLIP entry, error message if invalid.
    Fail-open: missing bar_time or parse errors allow the trade through.
    """
    entry_model = str(payload.get("entry_model", "")).strip()
    if not entry_model or "flip" not in entry_model.lower():
        return None

    bar_time = payload.get("bar_time")
    if not bar_time:
        logger.warning("FLIP entry but no bar_time in payload — allowing (no data to validate)")
        return None

    try:
        from datetime import datetime as _dt

        if not isinstance(bar_time, str):
            logger.warning("bar_time is not a string (%s) — skipping FLIP timing check", type(bar_time))
            return None

        cleaned = bar_time.replace("+00:00", "").replace("Z", "").split("+")[0].split("-0")[0] if "T" in bar_time else bar_time
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = _dt.strptime(cleaned, fmt)
                break
            except ValueError:
                continue
        else:
            from dateutil.parser import parse as _parse_dt
            dt = _parse_dt(bar_time)

        if dt.minute not in {0, 15, 30, 45}:
            return (
                f"FLIP entry rejected: bar_time {bar_time} has minute={dt.minute}, "
                f"but FLIP entries require 15-min boundaries (00/15/30/45)"
            )
        return None
    except Exception as e:
        logger.warning("FLIP timing validation error: %s — allowing trade (fail-open)", e)
        return None


_GRADE_VALUES = {"A+": 6, "A": 5, "B+": 4, "B": 3, "C+": 2, "C": 1}


def _validate_pine_filters(payload: Dict[str, Any]) -> Optional[str]:
    """Deterministic pre-filters mirroring SND_Strategy.pine entry conditions.

    Checks: score, grade, return strength, liquidity sweep, departure strength,
    dead zone, trading hours, daily trade limit.
    Returns None if all pass, rejection reason string if any fails.
    """
    s = get_settings()

    # --- Zone quality score ---
    score = payload.get("score")
    if score is not None:
        try:
            if float(score) < s.pine_min_score:
                return f"Zone score {score} below minimum {s.pine_min_score}"
        except (ValueError, TypeError):
            pass

    # --- Zone grade ---
    grade = payload.get("zone_grade") or payload.get("grade")
    if grade and s.pine_min_grade:
        grade_val = _GRADE_VALUES.get(str(grade).upper().strip(), 0)
        min_val = _GRADE_VALUES.get(s.pine_min_grade.upper().strip(), 0)
        if grade_val > 0 and min_val > 0 and grade_val < min_val:
            return f"Zone grade {grade} below minimum {s.pine_min_grade}"

    # --- Liquidity swept (core S&D rule) ---
    if s.pine_require_liq_swept:
        liq_swept = payload.get("liq_swept")
        if liq_swept is not None and not bool(liq_swept):
            return "Liquidity not swept before entry (liq_swept=false)"

    # --- Departure strength (arrival rule) ---
    dep_str = payload.get("departure_strength")
    if dep_str is not None and s.pine_min_departure_strength > 0:
        try:
            if float(dep_str) < s.pine_min_departure_strength:
                return f"Compressed arrival: departure_strength {dep_str} < {s.pine_min_departure_strength}"
        except (ValueError, TypeError):
            pass

    # --- Return strength ---
    ret_str = payload.get("return_strength")
    if ret_str is not None and s.pine_min_return_strength > 0:
        try:
            if float(ret_str) < s.pine_min_return_strength:
                return f"Slow return: return_strength {ret_str} < {s.pine_min_return_strength}"
        except (ValueError, TypeError):
            pass

    # --- Dead zone (xx:50-xx:00) ---
    if s.pine_block_dead_zone:
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                from datetime import datetime as _dt
                cleaned = bar_time.replace("+00:00", "").replace("Z", "").split("+")[0].split("-0")[0] if "T" in bar_time else bar_time
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt = _dt.strptime(cleaned, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    from dateutil.parser import parse as _parse_dt
                    dt = _parse_dt(bar_time)
                if dt.minute >= 50:
                    return f"Dead zone: bar_time {bar_time} is in last 10 min of hour (minute={dt.minute})"
            except Exception:
                pass  # fail-open

    # --- Trading hours (UTC) ---
    if s.pine_trading_start_hour != 0 or s.pine_trading_end_hour != 23:
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                from datetime import datetime as _dt
                cleaned = bar_time.replace("+00:00", "").replace("Z", "").split("+")[0].split("-0")[0] if "T" in bar_time else bar_time
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt = _dt.strptime(cleaned, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    from dateutil.parser import parse as _parse_dt
                    dt = _parse_dt(bar_time)
                if dt.hour < s.pine_trading_start_hour or dt.hour >= s.pine_trading_end_hour:
                    return f"Outside trading hours: hour={dt.hour} (allowed {s.pine_trading_start_hour}-{s.pine_trading_end_hour} UTC)"
            except Exception:
                pass  # fail-open

    # --- Daily trade limit ---
    if s.pine_max_trades_per_day > 0 and supabase:
        try:
            from datetime import datetime as _dt, timezone
            today_start = _dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            result = (
                supabase.table("trading_signals")
                .select("id")
                .in_("status", ["active", "executed", "closed"])
                .gte("created_at", today_start)
                .execute()
            )
            today_count = len(result.data)
            if today_count >= s.pine_max_trades_per_day:
                return f"Daily trade limit reached: {today_count}/{s.pine_max_trades_per_day} trades today"
        except Exception as e:
            logger.warning("Daily trade limit check failed: %s (fail-open)", e)

    # --- R:R ratio ---
    rr = payload.get("rr_ratio")
    if rr is not None and s.min_rr_ratio > 0:
        try:
            if float(rr) < s.min_rr_ratio:
                return f"R:R ratio {rr} below minimum {s.min_rr_ratio}"
        except (ValueError, TypeError):
            pass

    return None


def process_trade(payload: Dict[str, Any]):
    symbol = payload.get("symbol", "UNKNOWN")
    side = payload.get("side", "buy")
    size = float(payload.get("size", 0.01))
    logger.info("Processing: %s | %s | Size: %s", symbol, side.upper(), size)

    s = get_settings()

    # ── Invalid size (e.g. TradingView sent size=0) ─────────────────────
    if size <= 0 or not isinstance(payload.get("size"), (int, float)):
        save_result(
            payload,
            "filtered",
            f"Position size must be positive (got size={payload.get('size')})",
            0.0,
        )
        logger.warning(
            "SIZE REJECTED: size=%s (must be > 0). Check TradingView alert / Pine position sizing.",
            payload.get("size"),
        )
        return

    # ── Kill Switch (env var + Redis key from UI) ────────────
    redis_kill = False
    try:
        redis_kill = get_redis().get("trading:kill_switch") == "1"
    except Exception:
        pass
    if getattr(s, "trading_kill_switch", False) or redis_kill:
        save_result(payload, "kill_switch_blocked", "Trading kill-switch is ON", 0.0)
        log_event(None, "kill_switch_blocked", "worker", {"symbol": symbol})
        log_guard_decision("kill_switch", "blocked", "Trading kill-switch is ON", symbol)
        logger.warning("KILL-SWITCH: execution blocked")
        return

    # ── Circuit breaker (MetaApi / LIVE) ─────────────────────
    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    if run_mode == "LIVE":
        try:
            from src.core.circuit_breaker import is_metaapi_circuit_open
            if is_metaapi_circuit_open():
                save_result(
                    payload,
                    "circuit_breaker_blocked",
                    "MetaApi circuit breaker open (rate limit or repeated failures)",
                    0.0,
                )
                log_event(None, "circuit_breaker_blocked", "worker", {"symbol": symbol})
                log_guard_decision("circuit_breaker", "blocked", "MetaApi circuit open", symbol)
                logger.warning("CIRCUIT BREAKER: LIVE execution skipped")
                return
        except Exception:
            pass  # fail-open if circuit module unavailable

    # ── Idempotency is checked per-profile in the execution loop (multi-account) ──

    # ── PropGuard: Step-Up Risk Scaling ──────────────────────
    daily_pnl = 0.0
    if supabase:
        try:
            from datetime import date, datetime
            today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
            pnl_resp = supabase.table("trading_signals").select("pnl_usd").eq("status", "closed").gte("created_at", today_start).execute()
            daily_pnl = sum(float(t.get("pnl_usd") or 0) for t in (pnl_resp.data or []))
        except Exception:
            pass
    current_equity = s.account_balance + daily_pnl
    allowed, risk_multiplier, risk_label = check_safety(current_equity, s.account_balance, daily_pnl)
    if not allowed:
        save_result(payload, "risk_rejected", f"PropGuard: {risk_label}", 0.0)
        log_event(None, "prop_guard_blocked", "worker", {"label": risk_label, "daily_pnl": daily_pnl})
        log_guard_decision("prop_guard", "rejected", risk_label, symbol, {"daily_pnl": daily_pnl})
        logger.warning("PROP GUARD BLOCKED: %s", risk_label)
        return
    logger.info("PropGuard: %s (multiplier=%.2f)", risk_label, risk_multiplier)
    payload["_risk_multiplier"] = risk_multiplier

    # Pre-flight risk estimate (config balance — actual cap with live balance is in logic.py)
    max_allowed_size = _max_position_size(payload)
    logger.info("Risk Pre-Check (config balance): size %s vs estimate %s", size, round(max_allowed_size, 2))
    if size > max_allowed_size:
        logger.warning(
            "Size %s exceeds config-based estimate %s — logic.py will re-check with live balance",
            size,
            round(max_allowed_size, 2),
        )

    # ── Correlation Guard (full portfolio check) ─────────────
    if correlation_manager:
        try:
            active_positions = get_active_positions_from_db()
            corr_result = correlation_manager.check(symbol=symbol, side=side, active_positions=active_positions)
            logger.info("Correlation Check: %s/%s active", len(active_positions), s.trinity_max_positions)
            if not corr_result.passed:
                save_result(payload, "correlation_rejected", corr_result.rejection_message, 0.0)
                log_event(None, "correlation_rejected", "worker", {"reason": corr_result.rejection_message})
                log_guard_decision("correlation", "rejected", corr_result.rejection_message, symbol)
                logger.warning("CORRELATION REJECTED: %s", corr_result.rejection_message)
                return
        except Exception as e:
            logger.error("Correlation guard crashed: %s", e)
            save_result(payload, "correlation_rejected", f"DB Error: {str(e)[:50]}", 0.0)
            return
    elif supabase:
        try:
            active = supabase.table("trading_signals").select("id").in_("status", ["active", "executed"]).execute()
            active_count = len(active.data)
            logger.info("Correlation Check (simple): %s/%s active", active_count, MAX_OPEN_POSITIONS)
            if active_count >= MAX_OPEN_POSITIONS:
                msg = f"Bucket Full ({active_count}/{MAX_OPEN_POSITIONS})"
                save_result(payload, "correlation_rejected", msg, 0.0)
                log_guard_decision("correlation", "rejected", msg, symbol)
                logger.warning("CORRELATION REJECTED: bucket full")
                return
        except Exception as e:
            logger.error("Correlation guard crashed: %s", e)
            save_result(payload, "correlation_rejected", f"DB Error: {str(e)[:50]}", 0.0)
            return

    # ------------------------------------------------------------------
    # FLIP Entry Timing Validation
    # FLIP entries must occur at 15-minute candle boundaries (xx:00/15/30/45)
    # ------------------------------------------------------------------
    flip_error = _validate_flip_timing(payload)
    if flip_error:
        save_result(payload, "filtered", flip_error, 0.0)
        logger.warning("FLIP TIMING REJECTED: %s", flip_error)
        return

    # ------------------------------------------------------------------
    # Pine-Matching Deterministic Pre-Filters
    # Mirror SND_Strategy.pine entry rules: score, grade, liq_swept,
    # departure/return strength, dead zone, trading hours, daily limit, R:R.
    # Runs BEFORE ensemble brain to avoid wasting AI/ML processing.
    # ------------------------------------------------------------------
    pine_error = _validate_pine_filters(payload)
    if pine_error:
        save_result(payload, "filtered", f"Pine filter: {pine_error}", 0.0)
        logger.warning("PINE PRE-FILTER REJECTED: %s", pine_error)
        return

    # ------------------------------------------------------------------
    # Ensemble Brain decision (RF + RAG + LLM)
    # ------------------------------------------------------------------
    ai_result = ensemble_decision(payload)

    # Enrich AI result with zone/sweep/metrics from original payload
    # so the frontend Signal Inspector can display them.
    _ZONE_FIELD_MAP = {
        "zone_id": "zone_id",
        "zone_type": "zone_type",
        "zone_grade": "zone_grade",
        "entry_model": "entry_model",
        "score": "zone_score",
        "liq_swept": "liquidity_swept",
        "target_swept": "target_swept",
        "caused_sweep": "caused_sweep",
        "is_accuracy": "is_accuracy",
        "session": "session",
        "trend": "trend",
        "htf_trend": "htf_trend",
        "rsi": "rsi",
        "rvol": "rvol",
        "adx": "adx",
        "atr_ratio": "atr_ratio",
        "base_quality": "base_quality",
        "departure_strength": "departure_strength",
        "liquidity_distance": "liquidity_distance",
        "liquidity_spread": "liquidity_spread",
        "return_strength": "return_strength",
    }
    for src_key, dst_key in _ZONE_FIELD_MAP.items():
        val = payload.get(src_key)
        if val is not None and dst_key not in ai_result:
            ai_result[dst_key] = val

    logger.info(
        "🧠 BRAIN DECISION:\n"
        "Decision: %s\n"
        "RF Score: %.4f\n"
        "RAG Rules: %d found\n"
        "Reason: %s",
        ai_result.get("decision"),
        ai_result.get("rf_prob", 0.0),
        len(ai_result.get("rules") or []),
        ai_result.get("reason", ""),
    )

    decision = str(ai_result.get("decision", "NO_GO")).upper()
    shadow_mode = bool(getattr(s, "run_shadow_mode", False))

    if decision == "NO_GO":
        if shadow_mode:
            logger.warning("⚠️ SHADOW MODE: Executing trade despite AI rejection.")
        else:
            reason = ai_result.get("reason", "AI ensemble rejected trade.")
            save_result(
                payload,
                "ai_rejected",
                reason,
                float(ai_result.get("rf_prob", 0.0)),
                ai_reasoning=ai_result,
            )
            log_event(None, "ai_rejected", "worker", {"symbol": symbol, "reason": reason[:200]})
            log_guard_decision("ai_ensemble", "rejected", reason, symbol, {"rf_prob": ai_result.get("rf_prob")})
            return

    log_event(None, "ai_approved", "worker", {"symbol": symbol, "rf_prob": ai_result.get("rf_prob")})
    log_guard_decision("ai_ensemble", "approved", ai_result.get("reason", "GO")[:200], symbol, {"rf_prob": ai_result.get("rf_prob")})

    # If we reach here, either AI said GO or shadow mode is allowing it.
    payload["ai_reasoning"] = ai_result
    payload["ai_decision"] = ai_result.get("decision")
    try:
        payload["ai_confidence"] = round(float(ai_result.get("rf_prob", 0.0)) * 100, 1)
    except Exception:
        pass

    win_prob = float(ai_result.get("rf_prob", 0.0))
    dry_run = not getattr(s, "live_trading_enabled", False)

    # Multi-account: execute for each matching profile (or single default)
    from src.core.broker_profiles import get_active_profiles

    profiles = get_active_profiles()
    payload_run_mode = str(payload.get("run_mode", "PAPER")).upper()
    matching = [p for p in profiles if (p.get("run_mode") or "LIVE") == payload_run_mode]
    if not matching:
        matching = [None]  # fallback: one call with profile=None (single-account from settings)

    trade_key = (payload.get("trade_key") or "").strip()
    for profile in matching:
        profile_id = profile.get("id") if profile else None
        if trade_key and _exists_trade_key(trade_key, profile_id):
            logger.info("Idempotency: (trade_key=%s, profile_id=%s) exists, skipping", trade_key, profile_id)
            continue
        try:
            if dry_run:
                logger.info("DRY_RUN: LIVE_TRADING=false — saving alert + notify only")
            log_event(None, "execution_started", "worker", {"symbol": symbol, "dry_run": dry_run, "profile": (profile or {}).get("name")})
            logic.process_trade(payload, dry_run=dry_run, ai_result=ai_result, profile=profile)
            logger.info("logic.process_trade completed for profile %s", (profile or {}).get("name") or "default")
        except Exception as exec_err:
            logger.error("logic.process_trade failed: %s", exec_err)
            log_event(None, "execution_failed", "worker", {"symbol": symbol, "error": str(exec_err)[:200], "profile": (profile or {}).get("name")})
            save_result(
                payload,
                "execution_failed",
                f"logic.process_trade: {str(exec_err)[:80]}",
                win_prob,
                ai_reasoning=ai_result,
                broker_profile_id=profile_id,
            )


def run():
    init_connections()
    load_brain()
    s = get_settings()
    kill_sw = getattr(s, "trading_kill_switch", False)
    live = getattr(s, "live_trading_enabled", False)
    logger.info("=" * 60)
    logger.info("WORKER (DYNAMIC RISK MODE) STARTED")
    logger.info("Account Balance: $%s", f"{s.account_balance:,.0f}")
    logger.info("Risk Per Trade: %s%%", s.risk_percent)
    logger.info("Correlation Limit: %s positions", MAX_OPEN_POSITIONS)
    logger.info("ML Confidence: %s", f"{ML_MIN_CONFIDENCE:.0%}")
    logger.info("Kill-Switch: %s", "ON" if kill_sw else "OFF")
    logger.info("LIVE_TRADING: %s", "true" if live else "false")
    logger.info("--- Pine Pre-Filters ---")
    logger.info("Min Score: %s | Min Grade: %s", s.pine_min_score, s.pine_min_grade)
    logger.info("Liq Swept Required: %s", s.pine_require_liq_swept)
    logger.info("Min Departure Str: %s | Min Return Str: %s", s.pine_min_departure_strength, s.pine_min_return_strength)
    logger.info("Dead Zone Block: %s | Hours: %s-%s UTC", s.pine_block_dead_zone, s.pine_trading_start_hour, s.pine_trading_end_hour)
    logger.info("Max Trades/Day: %s | Min R:R: %s", s.pine_max_trades_per_day, s.min_rr_ratio)
    logger.info("=" * 60)

    backoff = 5
    watchdog = TradeWatchdog(supabase_client=supabase)
    from src.services.alert_engine import AlertEngine
    alert_engine = AlertEngine(supabase_client=supabase)
    last_watchdog_ts = time.time()
    while True:
        task = None
        payload_str = None
        try:
            redis_client = get_redis()
            # Periodic watchdog + alert engine: every 60 seconds
            now = time.time()
            if now - last_watchdog_ts >= 60:
                try:
                    watchdog.run_sync()
                except Exception as w_exc:  # noqa: BLE001
                    logger.error("TradeWatchdog run failed: %s", w_exc)
                try:
                    alert_engine.evaluate_all()
                except Exception as a_exc:  # noqa: BLE001
                    logger.error("AlertEngine run failed: %s", a_exc)
                finally:
                    last_watchdog_ts = now

            task = redis_client.blpop(QUEUE_NAME, timeout=5)
            backoff = 5
            if task is None:
                continue
            _key, payload_str = task
            payload = json.loads(payload_str)
            if payload.get("event_type") == "exit":
                logger.info("Exit event for zone_id=%s - processing", payload.get("zone_id"))
            process_trade(payload)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from queue: %s", e)
            continue
        except (ConnectionError, OSError) as e:
            logger.error("Redis connection error: %s (reconnecting)", e)
            try:
                reset_redis_client()
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            logger.error("Loop error: %s", e)
            try:
                if "redis" in type(e).__module__.lower() or "ConnectionError" in type(e).__name__:
                    reset_redis_client()
            except Exception:
                pass
            try:
                if task is not None and payload_str is not None:
                    push_dead_letter(payload_str, str(e))
                    log_event(None, "dead_lettered", "worker", {"error": str(e)[:200]})
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
