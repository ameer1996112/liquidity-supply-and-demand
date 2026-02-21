"""
Trade Executor (Consumer) - Orchestrator.
Guards: kill-switch, idempotency, risk, correlation, AI. On pass: logic.process_trade.

Architecture (v2 - multi-account isolated):
  Global guards (run once):  kill-switch(env), max-lot, staleness, AI ensemble
  Per-account guards (run inside account loop): kill-switch(Redis/MTM), circuit-breaker,
      PropGuard, correlation, VaR, sector, consistency
  Execution: accounts run in parallel via ThreadPoolExecutor
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from src.services.trailing_stop_manager import TrailingStopManager
from src.core.dynamic_config import get_dynamic_setting, clear_settings_cache, apply_time_based_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("TRINITY_WORKER")

MAX_OPEN_POSITIONS = 3
# NOTE: Actual RF threshold is settings.ml_min_confidence (default 0.60).
# This constant is only used in _build_ml_rejection_reasoning for legacy logging.
ML_MIN_CONFIDENCE = 0.60

# ═══════════════════════════════════════════════════════════════
# SYMBOL WHITELIST: Only trade profitable symbols (3:1 R:R)
# ═══════════════════════════════════════════════════════════════
# Based on backtest analysis (see ml/analyze_symbol_performance.py):
# - XAUUSD: 37.4% WR, EV +0.121 at 2:1 (best performer)
# - Most symbols: profitable at 3:1 R:R
# - AUDUSD, XAGUSD: Unprofitable even at 3:1 (excluded)
#
# To disable whitelist: Set SYMBOL_WHITELIST_ENABLED = False
# ═══════════════════════════════════════════════════════════════
SYMBOL_WHITELIST_ENABLED = True  # Set to False to allow all symbols
PROFITABLE_SYMBOLS = {
    # High performers (profitable at 2:1 R:R)
    "XAUUSD",     # 37.4% WR, EV +0.121

    # Medium performers (profitable at 3:1 R:R)
    "USDJPY",     # 33.2% WR, EV +0.330
    "USDCAD",     # 32.6% WR, EV +0.305
    "GBPAUD",     # 30.9% WR, EV +0.236
    "GBPCAD",     # 28.9% WR, EV +0.156
    "EURGBP",     # 28.4% WR, EV +0.137
    "NZDUSD",     # 28.3% WR, EV +0.132
    "EURUSD",     # 27.6% WR, EV +0.103
    "GBPJPY",     # 27.3% WR, EV +0.090
    "BTCUSD",     # 26.9% WR, EV +0.076
    "EURJPY",     # 26.8% WR, EV +0.073
    "ETHUSD",     # 26.2% WR, EV +0.047

    # Indices (add as you test them)
    "NAS100", "US100",  # Nasdaq
    "SPX500", "US500",  # S&P 500
    "US30",             # Dow Jones
    "GER40",            # DAX

    # EXCLUDED (unprofitable even at 3:1):
    # "AUDUSD",   # 24.8% WR, EV -0.007
    # "XAGUSD",   # 24.2% WR, EV -0.033
}

supabase = None
correlation_manager = None
trailing_stop_manager = None
settings = None  # Global settings instance


def init_connections():
    global supabase, correlation_manager, trailing_stop_manager, settings
    r = get_redis()
    s = get_settings()
    settings = s  # Store in global for use in save_result
    raw_key = s.supabase_service_role_key or s.supabase_key or ""
    key = raw_key.strip().strip('"\'').strip()
    if key.upper().startswith("SUPA") and "=" in key[:50]:
        key = key.split("=", 1)[-1].strip().strip('"\'').strip()
        
    if s.supabase_url and key:
        logger.info(f"Supabase Auth Initializing | Key Length: {len(key)} | Prefix: '{key[:10]}'")
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

    # Initialize trailing stop manager
    if supabase:
        try:
            from src.adapters.execution.router import get_adapter
            adapter = get_adapter(run_mode=s.run_mode, settings=s)
            trailing_stop_manager = TrailingStopManager(supabase, adapter)
            logger.info("TrailingStopManager initialized")
        except Exception as exc:
            logger.warning("TrailingStopManager init failed: %s", exc)

    # ✅ v5.1: Load custom symbol mappings from database
    if supabase:
        try:
            from src.services.symbol_mapper import SymbolMapper
            SymbolMapper.load_from_database(supabase)
            logger.info("SymbolMapper initialized (custom mappings loaded)")
        except Exception as exc:
            logger.warning("SymbolMapper failed to load custom mappings: %s", exc)


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
        "liquidity_distance_pips", "liquidity_spread_pips",
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
        "liquidity_distance_pips": columns.get("liquidity_distance_pips"),
        "liquidity_spread_pips": columns.get("liquidity_spread_pips"),
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
    account_name: Optional[str] = None,
):
    if not supabase:
        logger.warning("Supabase unavailable - result not saved: %s", status)
        return

    # Use global settings instance
    default_balance = settings.account_balance if settings else 50000

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
        "account_balance": float(payload.get("account_balance", default_balance)),
    }
    tk = (payload.get("trade_key") or "").strip()
    if tk:
        data["trade_key"] = tk
    if broker_profile_id is not None:
        data["broker_profile_id"] = broker_profile_id
    if account_name is not None:
        data["account_name"] = account_name

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


# Futures symbols (Mangoe rules: BOC or Directional Close primary; Flip only on 15m/1H boundary)
_FUTURES_SYMBOLS = frozenset({"CL", "NQ", "GC", "ES", "YM", "RTY", "XAUUSD", "XAU", "GOLD", "USOIL", "UKOIL"})


def _is_futures_symbol(symbol: str) -> bool:
    """True if symbol is a Future (Crude, Nasdaq, Gold, etc.) for Mangoe rules."""
    if not symbol:
        return False
    u = symbol.upper().strip()
    if u in _FUTURES_SYMBOLS:
        return True
    # Prefix match for broker suffixes (e.g. CL.c, NQZ4, GCJ24, XAUUSD.a)
    for prefix in ("CL", "NQ", "GC", "ES", "YM", "RTY", "XAU"):
        if u.startswith(prefix) or u.startswith(prefix + ".") or u.startswith(prefix + " "):
            return True
    if "XAU" in u or "GOLD" in u:
        return True
    return False


def _validate_futures_entry_model(payload: Dict[str, Any]) -> Optional[str]:
    """Enforce Mangoe Futures entry rules: BOC or Directional Close primary; reject Flip unless on 15m/1H boundary.

    For Futures (CL, NQ, GC, XAUUSD, etc.):
    - Prefer Break of Candle or Directional Close.
    - FLIP entries are only allowed when bar_time is on a 15-min boundary (00/15/30/45).
    Returns None if valid or not a Futures symbol, rejection reason string otherwise.
    """
    symbol = (payload.get("symbol") or "").strip()
    if not _is_futures_symbol(symbol):
        return None

    entry_model = str(payload.get("entry_model", "")).strip().lower()
    if not entry_model:
        return None  # No model info — allow (Pine may not send it)

    # BOC / Directional Close / Break of Candle / Dir Close — allow
    if any(x in entry_model for x in ("boc", "break", "directional", "dir_close", "dir close")):
        return None

    # FLIP: require 15m/1H boundary (strict for Futures — do not fail-open on missing bar_time)
    if "flip" in entry_model:
        bar_time = payload.get("bar_time")
        if not bar_time or not isinstance(bar_time, str):
            return (
                "Futures (Mangoe): FLIP entry requires bar_time for 15m/1H boundary check. "
                "Use Break of Candle or Directional Close, or ensure Flip occurs on 15m/1H candle open."
            )
        reason = _validate_flip_timing(payload)
        if reason:
            return f"Futures (Mangoe): {reason}"
        return None

    return None  # Other models (e.g. AUTO) — allow


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


def _get_account_daily_pnl(profile: Optional[Dict[str, Any]] = None) -> float:
    """Fetch today's closed PnL scoped to a specific account (or global fallback)."""
    if not supabase:
        return 0.0
    try:
        from datetime import date, datetime
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        q = supabase.table("trading_signals").select("pnl_usd").eq("status", "closed").gte("created_at", today_start)
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])
        pnl_resp = q.execute()
        return sum(float(t.get("pnl_usd") or 0) for t in (pnl_resp.data or []))
    except Exception:
        return 0.0


