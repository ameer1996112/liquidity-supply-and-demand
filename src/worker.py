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
from src.adapters.redis_queue import QUEUE_NAME, get_redis
from src.ai.brain import ensemble_decision, get_prediction, load_brain
from src.core.risk_engine import calculate_max_position_size as _calculate_max_position_size_impl
from src import logic
from src.services.watchdog import TradeWatchdog

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("TRINITY_WORKER")

MAX_OPEN_POSITIONS = 3
ML_MIN_CONFIDENCE = 0.50

supabase = None


def init_connections():
    global supabase
    r = get_redis()
    s = get_settings()
    key = (s.supabase_service_role_key or s.supabase_key).strip()
    if s.supabase_url and key:
        from supabase import create_client
        supabase = create_client(s.supabase_url, key)
        logger.info("Supabase connected")
    else:
        logger.warning("Supabase credentials missing - logging disabled")


def _exists_trade_key(trade_key: str) -> bool:
    if not trade_key or not str(trade_key).strip() or not supabase:
        return False
    try:
        r = supabase.table("trading_signals").select("id").eq("trade_key", trade_key.strip()).limit(1).execute()
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
    return _calculate_max_position_size_impl(
        payload,
        account_balance=float(payload.get("account_balance", s.account_balance)),
        risk_percent=float(payload.get("risk_percent", s.risk_percent)),
        symbol_overrides=symbol_overrides,
    )


# Single-arg API for tests and callers that pass balance/risk via payload or settings
def calculate_max_position_size(payload: Dict[str, Any]) -> float:
    """Max allowed lot size for payload (uses settings for balance/risk)."""
    return _max_position_size(payload)


def save_result(payload: Dict[str, Any], status: str, note: str, prob: float, ai_reasoning: Optional[Dict[str, Any]] = None):
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
        "run_mode": payload.get("run_mode", "LIVE"),
    }
    tk = (payload.get("trade_key") or "").strip()
    if tk:
        data["trade_key"] = tk
    if ai_reasoning:
        data["ai_reasoning"] = json.dumps(ai_reasoning)
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
    if getattr(s, "trading_kill_switch", False):
        save_result(payload, "kill_switch_blocked", "Trading kill-switch is ON", 0.0)
        logger.warning("KILL-SWITCH: execution blocked")
        return

    signal_id = payload.get("signal_id") or payload.get("trade_key")
    if signal_id and _exists_trade_key(signal_id):
        logger.info("Idempotency: signal_id/trade_key already exists, skipping")
        return

    # Pre-flight risk estimate (config balance — actual cap with live balance is in logic.py)
    max_allowed_size = _max_position_size(payload)
    logger.info("Risk Pre-Check (config balance): size %s vs estimate %s", size, round(max_allowed_size, 2))
    if size > max_allowed_size:
        logger.warning(
            "Size %s exceeds config-based estimate %s — logic.py will re-check with live balance",
            size,
            round(max_allowed_size, 2),
        )

    if supabase:
        try:
            active = supabase.table("trading_signals").select("id").eq("status", "active").execute()
            active_count = len(active.data)
            logger.info("Correlation Check: %s/%s active", active_count, MAX_OPEN_POSITIONS)
            if active_count >= MAX_OPEN_POSITIONS:
                save_result(payload, "correlation_rejected", f"Bucket Full ({active_count}/{MAX_OPEN_POSITIONS})", 0.0)
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
            # Block trade when not in shadow mode
            save_result(
                payload,
                "ai_rejected",
                ai_result.get("reason", "AI ensemble rejected trade."),
                float(ai_result.get("rf_prob", 0.0)),
                ai_reasoning=ai_result,
            )
            return

    # If we reach here, either AI said GO or shadow mode is allowing it.
    # Attach AI reasoning to the payload so it is persisted with the entry row.
    payload["ai_reasoning"] = ai_result
    payload["ai_decision"] = ai_result.get("decision")
    # Use RF probability (0-1) as a proxy for AI confidence in percent
    try:
        payload["ai_confidence"] = round(float(ai_result.get("rf_prob", 0.0)) * 100, 1)
    except Exception:
        pass

    win_prob = float(ai_result.get("rf_prob", 0.0))
    try:
        dry_run = not getattr(s, "live_trading_enabled", False)
        if dry_run:
            logger.info("DRY_RUN: LIVE_TRADING=false — saving alert + notify only")
        # Pass ai_result through so downstream notifications can render the brain matrix
        logic.process_trade(payload, dry_run=dry_run, ai_result=ai_result)
        logger.info("logic.process_trade completed")
    except Exception as exec_err:
        logger.error("logic.process_trade failed: %s", exec_err)
        save_result(
            payload,
            "execution_failed",
            f"logic.process_trade: {str(exec_err)[:80]}",
            win_prob,
            ai_reasoning=ai_result,
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
    redis_client = get_redis()
    watchdog = TradeWatchdog(supabase_client=supabase)
    last_watchdog_ts = time.time()
    while True:
        try:
            # Periodic watchdog: every 60 seconds, sync silent exits
            now = time.time()
            if now - last_watchdog_ts >= 60:
                try:
                    watchdog.run_sync()
                except Exception as w_exc:  # noqa: BLE001
                    logger.error("TradeWatchdog run failed: %s", w_exc)
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
        except Exception as e:
            logger.error("Loop error: %s", e)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
