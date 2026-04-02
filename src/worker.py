# ruff: noqa: E402
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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env from project root
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

from config import get_settings
from config.logging_config import configure_logging, get_logger
from src.adapters.redis_queue import get_redis
from src.core.transport import get_transport
from src.core.consumer_validator import validate_dequeued_message
from src.core.observers import (
    WorkerSubject,
    AuditorObserver,
    RiskObserver,
    ExecutorObserver,
    MetricsObserver,
    AccountRouterObserver,
)
from src.core.account_router import AccountRouter  # no observers dependency
from src.ai.brain import get_prediction, load_brain
from src.core.risk_engine import calculate_max_position_size as _calculate_max_position_size_impl
from src.core.guard_rails.correlation import (
    create_correlation_manager_from_settings,
)
from src.core.guard_rails.prop_guard import check_safety
from src.services.trade_events import log_event, log_guard_decision
from src import logic
from src.services.watchdog import TradeWatchdog
from src.services.trailing_stop_manager import TrailingStopManager
from src.services.breakeven_manager import BreakevenManager
from src.services.liquidity_scorer import LiquidityScorer
from src.core.dynamic_config import clear_settings_cache, apply_time_based_rules

configure_logging()
logger = get_logger("trinity.worker")

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
    "GBPUSD",     # Forex major
    "GBPJPY",     # 27.3% WR, EV +0.090
    "BTCUSD",     # 26.9% WR, EV +0.076
    "EURJPY",     # 26.8% WR, EV +0.073
    "ETHUSD",     # 26.2% WR, EV +0.047
    "NZDJPY",     # 28.5% WR, EV +0.133 (added 2026-03-05)

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
breakeven_manager = None
settings = None  # Global settings instance

# Supabase client rotation — recreate every 90s to prevent HTTP/2 connection staleness
_supabase_created_at: float = 0.0
_SUPABASE_MAX_AGE = 90  # seconds
_supabase_url: str = ""
_supabase_key: str = ""

# System trading mode cache — mirrors api.py's cache to avoid a DB hit on every signal
_system_mode_cache: dict = {"value": None, "loaded_at": 0.0}
_SYSTEM_MODE_CACHE_TTL = 30  # seconds

# HTF candle filter cache — DB overrides Pydantic defaults (30s TTL)
_htf_filter_cache: dict = {"enabled": None, "minutes": None, "period": None, "loaded_at": 0.0}

# 1-candle liquidity filter cache — DB overrides Pydantic defaults (30s TTL)
_one_candle_liq_cache: dict = {"enabled": None, "min_departure": None, "loaded_at": 0.0}


def _get_htf_filter_settings(s) -> tuple[bool, int, int]:
    """Return (htf_enabled, htf_block_minutes, htf_period) from DB (30s cache), falling back to Pydantic settings."""
    now = time.time()
    if now - _htf_filter_cache["loaded_at"] < _SYSTEM_MODE_CACHE_TTL and _htf_filter_cache["enabled"] is not None:
        return _htf_filter_cache["enabled"], _htf_filter_cache["minutes"], _htf_filter_cache["period"]
    try:
        sb = _get_fresh_supabase()
        if sb:
            rows = (
                sb.table("system_config")
                .select("key,value")
                .in_("key", ["pine_htf_candle_filter_enabled", "pine_htf_candle_block_minutes", "pine_htf_candle_period"])
                .execute()
            )
            kv = {r["key"]: r["value"] for r in (rows.data or [])}
            enabled = kv.get("pine_htf_candle_filter_enabled", None)
            minutes = kv.get("pine_htf_candle_block_minutes", None)
            period = kv.get("pine_htf_candle_period", None)
            htf_enabled = (enabled.lower() != "false") if enabled is not None else getattr(s, "pine_htf_candle_filter_enabled", True)
            htf_minutes = int(minutes) if minutes is not None else getattr(s, "pine_htf_candle_block_minutes", 10)
            htf_period = int(period) if period is not None else 15
            if htf_period not in (30, 60):
                htf_period = 30
        else:
            htf_enabled = getattr(s, "pine_htf_candle_filter_enabled", True)
            htf_minutes = getattr(s, "pine_htf_candle_block_minutes", 10)
            htf_period = 30
    except Exception:
        htf_enabled = getattr(s, "pine_htf_candle_filter_enabled", True)
        htf_minutes = getattr(s, "pine_htf_candle_block_minutes", 10)
        htf_period = 15
    _htf_filter_cache["enabled"] = htf_enabled
    _htf_filter_cache["minutes"] = htf_minutes
    _htf_filter_cache["period"] = htf_period
    _htf_filter_cache["loaded_at"] = now
    return htf_enabled, htf_minutes, htf_period


def _get_one_candle_liq_settings(s) -> tuple[bool, float]:
    """Return (block_enabled, min_departure) from DB (30s cache), falling back to Pydantic settings."""
    now = time.time()
    if now - _one_candle_liq_cache["loaded_at"] < _SYSTEM_MODE_CACHE_TTL and _one_candle_liq_cache["enabled"] is not None:
        return _one_candle_liq_cache["enabled"], _one_candle_liq_cache["min_departure"]
    try:
        sb = _get_fresh_supabase()
        if sb:
            rows = (
                sb.table("system_config")
                .select("key,value")
                .in_("key", ["pine_block_one_candle_liq", "pine_one_candle_liq_min_departure"])
                .execute()
            )
            kv = {r["key"]: r["value"] for r in (rows.data or [])}
            raw_enabled = kv.get("pine_block_one_candle_liq")
            raw_dep = kv.get("pine_one_candle_liq_min_departure")
            enabled = (raw_enabled.lower() != "false") if raw_enabled is not None else getattr(s, "pine_block_one_candle_liq", True)
            min_dep = float(raw_dep) if raw_dep is not None else getattr(s, "pine_one_candle_liq_min_departure", 60.0)
        else:
            enabled = getattr(s, "pine_block_one_candle_liq", True)
            min_dep = getattr(s, "pine_one_candle_liq_min_departure", 60.0)
    except Exception:
        enabled = getattr(s, "pine_block_one_candle_liq", True)
        min_dep = getattr(s, "pine_one_candle_liq_min_departure", 60.0)
    _one_candle_liq_cache["enabled"] = enabled
    _one_candle_liq_cache["min_departure"] = min_dep
    _one_candle_liq_cache["loaded_at"] = now
    return enabled, min_dep


# Singleton scorer — stateless, safe to share across threads
_liquidity_scorer = LiquidityScorer()


def _get_system_trading_mode() -> str:
    """Return the dashboard-authoritative trading mode from system_config (30s cache)."""
    now = time.time()
    if (
        now - _system_mode_cache["loaded_at"] < _SYSTEM_MODE_CACHE_TTL
        and _system_mode_cache["value"]
    ):
        return _system_mode_cache["value"]
    try:
        sb = _get_fresh_supabase()
        if sb:
            result = (
                sb.table("system_config")
                .select("value")
                .eq("key", "trading_mode")
                .single()
                .execute()
            )
            mode = result.data["value"] if result.data else "PAPER"
        else:
            mode = "PAPER"
    except Exception as e:
        logger.warning("Could not load system trading mode from DB, defaulting to PAPER: %s", e)
        mode = "PAPER"
    _system_mode_cache["value"] = mode.upper()
    _system_mode_cache["loaded_at"] = now
    return _system_mode_cache["value"]