def _get_account_positions_from_db(profile: Optional[Dict[str, Any]] = None) -> list:
    """Fetch active positions scoped to a specific account."""
    try:
        import src.adapters.supabase as supabase_db
        if not supabase_db.supabase:
            supabase_db.init_supabase()
        q = supabase_db.supabase.table("trading_signals").select(
            "symbol, side, size, entry, created_at, zone_id, trade_key"
        ).in_("status", ["active", "executed"])
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])
        response = q.execute()
        from src.core.guard_rails.correlation import ActivePosition
        from datetime import datetime
        positions = []
        for row in response.data:
            positions.append(ActivePosition(
                symbol=row.get("symbol", "UNKNOWN"),
                side=row.get("side", "buy"),
                size=float(row.get("size", 0)),
                entry_price=float(row.get("entry", 0)),
                entry_time=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
                zone_id=row.get("zone_id"),
                trade_key=row.get("trade_key"),
            ))
        return positions
    except Exception as e:
        logger.error("Failed to fetch account positions: %s", e)
        return []


def _run_account_guards(
    payload: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    s,
    current_equity_global: float,
) -> Optional[str]:
    """Run per-account guards. Returns rejection reason or None if all pass.

    These guards are scoped to a specific broker profile so one account's
    state doesn't interfere with another.
    """
    symbol = payload.get("symbol", "UNKNOWN")
    side = payload.get("side", "buy")
    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    profile_id = profile.get("id") if profile else None
    account_name = (profile.get("name") if profile else None) or "default"
    profile_risk_pct = float(profile.get("risk_pct", s.risk_percent)) if profile else s.risk_percent

    # ── Per-account kill switch (Redis + MTM) ─────────────────
    try:
        from src.adapters.redis_queue import get_redis as _get_redis
        acct_kill_key = f"trading:kill_switch:{account_name}" if account_name != "default" else "trading:kill_switch"
        if _get_redis().get(acct_kill_key) == "1":
            return f"Kill switch ON for account {account_name}"
    except Exception:
        pass

    # MTM Guardian (per-account)
    if supabase and getattr(s, "mtm_guardian_enabled", True):
        try:
            from src.services.mtm_guardian import MTMGuardian
            # Use per-account starting balance if available
            acct_balance = float(payload.get("account_balance", s.account_balance))
            mtm_guardian = MTMGuardian(supabase, s, starting_balance=acct_balance)
            mtm_kill, mtm_reason = mtm_guardian.check_kill_switch(
                account_name=account_name,
                broker_profile_id=profile_id,
            )
            if mtm_kill:
                try:
                    from src.adapters.redis_queue import get_redis as _get_redis
                    kill_key = f"trading:kill_switch:{account_name}" if account_name != "default" else "trading:kill_switch"
                    _get_redis().set(kill_key, "1")
                    logger.critical("MTM KILL SWITCH ENGAGED for %s: %s", account_name, mtm_reason)
                except Exception:
                    pass
                return mtm_reason
        except Exception as e:
            logger.error("MTM Guardian check failed for %s: %s", account_name, e)

    # ── Per-account circuit breaker ───────────────────────────
    if run_mode == "LIVE":
        try:
            from src.core.circuit_breaker import is_metaapi_circuit_open
            if is_metaapi_circuit_open(account_name=account_name):
                return f"Circuit breaker open for account {account_name}"
        except Exception:
            pass

    # ── Per-account PropGuard ─────────────────────────────────
    acct_balance = float(payload.get("account_balance", s.account_balance))
    daily_pnl = _get_account_daily_pnl(profile)
    current_equity = acct_balance + daily_pnl

    allowed, risk_multiplier, risk_label = check_safety(
        current_equity, acct_balance, daily_pnl,
        account_name=account_name,
        risk_pct_override=profile_risk_pct,
    )
    if not allowed:
        return f"PropGuard ({account_name}): {risk_label}"
    logger.info("PropGuard [%s]: %s (multiplier=%.2f)", account_name, risk_label, risk_multiplier)
    # Store per-account risk multiplier
    payload[f"_risk_multiplier_{account_name}"] = risk_multiplier

    # ── Per-account Correlation Guard ─────────────────────────
    active_positions = _get_account_positions_from_db(profile)
    max_pos = (profile.get("max_positions") if profile else None) or s.trinity_max_positions

    if correlation_manager:
        try:
            corr_result = correlation_manager.check(symbol=symbol, side=side, active_positions=active_positions)
            if not corr_result.passed:
                return f"Correlation ({account_name}): {corr_result.rejection_message}"
            logger.info("Correlation [%s]: %s/%s active — PASSED", account_name, len(active_positions), max_pos)
        except Exception as e:
            logger.error("Correlation guard crashed for %s: %s", account_name, e)
            return f"Correlation error ({account_name}): {str(e)[:50]}"
    elif len(active_positions) >= max_pos:
        return f"Bucket Full ({account_name}): {len(active_positions)}/{max_pos}"

    # ── Per-account Consistency Analyzer ──────────────────────
    if getattr(s, "evaluation_mode", False) and supabase:
        try:
            from src.services.consistency_analyzer import ConsistencyAnalyzer
            consistency = ConsistencyAnalyzer(supabase, s)
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

    return None  # All account-level guards passed


def _execute_for_profile(
    payload: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    ai_result: Dict[str, Any],
    dry_run: bool,
    s,
    current_equity_global: float,
) -> None:
    """Run per-account guards then execute for a single broker profile."""
    profile_id = profile.get("id") if profile else None
    account_name = (profile.get("name") if profile else None) or "default"
    symbol = payload.get("symbol", "UNKNOWN")
    win_prob = float(ai_result.get("rf_prob", 0.0))
    trade_key = (payload.get("trade_key") or "").strip()

    # Idempotency check per-profile
    if trade_key and _exists_trade_key(trade_key, profile_id):
        logger.info("Idempotency: (trade_key=%s, profile=%s) exists, skipping", trade_key, account_name)
        return

    # Apply per-account risk multiplier from guard phase
    acct_multiplier_key = f"_risk_multiplier_{account_name}"
    if acct_multiplier_key in payload:
        payload["_risk_multiplier"] = payload[acct_multiplier_key]

    # Run per-account guards
    rejection = _run_account_guards(payload, profile, s, current_equity_global)
    if rejection:
        save_result(payload, "risk_rejected", rejection, 0.0, broker_profile_id=profile_id, account_name=account_name)
        log_guard_decision("account_guard", "rejected", rejection, symbol)
        logger.warning("ACCOUNT GUARD BLOCKED [%s]: %s", account_name, rejection)
        return

    # Execute
    try:
        if dry_run:
            logger.info("DRY_RUN [%s]: LIVE_TRADING=false — saving alert + notify only", account_name)
        log_event(None, "execution_started", "worker", {"symbol": symbol, "dry_run": dry_run, "profile": account_name})
        logic.process_trade(payload, dry_run=dry_run, ai_result=ai_result, profile=profile)
        logger.info("logic.process_trade completed for profile %s", account_name)
    except Exception as exec_err:
        logger.error("logic.process_trade failed for %s: %s", account_name, exec_err)
        log_event(None, "execution_failed", "worker", {"symbol": symbol, "error": str(exec_err)[:200], "profile": account_name})
        save_result(
            payload,
            "execution_failed",
            f"logic.process_trade: {str(exec_err)[:80]}",
            win_prob,
            ai_reasoning=ai_result,
            broker_profile_id=profile_id,
            account_name=account_name,
        )