def _get_fresh_supabase():
    """Return a Supabase client, recreating it every 90s to avoid stale HTTP/2 connections.

    supabase-py uses httpx which maintains HTTP/2 connections. These go stale after
    15-40 minutes (server-side timeouts), causing ConnectionTerminated error_code:1.
    Rotating the client every 90s ensures connections stay fresh.
    """
    global supabase, _supabase_created_at
    import time
    now = time.time()
    if supabase is not None and _supabase_url and (now - _supabase_created_at) < _SUPABASE_MAX_AGE:
        return supabase
    if not _supabase_url or not _supabase_key:
        return supabase  # fallback: no creds yet, return whatever we have
    try:
        from supabase import create_client
        supabase = create_client(_supabase_url, _supabase_key)
        _supabase_created_at = now
    except Exception as _e:
        logger.warning("Worker: failed to rotate Supabase client: %s", _e)
    return supabase


def init_connections():
    global supabase, correlation_manager, trailing_stop_manager, breakeven_manager, settings
    s = get_settings()
    settings = s  # Store in global for use in save_result
    raw_key = s.supabase_service_role_key or s.supabase_key or ""
    key = raw_key.strip().strip('"\'').strip()
    if key.upper().startswith("SUPA") and "=" in key[:50]:
        key = key.split("=", 1)[-1].strip().strip('"\'').strip()
        
    if s.supabase_url and key:
        logger.info("Supabase Auth Initializing | Key present: True")
        from supabase import create_client
        import time as _time
        global _supabase_url, _supabase_key, _supabase_created_at
        _supabase_url = s.supabase_url
        _supabase_key = key
        supabase = create_client(s.supabase_url, key)
        _supabase_created_at = _time.time()
        logger.info("Supabase connected")
    else:
        logger.warning("Supabase credentials missing - logging disabled")

    try:
        correlation_manager = create_correlation_manager_from_settings()
        logger.info("CorrelationManager initialized")
    except Exception as exc:
        logger.warning("CorrelationManager init failed (fallback to simple count): %s", exc)

    # Initialize trailing stop manager and breakeven manager
    if supabase:
        try:
            from src.adapters.execution.router import get_adapter
            adapter = get_adapter(run_mode=s.run_mode, settings=s)
            trailing_stop_manager = TrailingStopManager(supabase, adapter)
            breakeven_manager = BreakevenManager(supabase, adapter, trailing_stop_manager=trailing_stop_manager)
            logger.info("TrailingStopManager and BreakevenManager initialized (trailing stop auto-activation: enabled)")
        except Exception as exc:
            logger.warning("TrailingStopManager/BreakevenManager init failed: %s", exc)

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


def _claim_trade_key(trade_key: str, broker_profile_id: Optional[int] = None, ttl: int = 300) -> bool:
    """Atomically claim a trade_key via Redis SETNX before DB check.

    Returns True if this worker instance successfully claimed the key (i.e. it
    should proceed with execution).  Returns False if another instance already
    holds the key — the caller must treat this as a duplicate and skip.

    The key expires after *ttl* seconds (default 5 minutes) so that a crashed
    worker does not permanently block retries.
    """
    try:
        from src.adapters.redis_queue import get_redis as _get_redis
        _redis = _get_redis()
        bp_part = str(broker_profile_id) if broker_profile_id is not None else "none"
        lock_key = f"trade_lock:{trade_key.strip()}:{bp_part}"
        # SET NX EX — returns True only if key did not exist
        acquired = _redis.set(lock_key, "1", nx=True, ex=ttl)
        return bool(acquired)
    except Exception as e:
        # If Redis is unavailable, fall back to the DB-level check below.
        # Log the failure but do not block — the DB unique constraint is the
        # hard safety net in this case.
        logger.warning("Trade key claim (Redis SETNX) failed: %s — falling back to DB check", e)
        return True  # allow DB check to be the arbiter