def process_trade(payload: Dict[str, Any]):
    symbol = payload.get("symbol", "UNKNOWN")
    side = payload.get("side", "buy")
    size = float(payload.get("size", 0.01))
    logger.info("Processing: %s | %s | Size: %s", symbol, side.upper(), size)

    s = get_settings()

    # ══════════════════════════════════════════════════════════════════
    # SYMBOL WHITELIST CHECK (Block unprofitable symbols)
    # ══════════════════════════════════════════════════════════════════
    if SYMBOL_WHITELIST_ENABLED and symbol.upper() not in PROFITABLE_SYMBOLS:
        rejection = f"Symbol {symbol} not in profitable whitelist (see PROFITABLE_SYMBOLS in worker.py)"
        logger.warning("❌ SYMBOL WHITELIST BLOCKED: %s", rejection)
        save_result(payload, "symbol_blacklisted", rejection, 0.0)
        log_guard_decision("symbol_whitelist", "rejected", rejection, symbol)
        return

    # ── Determine account_name early for tracking rejected signals ────
    from src.core.broker_profiles import get_active_profiles

    account_name = None
    payload_run_mode = str(payload.get("run_mode", "PAPER")).upper()
    try:
        profiles = get_active_profiles()
        matching = [p for p in profiles if (p.get("run_mode") or "LIVE") == payload_run_mode]
        if matching and matching[0].get("name"):
            account_name = matching[0]["name"]
            logger.info("Account: %s (mode: %s)", account_name, payload_run_mode)
    except Exception as e:
        logger.warning("Failed to determine account_name: %s", e)

    # ── Dynamic Risk Controls: Check for time-based rules & DB overrides ────
    time_based_multiplier = apply_time_based_rules()
    if time_based_multiplier is not None and time_based_multiplier < 1.0:
        logger.info(f"Time-based risk rule active: reducing risk by {(1.0 - time_based_multiplier) * 100:.0f}%")
        payload["_time_risk_multiplier"] = time_based_multiplier

    # ══════════════════════════════════════════════════════════════════
    # GLOBAL GUARDS (run once, affect all accounts)
    # ══════════════════════════════════════════════════════════════════

    # ── Invalid size (e.g. TradingView sent size=0 or risk engine returned 0) ──────
    if size <= 0 or not isinstance(payload.get("size"), (int, float)):
        # ✅ v5.1: Provide detailed error explanation
        entry = float(payload.get("entry", 0))
        sl = float(payload.get("sl", 0))
        sl_distance = abs(entry - sl) if entry and sl else 0
        account_balance = float(payload.get("account_balance", s.account_balance))
        risk_pct = float(payload.get("risk_percent", s.risk_percent))

        rejection_reason = (
            f"Position size must be positive (got size={payload.get('size')}). "
        )

        # Diagnose the root cause
        if sl_distance > 0:
            # Calculate what the min account balance would need to be
            min_lot = 0.01  # Typical broker minimum
            pip_size = 0.01 if "JPY" in symbol.upper() else 0.0001
            sl_pips = sl_distance / pip_size
            pip_value = 10.0  # Approximate for forex
            min_risk_needed = min_lot * sl_pips * pip_value
            min_balance_needed = (min_risk_needed / (risk_pct / 100))

            rejection_reason += (
                f"This usually means the stop loss is TOO WIDE relative to account size. "
                f"Details: SL distance={sl_distance:.5f} ({sl_pips:.1f} pips), "
                f"Account balance=${account_balance:.2f}, Risk={risk_pct}%. "
                f"To place min trade (0.01 lots), you need ~${min_balance_needed:.0f} account balance "
                f"OR reduce SL distance by {(sl_pips / 50):.0f}x. "
                f"Alternatively, check TradingView Pine 'account_size_usd' input (should match ${account_balance:.0f}, not initial_capital)."
            )
        else:
            rejection_reason += (
                "Missing entry/SL prices. Check TradingView webhook payload."
            )

        save_result(
            payload,
            "filtered",
            rejection_reason,
            0.0,
            account_name=account_name,
        )
        logger.warning(
            "SIZE REJECTED: size=%s (must be > 0). Reason: %s",
            payload.get("size"),
            rejection_reason[:200],
        )
        return

    # ── Max Lot Size Guard ────────────────────────────────────
    max_lot_size = s.max_lot_size if hasattr(s, 'max_lot_size') else 10.0
    if size > max_lot_size:
        save_result(
            payload,
            "filtered",
            f"Position size {size} lots exceeds max_lot_size={max_lot_size}. "
            f"Check TradingView Pine initial_capital vs actual account balance.",
            0.0,
            account_name=account_name,
        )
        logger.warning(
            "MAX LOT SIZE REJECTED: size=%s > max=%s lots.",
            size,
            max_lot_size,
        )
        return

    # ── Futures (Mangoe) entry model: BOC/Dir Close preferred; Flip only on 15m/1H boundary ──
    futures_reason = _validate_futures_entry_model(payload)
    if futures_reason:
        save_result(payload, "filtered", futures_reason, 0.0, account_name=account_name)
        log_guard_decision("futures_entry_model", "rejected", futures_reason, symbol)
        logger.warning("FUTURES ENTRY MODEL REJECTED: %s", futures_reason)
        return

    # ── Global Kill Switch (ENV only — Redis/MTM are now per-account) ──
    env_kill = getattr(s, "trading_kill_switch", False)
    if env_kill:
        reason = "Trading kill-switch is ON (env)"
        save_result(payload, "kill_switch_blocked", reason, 0.0, account_name=account_name)
        log_event(None, "kill_switch_blocked", "worker", {"symbol": symbol, "reason": reason})
        log_guard_decision("kill_switch", "blocked", reason, symbol)
        logger.warning("KILL-SWITCH: execution blocked - %s", reason)
        return

    # ── Signal Staleness Guard (global — same signal for all accounts) ──
    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    if run_mode == "LIVE" and getattr(s, "enable_staleness_guard", True):
        try:
            from src.core.guard_rails.staleness_guard import StalenessGuard
            staleness_guard = StalenessGuard(
                max_age_seconds=getattr(s, "staleness_max_age_seconds", 5),
                max_price_deviation_pips=getattr(s, "staleness_max_price_deviation_pips", 3.0)
            )
            passed, reason = staleness_guard.check(payload)
            if not passed:
                save_result(payload, "staleness_rejected", reason, 0.0, account_name=account_name)
                log_event(None, "staleness_rejected", "worker", {"symbol": symbol, "reason": reason})
                log_guard_decision("staleness", "rejected", reason, symbol)
                logger.warning("STALENESS REJECTED: %s", reason)
                return
            logger.info("Staleness Guard: PASSED")
        except Exception as e:
            logger.error("Staleness guard crashed: %s", e, exc_info=True)

    # ══════════════════════════════════════════════════════════════════
    # AI ENSEMBLE DECISION (global — same decision for all accounts)
    # Pine pre-filters REMOVED: Pine Script handles entry rules directly.
    # The AI ensemble adds ML-based optimization on top of Pine signals.
    # ══════════════════════════════════════════════════════════════════
    ai_result = ensemble_decision(payload)

    # Enrich AI result with zone/sweep/metrics from original payload
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
        "liquidity_distance_pips": "liquidity_distance_pips",
        "liquidity_spread_pips": "liquidity_spread_pips",
    }
    for src_key, dst_key in _ZONE_FIELD_MAP.items():
        val = payload.get(src_key)
        if val is not None and dst_key not in ai_result:
            ai_result[dst_key] = val

    logger.info(
        "BRAIN DECISION: decision=%s rf=%.4f rag_rules=%d reason=%s",
        ai_result.get("decision"),
        ai_result.get("rf_prob", 0.0),
        len(ai_result.get("rules") or []),
        ai_result.get("reason", ""),
    )

    decision = str(ai_result.get("decision", "NO_GO")).upper()
    shadow_mode = bool(getattr(s, "run_shadow_mode", False))

    if decision in {"NO_GO", "MODEL_ERROR"}:
        if shadow_mode:
            logger.warning("SHADOW MODE: Executing trade despite AI decision=%s.", decision)
        else:
            reason = ai_result.get("reason", "AI ensemble rejected trade.")
            status = "ai_rejected" if decision == "NO_GO" else "model_error"
            save_result(
                payload,
                status,
                reason,
                float(ai_result.get("rf_prob", 0.0)),
                ai_reasoning=ai_result,
                account_name=account_name,
            )
            log_event(
                None,
                "ai_rejected" if decision == "NO_GO" else "model_error",
                "worker",
                {"symbol": symbol, "reason": reason[:200]},
            )
            log_guard_decision(
                "ai_ensemble",
                "rejected" if decision == "NO_GO" else "model_error",
                reason,
                symbol,
                {"rf_prob": ai_result.get("rf_prob"), "decision": decision},
            )
            return

    log_event(None, "ai_approved", "worker", {"symbol": symbol, "rf_prob": ai_result.get("rf_prob")})
    log_guard_decision("ai_ensemble", "approved", ai_result.get("reason", "GO")[:200], symbol, {"rf_prob": ai_result.get("rf_prob")})

    payload["ai_reasoning"] = ai_result
    payload["ai_decision"] = ai_result.get("decision")
    try:
        payload["ai_confidence"] = round(float(ai_result.get("rf_prob", 0.0)) * 100, 1)
    except Exception:
        pass

    dry_run = not getattr(s, "live_trading_enabled", False)

    # Global equity estimate for VaR/sector (pre-account loop)
    dynamic_account_balance = float(payload.get("account_balance", s.account_balance))
    global_daily_pnl = _get_account_daily_pnl(None)
    current_equity_global = dynamic_account_balance + global_daily_pnl

    # ══════════════════════════════════════════════════════════════════
    # MULTI-ACCOUNT EXECUTION (parallel — each account isolated)
    # Per-account guards (kill switch, circuit breaker, PropGuard,
    # correlation, consistency) run inside each profile's execution.
    # ══════════════════════════════════════════════════════════════════
    from src.core.broker_profiles import get_active_profiles

    profiles = get_active_profiles()
    payload_run_mode = str(payload.get("run_mode", "PAPER")).upper()
    matching = [p for p in profiles if (p.get("run_mode") or "LIVE") == payload_run_mode]
    if not matching:
        matching = [None]

    if len(matching) == 1:
        # Single account: run directly (no thread overhead)
        _execute_for_profile(payload.copy(), matching[0], ai_result, dry_run, s, current_equity_global)
    else:
        # Multiple accounts: execute in parallel
        logger.info("Multi-account execution: %d profiles matched", len(matching))
        with ThreadPoolExecutor(max_workers=min(len(matching), 5)) as executor:
            futures = {
                executor.submit(
                    _execute_for_profile,
                    payload.copy(),
                    profile,
                    ai_result,
                    dry_run,
                    s,
                    current_equity_global,
                ): (profile or {}).get("name", "default")
                for profile in matching
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.error("Profile %s execution error: %s", name, exc)


def run():
    init_connections()
    load_brain()
    s = get_settings()
    kill_sw = getattr(s, "trading_kill_switch", False)
    live = getattr(s, "live_trading_enabled", False)
    logger.info("=" * 60)
    logger.info("WORKER v2 (MULTI-ACCOUNT ISOLATED) STARTED")
    logger.info("Account Balance: $%s", f"{s.account_balance:,.0f}")
    logger.info("Risk Per Trade: %s%%", s.risk_percent)
    logger.info("Correlation Limit: %s positions", s.trinity_max_positions)
    logger.info("AI Ensemble: %s | Shadow: %s", "ON", "ON" if getattr(s, "run_shadow_mode", False) else "OFF")
    logger.info("Kill-Switch: %s", "ON" if kill_sw else "OFF")
    logger.info("LIVE_TRADING: %s", "true" if live else "false")
    logger.info("Evaluation Mode: %s", "ON" if getattr(s, "evaluation_mode", False) else "OFF")
    logger.info("--- Guards ---")
    logger.info("Global: kill-switch(env), max-lot, staleness, AI ensemble")
    logger.info("Per-account: kill-switch(Redis/MTM), circuit-breaker, PropGuard, correlation, consistency")
    logger.info("Pine pre-filters: DISABLED (Pine Script handles entry rules)")
    logger.info("R:R filter: %s", f"ON (min={s.min_rr_ratio})" if s.min_rr_ratio > 0 else "OFF (Pine handles SL/TP)")
    logger.info("=" * 60)

    backoff = 5
    watchdog = TradeWatchdog(supabase_client=supabase)
    from src.services.alert_engine import AlertEngine
    alert_engine = AlertEngine(supabase_client=supabase)

    # Initialize daily reset scheduler for prop firm metrics
    daily_reset_scheduler = None
    if supabase and getattr(s, "evaluation_mode", False):
        try:
            from src.services.daily_reset_scheduler import DailyResetScheduler
            daily_reset_scheduler = DailyResetScheduler(supabase, s)
            logger.info("📊 Daily reset scheduler initialized for prop firm tracking")
        except Exception as exc:
            logger.warning("Daily reset scheduler init failed: %s", exc)

    last_watchdog_ts = time.time()
    while True:
        task = None
        payload_str = None
        try:
            redis_client = get_redis()
            # Periodic tasks: every 60 seconds (watchdog, alerts, trailing stops, config refresh)
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

                # Update trailing stops
                if trailing_stop_manager:
                    try:
                        trailing_stop_manager.update_trailing_stops()
                    except Exception as ts_exc:  # noqa: BLE001
                        logger.error("TrailingStopManager update failed: %s", ts_exc)

                # Clear config cache to pick up DB changes
                try:
                    clear_settings_cache()
                except Exception as cfg_exc:  # noqa: BLE001
                    logger.error("Config cache clear failed: %s", cfg_exc)

                # Check and execute daily reset for prop firm metrics
                if daily_reset_scheduler:
                    try:
                        daily_reset_scheduler.check_and_execute_reset()
                    except Exception as reset_exc:  # noqa: BLE001
                        logger.error("Daily reset check failed: %s", reset_exc)

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