def _lookup_symbol_overrides(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch per-symbol risk rules from Supabase with Redis cache (TTL=60s)."""
    if not supabase or not symbol:
        return None
    cache_key = f"symbol_rules:{symbol.upper()}"
    # Try Redis cache first
    try:
        from src.services.redis_cache import cache_get, cache_set
        cached = cache_get(cache_key)
        if cached is not None:
            return cached if cached else None  # empty dict = "no rules" sentinel
    except Exception:
        pass
    # Cache miss — query Supabase
    try:
        r = (
            supabase.table("symbol_risk_rules")
            .select("*")
            .eq("symbol", symbol.upper())
            .limit(1)
            .execute()
        )
        result = r.data[0] if r.data else {}
        try:
            from src.services.redis_cache import cache_set
            cache_set(cache_key, result, ttl_seconds=60)
        except Exception:
            pass
        return result if result else None
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
        # Sprint 2.3: stamp the routing account_id so signals can be filtered
        # per-account. Defaults to "default" for single-account deployments.
        "account_id": payload.get("_account_id") or "default",
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

    signal_time_str = payload.get("signal_time")
    if signal_time_str:
        try:
            from datetime import datetime, timezone
            dt = datetime.strptime(signal_time_str, "%Y-%m-%d %H:%M:%S")
            data["created_at"] = dt.replace(tzinfo=timezone.utc).isoformat()
        except Exception as e:
            logger.warning("Failed to parse signal_time '%s': %s", signal_time_str, e)

    # ai_reasoning: merge zone/metrics with optional caller-provided (e.g. ensemble)
    merged_reason = {**zone_reason}
    if ai_reasoning:
        merged_reason.update(ai_reasoning)

    # Transparency: Ensure decision_trace exists for frontend "Debug View"
    # This ensures "Feature Snapshot" tab is populated even for early guard rejections.
    if "decision_trace" not in merged_reason:
        merged_reason["decision_trace"] = {
            "features_snapshot": {**zone_reason},
            "interpretation": "Trade rejected by internal guard before reaching AI ensemble processing."
        }

    if merged_reason:
        merged_reason.setdefault("decision", status)
        merged_reason.setdefault("reason", note)
        data["ai_reasoning"] = json.dumps(merged_reason)

    receipt_id = (payload.get("_webhook_receipt_id") or "").strip()
    try:
        if receipt_id:
            # API pre-inserted; update existing row instead of inserting
            existing = (
                supabase.table("trading_signals")
                .select("id")
                .eq("webhook_receipt_id", receipt_id)
                .limit(1)
                .execute()
            )
            if existing.data and len(existing.data) > 0:
                sig_id = int(existing.data[0]["id"])
                # Don't overwrite created_at; remove it from data if present
                data.pop("created_at", None)
                supabase.table("trading_signals").update(data).eq("id", sig_id).execute()
                payload["_signal_id"] = sig_id
                corr = payload.get("_correlation_id")
                if corr:
                    from src.services.ai_run_service import link_ai_run_to_signal
                    link_ai_run_to_signal(supabase, corr, sig_id)
                logger.info("Updated: %s | %s (receipt_id=%s)", status, note, receipt_id[:8])
            else:
                # Receipt not found (e.g. migration not run); fall back to insert
                resp = supabase.table("trading_signals").insert(data).execute()
                if resp.data and len(resp.data) > 0:
                    sig_id = int(resp.data[0]["id"])
                    payload["_signal_id"] = sig_id
                    corr = payload.get("_correlation_id")
                    if corr:
                        from src.services.ai_run_service import link_ai_run_to_signal
                        link_ai_run_to_signal(supabase, corr, sig_id)
                logger.info("Saved: %s | %s", status, note)
        else:
            resp = supabase.table("trading_signals").insert(data).execute()
            if resp.data and len(resp.data) > 0:
                sig_id = int(resp.data[0]["id"])
                payload["_signal_id"] = sig_id
                corr = payload.get("_correlation_id")
                if corr:
                    from src.services.ai_run_service import link_ai_run_to_signal
                    link_ai_run_to_signal(supabase, corr, sig_id)
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
    """Validate FLIP entry timing: bar_time minutes must be at 5-min boundary.

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
        from dateutil.parser import parse as _parse_dt

        if not isinstance(bar_time, str):
            logger.warning("bar_time is not a string (%s) — skipping FLIP timing check", type(bar_time))
            return None

        dt = _parse_dt(bar_time)

        if dt.minute % 5 != 0:
            return (
                f"FLIP entry rejected: bar_time {bar_time} has minute={dt.minute}, "
                f"but FLIP entries require 5-min boundaries"
            )
        return None
    except Exception as e:
        logger.warning("FLIP timing validation error: %s — allowing trade (fail-open)", e)
        return None


# Futures symbols (Mangoe rules: BOC or Directional Close primary; Flip only on 5m boundary)
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
    """Enforce Mangoe Futures entry rules: BOC or Directional Close primary; reject Flip unless on 5m boundary.

    For Futures (CL, NQ, GC, XAUUSD, etc.):
    - Prefer Break of Candle or Directional Close.
    - FLIP entries are only allowed when bar_time is on a 5-min boundary.
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

    # FLIP: require 5m boundary (strict for Futures — do not fail-open on missing bar_time)
    if "flip" in entry_model:
        bar_time = payload.get("bar_time")
        if not bar_time or not isinstance(bar_time, str):
            return (
                "Futures (Mangoe): FLIP entry requires bar_time for 5m boundary check. "
                "Use Break of Candle or Directional Close, or ensure Flip occurs on 5m candle open."
            )
        reason = _validate_flip_timing(payload)
        if reason:
            return f"Futures (Mangoe): {reason}"
        return None

    return None  # Other models (e.g. AUTO) — allow


_GRADE_VALUES = {"A+": 6, "A": 5, "B+": 4, "B": 3, "C+": 2, "C": 1}

# Guards that are important enough to notify Discord/Telegram when they fire.
# Others (e.g. zone score, dead zone) are routine and would spam.
_NOTIFY_GUARD_PREFIXES = (
    "weekly loss limit",
    "monthly loss limit",
    "circuit breaker",
    "profit lock",
    "drawdown scale",
    "spread gate",
)


def _notify_guard_activation(reason: str, symbol: str, payload: Dict[str, Any]) -> None:
    """Fire a Discord/Telegram alert when an important risk guard activates."""
    reason_lower = reason.lower()
    if not any(reason_lower.startswith(p) for p in _NOTIFY_GUARD_PREFIXES):
        return
    try:
        from src.adapters.discord import send_discord_async
        notification_payload = {
            "symbol": symbol,
            "side": payload.get("side", ""),
            "size": payload.get("size", 0),
            "entry": payload.get("entry", 0),
            "account_balance": payload.get("account_balance", 0),
            "run_mode": payload.get("run_mode", "PAPER"),
            "_guard_reason": reason,
            "_guard_blocked": True,
        }
        send_discord_async(notification_payload, alert_id=0, mode="guard_blocked")
    except Exception as _e:
        logger.debug("Guard notification skipped: %s", _e)


def _validate_pine_filters(payload: Dict[str, Any]) -> Optional[str]:
    """Deterministic pre-filters mirroring SND_Strategy.pine entry conditions.

    Checks: score, grade, return strength, liquidity sweep, departure strength,
    dead zone, trading hours, daily trade limit.
    Returns None if all pass, rejection reason string if any fails.
    """
    from datetime import datetime as _dt, timezone
    from dateutil.parser import parse as _parse_dt

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

    # --- 1-candle liquidity filter (composite confidence scorer) ---
    # Uses LiquidityScorer: hard gates + weighted zone quality + market context.
    # Only applies when liq_candle_count == 1 and the feature is enabled.
    _ocl_enabled, _ocl_min_dep = _get_one_candle_liq_settings(s)
    if _ocl_enabled:
        liq_candle_count = payload.get("liq_candle_count")
        if liq_candle_count is not None:
            try:
                if int(liq_candle_count) == 1:
                    # Hard gate check (safety net — Pine should block these first)
                    gate_ok, gate_reason = _liquidity_scorer.passes_hard_gates(payload)
                    if not gate_ok:
                        return f"1-candle liquidity blocked: {gate_reason}"

                    # Middle zone hard block (no stronger zone available)
                    if bool(payload.get("is_middle_zone", False)):
                        return "1-candle liquidity blocked: middle zone"

                    # Composite score (market_cache empty until MetaAPI cache is wired)
                    result = _liquidity_scorer.score(payload, market_cache={})
                    # Attach score to payload so save_alert persists it to DB
                    payload["liquidity_score"] = result["score"]
                    if not result["execute"]:
                        return f"1-candle liquidity blocked: {result['reason']}"

                    logger.info(
                        "1-candle liquidity ALLOWED: %s symbol=%s",
                        result["reason"], payload.get("symbol")
                    )
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

    # --- Dead zone (xx:50-xx:00) --- [legacy fallback, only active if pine_block_dead_zone=true]
    if s.pine_block_dead_zone:
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                dt = _parse_dt(bar_time)
                if dt.minute >= 50:
                    return f"Dead zone: bar_time {bar_time} is in last 10 min of hour (minute={dt.minute})"
            except Exception:
                pass  # fail-open

    # --- HTF pre-candle block (high-volume open protection) ---
    # The HTF candle (15m/30m/1h) opens with high volume that can spike price and
    # stop out any position entered in the preceding minutes.
    # Block ALL entries in the last block_mins of the HTF cycle.
    _htf_enabled, _htf_block_mins, _htf_period = _get_htf_filter_settings(s)
    if _htf_enabled:
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                dt = _parse_dt(bar_time)
                candle_offset = dt.minute % _htf_period
                if candle_offset >= (_htf_period - _htf_block_mins):
                    next_candle_min = ((dt.minute // _htf_period) + 1) * _htf_period % 60
                    return (
                        f"HTF pre-candle block: entry rejected {_htf_period - candle_offset}m before "
                        f"{_htf_period}m HTF candle open at :{next_candle_min:02d} "
                        f"(bar_time minute={dt.minute}, block_mins={_htf_block_mins})"
                    )
            except Exception:
                pass  # fail-open

    # --- Trading hours (local timezone, auto-DST) ---
    start_local = getattr(s, "pine_trading_start_hour_local", s.pine_trading_start_hour)
    end_local = getattr(s, "pine_trading_end_hour_local", s.pine_trading_end_hour)
    tz_name = getattr(s, "pine_trading_timezone", "UTC")
    if start_local != 0 or end_local != 23:
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                import pytz as _pytz
                dt_utc = _parse_dt(bar_time)
                if dt_utc.tzinfo is None:
                    from datetime import timezone as _tz
                    dt_utc = dt_utc.replace(tzinfo=_tz.utc)
                local_tz = _pytz.timezone(tz_name)
                dt_local = dt_utc.astimezone(local_tz)
                if dt_local.hour < start_local or dt_local.hour >= end_local:
                    return (
                        f"Outside trading hours: local_hour={dt_local.hour} {tz_name} "
                        f"(allowed {start_local}:00-{end_local}:00)"
                    )
            except Exception:
                pass  # fail-open



    # --- Spread gate (minimum SL pips per instrument type) ---
    if getattr(s, "spread_gate_enabled", True):
        try:
            entry_price = float(payload.get("entry", 0))
            sl_price = float(payload.get("sl", 0))
            sym_upper = (payload.get("symbol") or "").upper()
            if entry_price > 0 and sl_price > 0:
                price_diff = abs(entry_price - sl_price)
                if "XAU" in sym_upper or "GOLD" in sym_upper or "XAG" in sym_upper:
                    sl_pips_calc = price_diff / 0.01
                    min_sl = getattr(s, "min_sl_pips_gold", 30.0)
                    instrument = "gold/silver"
                elif any(x in sym_upper for x in ["US30", "NAS", "SPX", "NDX", "USTEC"]):
                    sl_pips_calc = price_diff  # indices: 1 point = 1 unit
                    min_sl = getattr(s, "min_sl_pips_indices", 10.0)
                    instrument = "index"
                elif "JPY" in sym_upper:
                    sl_pips_calc = price_diff / 0.01
                    min_sl = getattr(s, "min_sl_pips_jpy", 7.0)
                    instrument = "JPY pair"
                else:
                    sl_pips_calc = price_diff / 0.0001
                    min_sl = getattr(s, "min_sl_pips_forex", 5.0)
                    instrument = "forex"
                if sl_pips_calc < min_sl:
                    return (
                        f"Spread gate ({instrument}): SL {sl_pips_calc:.1f} pips < "
                        f"minimum {min_sl:.0f} pips — SL too tight relative to spread risk"
                    )
        except Exception as e:
            logger.warning("Spread gate check failed: %s (fail-open)", e)

    # --- Monthly loss limit ---
    if getattr(s, "enable_monthly_loss_limit", True) and getattr(s, "monthly_max_loss_pct", 8.0) > 0 and supabase:
        try:
            month_start = _dt.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
            monthly_resp = (
                supabase.table("trading_signals")
                .select("pnl_usd")
                .in_("status", ["CLOSED", "closed"])
                .gte("created_at", month_start)
                .execute()
            )
            monthly_pnl = sum(float(t.get("pnl_usd") or 0) for t in (monthly_resp.data or []))
            acct_bal_m = float(payload.get("account_balance", s.account_balance))
            monthly_limit = -(getattr(s, "monthly_max_loss_pct", 8.0) / 100.0) * acct_bal_m
            if monthly_pnl < monthly_limit:
                return (
                    f"Monthly loss limit: ${monthly_pnl:.2f} loss this month "
                    f"(limit ${monthly_limit:.2f} = {getattr(s, 'monthly_max_loss_pct', 8.0):.0f}% of ${acct_bal_m:.0f})"
                )
        except Exception as e:
            logger.warning("Monthly loss check failed: %s (fail-open)", e)

    # --- Weekly loss limit ---
    if getattr(s, "enable_weekly_loss_limit", True) and getattr(s, "weekly_max_loss_pct", 10.0) > 0 and supabase:
        try:
            from datetime import timedelta
            week_start = (_dt.now(timezone.utc) - timedelta(days=7)).isoformat()
            weekly_resp = (
                supabase.table("trading_signals")
                .select("pnl_usd")
                .in_("status", ["CLOSED", "closed"])
                .gte("created_at", week_start)
                .execute()
            )
            weekly_pnl = sum(float(t.get("pnl_usd") or 0) for t in (weekly_resp.data or []))
            acct_bal = float(payload.get("account_balance", s.account_balance))
            weekly_limit = -(getattr(s, "weekly_max_loss_pct", 10.0) / 100.0) * acct_bal
            if weekly_pnl < weekly_limit:
                return (
                    f"Weekly loss limit: ${weekly_pnl:.2f} loss this week "
                    f"(limit ${weekly_limit:.2f} = {getattr(s, 'weekly_max_loss_pct', 10.0):.0f}% of ${acct_bal:.0f})"
                )
        except Exception as e:
            logger.warning("Weekly loss check failed: %s (fail-open)", e)

    # --- Consecutive loss circuit breaker ---
    max_consec = getattr(s, "max_consecutive_losses", 3)
    if max_consec > 0 and supabase:
        try:
            consec_resp = (
                supabase.table("trading_signals")
                .select("pnl_usd, exit_time")
                .in_("status", ["CLOSED", "closed"])
                .order("exit_time", desc=True)
                .limit(max_consec)
                .execute()
            )
            consecutive = 0
            for trade in (consec_resp.data or []):
                if (float(trade.get("pnl_usd") or 0)) < 0:
                    consecutive += 1
                else:
                    break
            if consecutive >= max_consec and consec_resp.data:
                pause_hours = float(getattr(s, "consec_loss_pause_hours", 4.0))
                last_exit_str = consec_resp.data[0].get("exit_time")
                if last_exit_str:
                    try:
                        from dateutil.parser import parse as _parse_exit
                        last_exit = _parse_exit(last_exit_str)
                        if last_exit.tzinfo is None:
                            last_exit = last_exit.replace(tzinfo=timezone.utc)
                        elapsed_h = (_dt.now(timezone.utc) - last_exit).total_seconds() / 3600
                        if elapsed_h < pause_hours:
                            remaining = pause_hours - elapsed_h
                            return (
                                f"Circuit breaker: {consecutive} consecutive losses — "
                                f"cooling off ({remaining:.1f}h remaining of {pause_hours:.0f}h pause)"
                            )
                    except Exception:
                        pass  # fail-open on date parse error
        except Exception as e:
            logger.warning("Consecutive loss check failed: %s (fail-open)", e)

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
        from datetime import datetime as _dt, timezone
        today_start = _dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        q = supabase.table("trading_signals").select("pnl_usd").in_("status", ["CLOSED", "closed"]).gte("created_at", today_start)
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])
        pnl_resp = q.execute()
        return sum(float(t.get("pnl_usd") or 0) for t in (pnl_resp.data or []))
    except Exception:
        return 0.0


def _get_account_daily_trade_count(profile: Optional[Dict[str, Any]] = None) -> int:
    """Count today's executed/active/closed trades for a specific account."""
    if not supabase:
        return 0
    try:
        from datetime import datetime as _dt, timezone
        today_start = _dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        q = (
            supabase.table("trading_signals")
            .select("id")
            .in_("status", ["active", "executed", "closed"])
            .gte("created_at", today_start)
        )
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])
        result = q.execute()
        return len(result.data or [])
    except Exception:
        return 0


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
    except Exception as e:
        if run_mode == "LIVE":
            logger.critical("Kill switch check failed for %s in LIVE mode: %s — blocking trade (fail-closed)", account_name, e)
            return f"Kill switch dependency unavailable for account {account_name} — blocked for safety"
        logger.warning("Kill switch check failed for %s: %s (non-LIVE, continuing)", account_name, e)

    # MTM Guardian (per-account)
    if supabase and getattr(s, "mtm_guardian_enabled", True):
        try:
            from src.services.mtm_guardian import MTMGuardian
            # Use per-account starting balance if available
            acct_balance = float(payload.get("account_balance", s.account_balance))
            mtm_guardian = MTMGuardian(_get_fresh_supabase(), s, starting_balance=acct_balance)
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
            if run_mode == "LIVE":
                logger.critical("MTM Guardian check failed for %s in LIVE mode: %s — blocking trade (fail-closed)", account_name, e)
                return f"MTM Guardian dependency unavailable for account {account_name} — blocked for safety"
            logger.error("MTM Guardian check failed for %s: %s (non-LIVE, continuing)", account_name, e)

    # ── Per-account circuit breaker ───────────────────────────
    if run_mode == "LIVE":
        try:
            from src.core.circuit_breaker import is_metaapi_circuit_open
            if is_metaapi_circuit_open(account_name=account_name):
                return f"Circuit breaker open for account {account_name}"
        except Exception as e:
            logger.critical("Circuit breaker check failed for %s in LIVE mode: %s — blocking trade (fail-closed)", account_name, e)
            return f"Circuit breaker dependency unavailable for account {account_name} — blocked for safety"

    # ── Per-account Adaptive daily trade limit (PineGuardian) ─
    try:
        from src.core.guard_rails.pine_guardian import create_pine_guardian_from_settings
        from src.services.pine_streak import get_streak_days, get_today_summary
        from src.adapters.redis_queue import get_redis as _get_redis_for_limit
        import datetime as _dt_mod

        _redis = _get_redis_for_limit()
        _guardian = create_pine_guardian_from_settings()

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
                    f"Adaptive trade limit ({account_name}): {_state.current_session_trades}/{_state.effective_limit} "
                    f"[{_state.session.value} | base={_state.session_base} "
                    f"intraday={_state.intraday_adj:+d} streak={_state.streak_bonus:+d}]"
                )
            if not _guardian.check_risk_budget():
                return (
                    f"Daily risk budget exhausted ({account_name}): {_guardian.daily_risk_deployed_pct:.2f}% "
                    f">= {_guardian.daily_risk_budget_pct:.2f}%"
                )
        elif getattr(s, "pine_max_trades_per_day", 0) > 0:
            today_count = _get_account_daily_trade_count(profile)
            if today_count >= getattr(s, "pine_max_trades_per_day", 0):
                return f"Daily trade limit reached ({account_name}): {today_count}/{s.pine_max_trades_per_day} trades today"
    except Exception as e:
        if run_mode == "LIVE":
            logger.critical("Adaptive trade limit check failed for %s in LIVE mode: %s — blocking trade (fail-closed)", account_name, e)
            return f"Adaptive trade limit dependency unavailable for account {account_name} — blocked for safety"
        logger.warning("Adaptive trade limit check failed for %s: %s (non-LIVE, continuing)", account_name, e)

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
    # Resolution order:
    #   1. profile["consistency_enabled"] from broker_profiles DB column (None | True | False)
    #   2. global settings.consistency_enabled                           (True by default)
    # This lets ACG (no consistency rule) set consistency_enabled=False per account
    # while FTMO accounts keep the 40% best-day cap enforced.
    _profile_consistency = (profile or {}).get("consistency_enabled")   # None | True | False
    _global_consistency = getattr(s, "consistency_enabled", True)
    _run_consistency = _profile_consistency if _profile_consistency is not None else _global_consistency

    # evaluation_mode: prefer per-account profile flag, fall back to global settings
    _profile_eval_mode = (profile or {}).get("evaluation_mode")   # True | False | None
    _global_eval_mode = getattr(s, "evaluation_mode", False)
    _eval_mode = _profile_eval_mode if _profile_eval_mode is not None else _global_eval_mode

    if _run_consistency and _eval_mode and supabase:
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

    # Idempotency check per-profile (atomic Redis claim + DB fallback)
    if trade_key:
        if not _claim_trade_key(trade_key, profile_id):
            logger.info("Idempotency (Redis): (trade_key=%s, profile=%s) already claimed, skipping", trade_key, account_name)
            return
        if _exists_trade_key(trade_key, profile_id):
            logger.info("Idempotency (DB): (trade_key=%s, profile=%s) exists, skipping", trade_key, account_name)
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

    # Apply PropGuard multiplier from the guards that just ran
    if acct_multiplier_key in payload:
        payload["_risk_multiplier"] = payload[acct_multiplier_key]

    # ── Half-risk enforcement for 2nd daily trade (Python-side authority) ────────────
    # Pine Script also applies half-risk for the 2nd trade, but Python is the authority.
    # This ensures the cap holds even if Pine has a bug or risk% changes mid-day.
    max_daily = getattr(s, "pine_max_trades_per_day", 0)
    if max_daily >= 2:
        try:
            acct_today_count = _get_account_daily_trade_count(profile)
            if acct_today_count == 1:  # this incoming trade will be the 2nd
                current_mult = float(payload.get("_risk_multiplier", 1.0))
                payload["_risk_multiplier"] = current_mult * 0.5
                logger.info(
                    "Half-risk [%s]: 2nd trade of day — multiplier %.2f → %.2f",
                    account_name, current_mult, payload["_risk_multiplier"],
                )
        except Exception as e:
            logger.warning("Half-risk daily count failed for %s: %s (fail-open)", account_name, e)

    # Execute
    try:
        if dry_run:
            logger.info("DRY_RUN [%s]: LIVE_TRADING=false — saving alert + notify only", account_name)
        log_event(None, "execution_started", "worker", {"symbol": symbol, "dry_run": dry_run, "profile": account_name})
        logic.process_trade(payload, dry_run=dry_run, ai_result=ai_result, profile=profile)
        logger.info("logic.process_trade completed for profile %s", account_name)
        # Record trade in streak tracker (intraday state for adaptive limit)
        try:
            from src.services.pine_streak import record_trade_result as _record_streak
            _risk_pct = float(payload.get("risk_percent", get_settings().risk_percent))
            # pnl not known at entry; use 0 as placeholder (wins/losses tracked by watchdog later)
            # Record as a "placed" trade so the budget gate deploys correctly
            _record_streak(get_redis(), pnl=0.0, risk_pct=_risk_pct)
        except Exception as _streak_err:
            logger.debug("pine_streak record failed (non-fatal): %s", _streak_err)
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
    # Exit events: route directly to logic (no entry guards)
    if payload.get("event_type") == "exit":
        logger.info("Exit event for zone_id=%s — routing to logic.process_trade", payload.get("zone_id"))
        logic.process_trade(payload)
        return

    symbol = payload.get("symbol", "UNKNOWN")
    side = payload.get("side", "buy")
    size = float(payload.get("size", 0.01))
    logger.info("Processing: %s | %s | Size: %s", symbol, side.upper(), size)

    s = get_settings()

    # ══════════════════════════════════════════════════════════════════
    # LATENCY INSTRUMENTATION (Phase 1 Optimization)
    # Track execution time at each stage to identify bottlenecks
    # ══════════════════════════════════════════════════════════════════
    from src.utils.latency_tracker import LatencyTracker
    latency_enabled = getattr(s, "enable_latency_instrumentation", False)
    tracker = LatencyTracker(enabled=latency_enabled)
    tracker.set_metadata("symbol", symbol)
    tracker.set_metadata("side", side)
    tracker.checkpoint("start")

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
        log_guard_decision("size_guard", "rejected", rejection_reason, symbol)
        logger.warning(
            "SIZE REJECTED: size=%s (must be > 0). Reason: %s",
            payload.get("size"),
            rejection_reason[:200],
        )
        return

    # ── Max Lot Size Guard ────────────────────────────────────
    max_lot_size = s.max_lot_size if hasattr(s, 'max_lot_size') else 10.0
    if size > max_lot_size:
        reason = (
            f"Position size {size} lots exceeds max_lot_size={max_lot_size}. "
            f"Check TradingView Pine initial_capital vs actual account balance."
        )
        save_result(
            payload,
            "filtered",
            reason,
            0.0,
            account_name=account_name,
        )
        log_guard_decision("max_lot_size", "rejected", reason, symbol)
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
    # Skip when _e2e_test=true (E2E test uses static prices; guard would reject)
    run_mode = str(payload.get("run_mode", "PAPER")).upper()
    if (
        run_mode == "LIVE"
        and getattr(s, "enable_staleness_guard", True)
        and not payload.get("_e2e_test")
    ):
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

    tracker.checkpoint("after_staleness_guard")

    # ══════════════════════════════════════════════════════════════════
    # PINE FILTERS + RISK GUARDS (zone quality, daily/weekly/monthly limits,
    # spread gate, consecutive loss circuit breaker)
    # ══════════════════════════════════════════════════════════════════
    pine_rejection = _validate_pine_filters(payload)
    if pine_rejection:
        save_result(payload, "filtered", pine_rejection, 0.0, account_name=account_name)
        _tag = pine_rejection.split(":")[0].lower().replace(" ", "_")[:40]
        log_guard_decision("pine_filters", "rejected", pine_rejection, symbol, {"tag": _tag})
        logger.warning("PINE/RISK FILTER BLOCKED [%s]: %s", symbol, pine_rejection)
        _notify_guard_activation(pine_rejection, symbol, payload)
        return

    tracker.checkpoint("after_pine_filters")

    # ══════════════════════════════════════════════════════════════════
    # FAST-PATH BYPASS (Phase 1 Latency Optimization)
    # Skip full AI ensemble for high-confidence signals to reduce latency.
    # If RF confidence >= threshold, skip Supervisor + Trading Council.
    # ══════════════════════════════════════════════════════════════════
    enable_fast_path = getattr(s, "enable_fast_path_bypass", False)
    fast_path_threshold = getattr(s, "fast_path_rf_threshold", 0.85)
    fast_path_live_only = getattr(s, "fast_path_live_only", True)

    ai_result = None
    used_fast_path = False

    # Fast path conditions: enabled + (LIVE mode OR not live-only restriction)
    if enable_fast_path and (run_mode == "LIVE" or not fast_path_live_only):
        try:
            # Quick RF prediction only (no LLM, no RAG)
            rf_prob, rf_note, features = get_prediction(payload)

            if rf_prob >= fast_path_threshold:
                # High confidence - bypass full AI ensemble
                used_fast_path = True
                ai_result = {
                    "decision": "GO",
                    "reason": f"Fast-path approved (RF={rf_prob:.2f} >= {fast_path_threshold:.2f})",
                    "rf_prob": rf_prob,
                    "rf_note": rf_note,
                    "fast_path": True,
                    "rules": [],
                    "narrative": "Fast-path bypass - skipped RAG/LLM for speed",
                    "llm_raw": None,
                }
                logger.info(
                    "⚡ FAST PATH: RF=%.2f >= %.2f, skipping full AI ensemble (saved ~1200ms)",
                    rf_prob,
                    fast_path_threshold,
                )
                log_event(
                    None,
                    "fast_path_bypass",
                    "worker",
                    {"symbol": symbol, "rf_prob": rf_prob, "threshold": fast_path_threshold},
                )
            else:
                logger.info(
                    "Fast-path not triggered: RF=%.2f < %.2f, running full AI ensemble",
                    rf_prob,
                    fast_path_threshold,
                )
        except Exception as e:
            logger.warning("Fast-path check failed, falling back to full AI: %s", e)

    # ══════════════════════════════════════════════════════════════════
    # MAS COUNCIL DECISION (Supervisor → Quant Agent → Risk Agent)
    # Debate is streamed live to /ws/debate via Redis pub/sub.
    # Only runs if fast-path didn't bypass it.
    # ══════════════════════════════════════════════════════════════════
    if ai_result is None:
        from src.agents.supervisor import Supervisor as _Supervisor
        _supervisor = _Supervisor(supabase_client=supabase, redis_client=get_redis())
        ai_result = _supervisor.evaluate(payload)

    tracker.checkpoint("after_ai_supervisor")
    tracker.set_metadata("used_fast_path", used_fast_path)
    tracker.set_metadata("rf_prob", ai_result.get("rf_prob", 0.0) if ai_result else 0.0)

    # Trading Council — 9-stage multi-agent pipeline (SHADOW MODE, never blocks)
    # Replaces the old 4-agent Bull/Bear/Risk/Chair debate.
    # Stages: Market Analyst → Setup Analyst → Bull/Bear Researchers →
    #         Research Manager → Aggressive/Conservative/Neutral Debaters → Risk Judge
    #
    # Phase 1 Optimization: Run in background thread if async enabled (saves ~500-1000ms)
    if getattr(s, "ai_debate_enabled", True):
        async_council = getattr(s, "async_trading_council", False)

        def _run_council_sync():
            """Run Trading Council synchronously (blocking)."""
            try:
                from src.ai.trading_council import run_trading_council
                from src.services.ai_run_service import persist_debate, _get_trace_id_by_correlation

                council_result = run_trading_council(
                    payload,
                    supabase=supabase,
                    redis_client=get_redis(),
                )
                corr = payload.get("_correlation_id")

                import src.adapters.supabase as supabase_module
                supabase_module.init_supabase()
                sb_client = supabase_module.supabase

                if not corr:
                    logger.warning(
                        "Trading Council: no _correlation_id in payload — ai_run will not be persisted. "
                        "Ensure api.py stamps _correlation_id before enqueue."
                    )
                elif sb_client:
                    trace_id = _get_trace_id_by_correlation(sb_client, corr) if sb_client else None
                    persist_debate(sb_client, corr, council_result, trace_id=trace_id)

                # Shadow: council recommendation is logged only, NEVER blocks execution
                logger.info(
                    "Trading Council (shadow): decision=%s confidence=%d memo=%s votes=%s",
                    council_result.get("council_decision"),
                    council_result.get("council_confidence", 0),
                    (council_result.get("memo") or "")[:80],
                    council_result.get("votes_tally", ""),
                )
            except Exception as deb_err:
                logger.warning("Trading Council failed (non-blocking): %s", deb_err)

        if async_council:
            corr = payload.get("_correlation_id")
            logger.info("⚡ Trading Council async check: corr=%s", corr)
            if corr:
                from src.services.ai_run_service import init_ai_run
                import src.adapters.supabase as supabase_module
                supabase_module.init_supabase()
                inserted = init_ai_run(supabase_module.supabase, corr)
                logger.info("⚡ init_ai_run for corr=%s returned %s", corr, inserted)
            # Run in background thread - don't wait for result
            import threading
            threading.Thread(target=_run_council_sync, daemon=True, name="TradingCouncilAsync").start()
            logger.info("⚡ Trading Council started in background (async mode, saved ~500-1000ms)")
        else:
            # Original blocking behavior
            _run_council_sync()

    tracker.checkpoint("after_trading_council")

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
    # Shadow mode: run_shadow_mode (hardcoded) OR ai_mode=="shadow" (env-controlled AI_MODE)
    # AI_MODE=shadow → log-only, never block. AI_MODE=enforce → blocking active.
    _effective_ai_mode = getattr(s, "ai_mode", "shadow")
    try:
        from src.services.ai_mode_override import get_ai_mode_override
        _db_override = get_ai_mode_override()
        if _db_override:
            _effective_ai_mode = _db_override
    except Exception:
        pass
    shadow_mode = bool(getattr(s, "run_shadow_mode", False)) or (_effective_ai_mode == "shadow")

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

    tracker.checkpoint("after_ai_decision")

    payload["ai_reasoning"] = ai_result
    payload["ai_decision"] = ai_result.get("decision")
    try:
        payload["ai_confidence"] = round(float(ai_result.get("rf_prob", 0.0)) * 100, 1)
    except Exception:
        pass

    # ── Execution Mode: derived from system_config (set by dashboard toggle) ──
    # DRY_RUN → early exit, no profiles touched, signal saved as dry_run status
    # PAPER   → route to PAPER-tagged broker profiles, dry_run=True (no real orders)
    # LIVE    → route to LIVE-tagged broker profiles, dry_run=False (real MetaTrader orders)
    # Always read from DB — payload's run_mode is informational only; dashboard is authoritative.
    system_mode = _get_system_trading_mode()

    if system_mode == "DRY_RUN":
        logger.info("System mode: DRY_RUN — signal acknowledged, no execution")
        save_result(payload, "dry_run", "System mode: DRY_RUN — no execution", 0.0)
        return

    # dry_run: True when mode is PAPER (demo account, no real order), False when LIVE
    dry_run = (system_mode != "LIVE")

    # Global equity estimate for VaR/sector (pre-account loop)
    dynamic_account_balance = float(payload.get("account_balance", s.account_balance))
    global_daily_pnl = _get_account_daily_pnl(None)
    current_equity_global = dynamic_account_balance + global_daily_pnl

    # ── De-duplication: stamp _signal_id from the API-pre-inserted row so that
    # logic.process_trade() → save_alert() can UPDATE it instead of INSERT a new row.
    # Without this, every approved signal produces 2 rows: RECEIVED (API) + OPEN (logic).
    receipt_id = (payload.get("_webhook_receipt_id") or "").strip()
    if receipt_id and supabase and "_signal_id" not in payload:
        try:
            _existing = (
                supabase.table("trading_signals")
                .select("id")
                .eq("webhook_receipt_id", receipt_id)
                .limit(1)
                .execute()
            )
            if _existing.data:
                payload["_signal_id"] = int(_existing.data[0]["id"])
                logger.info(
                    "De-dup: stamped _signal_id=%s from receipt_id=%s",
                    payload["_signal_id"], receipt_id[:8],
                )
        except Exception as _dedup_err:
            logger.warning("De-dup lookup failed (non-fatal): %s", _dedup_err)

    # ══════════════════════════════════════════════════════════════════
    # MULTI-ACCOUNT EXECUTION (parallel — each account isolated)
    # Per-account guards (kill switch, circuit breaker, PropGuard,
    # correlation, consistency) run inside each profile's execution.
    # ══════════════════════════════════════════════════════════════════
    from src.core.broker_profiles import get_active_profiles

    profiles = get_active_profiles()
    matching = [p for p in profiles if (p.get("run_mode") or "LIVE") == system_mode]
    if not matching:
        logger.warning(
            "No broker profiles tagged run_mode=%s — signal acknowledged but no execution target",
            system_mode,
        )
        save_result(payload, "no_profile", f"No profiles configured for run_mode={system_mode}", 0.0)
        return

    logger.info("Execution mode: %s | dry_run=%s | %d profile(s) matched", system_mode, dry_run, len(matching))

    tracker.checkpoint("before_execution")

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

    tracker.checkpoint("after_execution")
    tracker.set_metadata("accounts_executed", len(matching))

    # Report latency breakdown (only if instrumentation enabled)
    if latency_enabled:
        tracker.report(symbol=symbol)


def run():
    init_connections()
    load_brain()
    s = get_settings()

    # Hydrate Trading Council BM25 memory from Supabase (non-blocking)
    if getattr(s, "memory_enabled", False):
        try:
            from src.ai.trading_council import load_council_memories_from_supabase
            from src.adapters.supabase import get_supabase
            _supabase = get_supabase()
            if _supabase:
                load_council_memories_from_supabase(_supabase)
        except Exception as _mem_err:
            logger.debug("Council memory hydration skipped: %s", _mem_err)
    transport = get_transport()
    kill_sw = getattr(s, "trading_kill_switch", False)
    logger.info("=" * 60)
    logger.info("WORKER v2 (MULTI-ACCOUNT ISOLATED) STARTED")
    logger.info("Transport: %s", type(transport).__name__)
    logger.info("Account Balance: $%s", f"{s.account_balance:,.0f}")
    logger.info("Risk Per Trade: %s%%", s.risk_percent)
    logger.info("Correlation Limit: %s positions", s.trinity_max_positions)
    logger.info("AI Ensemble: %s | Shadow: %s (ai_mode=%s)", "ON", "ON" if getattr(s, "run_shadow_mode", False) or getattr(s, "ai_mode", "shadow") == "shadow" else "OFF", getattr(s, "ai_mode", "shadow"))
    logger.info("Kill-Switch: %s", "ON" if kill_sw else "OFF")
    logger.info("EXECUTION MODE: Controlled by dashboard (system_config.trading_mode). DRY_RUN | PAPER | LIVE.")
    logger.info("Evaluation Mode: %s", "ON" if getattr(s, "evaluation_mode", False) else "OFF")
    logger.info("--- Guards ---")
    logger.info("Global: kill-switch(env), max-lot, staleness, AI ensemble")
    logger.info("Per-account: kill-switch(Redis/MTM), circuit-breaker, PropGuard, correlation, consistency")
    logger.info("Pine pre-filters: DISABLED (Pine Script handles entry rules)")
    logger.info("R:R filter: %s", f"ON (min={s.min_rr_ratio})" if s.min_rr_ratio > 0 else "OFF (Pine handles SL/TP)")
    logger.info("=" * 60)

    # ── Startup: validate Discord webhook URL (once, non-blocking) ──────────
    _discord_url = (getattr(s, "discord_webhook_url", "") or "").strip()
    if _discord_url:
        try:
            import requests as _req
            _probe = _req.get(_discord_url, timeout=5)
            if _probe.status_code == 404:
                logger.warning(
                    "⚠️  Discord webhook URL is INVALID (404 Unknown Webhook). "
                    "Update DISCORD_WEBHOOK_URL in .env — notifications will be silently skipped until fixed."
                )
            elif _probe.status_code in (200, 401):
                logger.info("Discord webhook URL validated OK (HTTP %s)", _probe.status_code)
        except Exception as _we:
            logger.debug("Discord webhook probe failed (non-fatal): %s", _we)

    # ── Observer pipeline ──────────────────────────────────────────────────
    subject = WorkerSubject(process_fn=process_trade, account_router=AccountRouter())
    subject.attach(AuditorObserver())
    subject.attach(RiskObserver())
    subject.attach(ExecutorObserver())
    subject.attach(AccountRouterObserver())
    subject.attach(MetricsObserver())
    logger.info(
        "Observer pipeline: %s",
        ["AuditorObserver", "RiskObserver", "ExecutorObserver", "AccountRouterObserver", "MetricsObserver"],
    )

    backoff = 5
    watchdog = TradeWatchdog(supabase_client=supabase)
    from src.services.alert_engine import AlertEngine
    from src.services.alert_service import create_default_alert_service
    _worker_alert_service = create_default_alert_service(supabase)
    alert_engine = AlertEngine(supabase_client=supabase, alert_service=_worker_alert_service)

    # Initialize daily reset scheduler for prop firm metrics
    daily_reset_scheduler = None
    if supabase and getattr(s, "evaluation_mode", False):
        try:
            from src.services.daily_reset_scheduler import DailyResetScheduler
            daily_reset_scheduler = DailyResetScheduler(supabase, s)
            logger.info("Daily reset scheduler initialized for prop firm tracking")
        except Exception as exc:
            logger.warning("Daily reset scheduler init failed: %s", exc)

    # Initialize Daily Digest scheduler
    digest_scheduler = None
    if supabase and getattr(s, "digest_enabled", True):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from src.services.digest_service import DigestService
            from src.services.notification_service import NotificationService
            from src.adapters.discord import dispatch_payload_async
            
            digest_scheduler = BackgroundScheduler()
            
            def _trigger_daily_digest():
                try:
                    logger.info("Triggering Daily Performance Digest...")
                    # ensure we use a fresh connection if needed
                    from src.worker import _get_fresh_supabase
                    sb = _get_fresh_supabase()
                    if not sb:
                        return
                        
                    digest_service = DigestService(sb)
                    notif_service = NotificationService()
                    
                    report = digest_service.aggregate_daily_performance(hours_lookback=24)
                    if report is None:
                        return
                    
                    for acct, stats in report.items():
                        payload = notif_service.format_digest(acct, stats)
                        dispatch_payload_async(payload, supabase_client=sb, notification_service=notif_service)
                        
                except Exception as e:
                    logger.error("Error in daily digest job: %s", e)

            # parse schedule config "HH:MM"
            digest_time = getattr(s, "digest_time_utc", "21:00")
            hour, min_ = 21, 0
            try:
                if ":" in digest_time:
                    parts = digest_time.split(":")
                    hour, min_ = int(parts[0]), int(parts[1])
            except Exception:
                pass
                
            digest_scheduler.add_job(_trigger_daily_digest, 'cron', hour=hour, minute=min_, timezone="UTC")
            digest_scheduler.start()
            logger.info("Daily digest scheduler initialized for %02d:%02d UTC", hour, min_)
        except Exception as exc:
            logger.warning("Daily digest scheduler init failed: %s", exc)

    last_watchdog_ts = time.time()
    last_reconciliation_ts = 0  # Broker reconciliation runs every 5 minutes
    last_prop_firm_cache_ts = 0  # Prop firm metrics cache runs every 20 seconds
    while True:
        task = None
        payload_str = None
        try:
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

                # Check and fire break-even SL moves (near-zero latency)
                if breakeven_manager:
                    try:
                        breakeven_manager.check_and_trigger()
                    except Exception as be_exc:  # noqa: BLE001
                        logger.error("BreakevenManager check failed: %s", be_exc)

                # Phase 11: Detect late fills (signals >TCA_LATENCY_THRESHOLD_MS with no broker confirmation)
                if watchdog:
                    try:
                        watchdog.check_late_fills()
                    except Exception as lf_exc:  # noqa: BLE001
                        logger.debug("Late fill check failed: %s", lf_exc)
                    try:
                        watchdog.expire_stuck_pending()
                    except Exception as ep_exc:  # noqa: BLE001
                        logger.debug("Expire stuck pending failed: %s", ep_exc)


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

            # FIX 4: Broker reconciliation runs INDEPENDENTLY of the 60s watchdog tick.
            # It checks every loop iteration (~5s) but only fires every 300s.
            # Previously it was nested inside the 60s block, making the 300s timer
            # only evaluated once per minute instead of continuously.
            if now - last_reconciliation_ts >= 300:
                try:
                    from src.services.broker_reconciliation import run_reconciliation_for_profile
                    from src.core.broker_profiles import get_active_profiles

                    profiles = get_active_profiles()
                    settings = get_settings()
                    for profile in profiles:
                        # Skip paper trading profiles
                        if profile.get("run_mode") == "PAPER":
                            continue
                        result = run_reconciliation_for_profile(
                            supabase_url=settings.supabase_url,
                            supabase_key=settings.supabase_service_role_key or settings.supabase_key,
                            broker_profile_id=profile.get("id", 0),
                            meta_api_token=profile.get("token", ""),
                            meta_api_account_id=profile.get("meta_api_account_id", ""),
                            meta_api_region=getattr(settings, "meta_api_region", "london"),
                        )
                        closed_count = result.get("closed_count", 0)
                        error_count = len(result.get("errors", []))
                        # Only log at INFO when something actually happened
                        if closed_count > 0 or error_count > 0:
                            logger.info(
                                "Broker reconciliation for profile %s: %d closed, %d errors",
                                profile.get("name", "unknown"),
                                closed_count,
                                error_count,
                            )
                        else:
                            logger.debug(
                                "Broker reconciliation for profile %s: no changes",
                                profile.get("name", "unknown"),
                            )
                    last_reconciliation_ts = now
                except Exception as recon_exc:  # noqa: BLE001
                    logger.error("Broker reconciliation failed: %s", recon_exc)

            if now - last_prop_firm_cache_ts >= 20:
                try:
                    from src.core.broker_profiles import get_active_profiles
                    from src.services.prop_firm_detector import PropFirmDetector
                    from src.services.redis_cache import cache_set
                    
                    profiles = get_active_profiles()
                    detector = PropFirmDetector(supabase) if supabase else None
                    if detector:
                        for profile in profiles:
                            account_name = profile.get("name")
                            if not account_name:
                                continue
                            
                            server_name = profile.get("meta_api_server_name", "")
                            challenge_type = detector.auto_detect_challenge_type(server_name, account_name)
                            rules = detector.get_firm_and_rules(server_name, challenge_type)
                            if not rules:
                                continue
                                
                            metrics_resp = supabase.table("prop_firm_metrics").select("*").eq("account_name", account_name).order("snapshot_time", desc=True).limit(1).execute()
                            metrics = metrics_resp.data[0] if metrics_resp.data else None
                            
                            res = {
                                "status": "active",
                                "firm_detected": bool(rules),
                                "firm_info": rules,
                                "metrics": metrics
                            }
                            cache_key = f"prop_firm:metrics:{account_name}"
                            cache_set(cache_key, res, ttl_seconds=30)
                except Exception as cache_exc:
                    logger.error("Prop firm cache worker failed: %s", cache_exc)
                last_prop_firm_cache_ts = now

            task = transport.dequeue(timeout=5)
            backoff = 5
            if task is None:
                continue
            _key, payload_str = task
            payload = validate_dequeued_message(payload_str, transport)
            if payload is None:
                continue  # dead-lettered and audited inside validator
            if payload.get("event_type") == "exit":
                logger.info("Exit event for zone_id=%s - processing", payload.get("zone_id"))
            subject.process_signal(payload)
        except (ConnectionError, OSError) as e:
            logger.error("Transport connection error: %s (reconnecting)", e)
            try:
                transport.reset()
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            logger.error("Loop error: %s", e)
            
            # --- PHASE 4: AUTOMATED ERROR-TO-TICKET PIPELINE ---
            try:
                import traceback
                from src.adapters.jira import create_bug_ticket
                error_trace = traceback.format_exc()
                create_bug_ticket(f"Worker Loop Error: {type(e).__name__}", f"Exception in worker loop:\n{error_trace}", sync_block=True)
            except Exception as jira_err:
                logger.error("Failed to forward exception to Jira: %s", jira_err)
            
            try:
                if "redis" in type(e).__module__.lower() or "ConnectionError" in type(e).__name__:
                    transport.reset()
            except Exception:
                pass
            try:
                if task is not None and payload_str is not None:
                    transport.dead_letter(payload_str, str(e))
                    log_event(None, "dead_lettered", "worker", {"error": str(e)[:200]})
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
