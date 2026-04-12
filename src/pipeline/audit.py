"""
src/pipeline/audit.py

DB write helpers for pipeline guard decisions and trade results.

All functions here are thin wrappers around the Supabase write layer.
They do NOT contain business logic — they just persist outcomes so the
frontend Signal Inspector and Debug View have data to display.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from config.logging_config import get_logger

logger = get_logger("trinity.pipeline.audit")

# ── Lazy module-level references (populated at worker startup) ────────────────
# These mirror the globals in worker.py so audit.py doesn't need to import
# the full worker module (which would cause circular imports).
_SUPABASE_GETTER = None   # callable() → supabase client
_SETTINGS_GETTER = None   # callable() → settings


def _get_sb():
    """Return the live Supabase client, or None if unavailable."""
    try:
        import src.adapters.supabase as _m
        return _m.supabase
    except Exception:
        return None


def _get_settings():
    from config import get_settings
    return get_settings()


# ── Zone / metric extraction ──────────────────────────────────────────────────

_SCHEMA_ZONE_METRICS = (
    "zone_id", "zone_type", "zone_top", "zone_bottom", "zone_size_pips",
    "entry_model", "score", "freshness", "session", "atr_ratio", "trend",
    "htf_trend", "rsi", "rvol", "adx", "touch_count", "base_quality",
    "departure_strength", "liquidity_distance", "liquidity_spread",
    "return_strength", "liquidity_distance_pips", "liquidity_spread_pips",
)
_BOOL_ZONE_FIELDS = ("liq_swept", "target_swept", "caused_sweep", "is_accuracy")


def extract_zone_and_metrics(
    payload: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Return (schema_columns, ai_reasoning_dict) from payload.

    Handles ``F:``-prefixed fallback keys so filtered signals still carry
    Zone Analysis data in the Signal Inspector.
    """
    def _f(k: str, default=None):
        return payload.get(k) if payload.get(k) is not None else payload.get(f"F:{k}", default)

    columns: Dict[str, Any] = {}
    for key in _SCHEMA_ZONE_METRICS:
        val = _f(key)
        if val is not None:
            columns[key] = val
    for key in _BOOL_ZONE_FIELDS:
        if payload.get(key) is not None:
            columns[key] = bool(payload[key])

    reason: Dict[str, Any] = {
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
    reason = {k: v for k, v in reason.items() if v is not None}
    return columns, reason


# ── Main audit write ──────────────────────────────────────────────────────────

def save_result(
    payload: Dict[str, Any],
    status: str,
    note: str,
    prob: float,
    ai_reasoning: Optional[Dict[str, Any]] = None,
    broker_profile_id: Optional[int] = None,
    account_name: Optional[str] = None,
) -> None:
    """Persist a guard / execution outcome row to ``trading_signals``.

    Strategy:
    - If ``_webhook_receipt_id`` is in payload → UPDATE the API-pre-inserted row.
    - Otherwise → INSERT a new row.

    Side-effect: stamps ``payload["_signal_id"]`` with the DB row id so
    downstream callers (e.g. ``link_ai_run_to_signal``) can reference it.
    """
    sb = _get_sb()
    if not sb:
        logger.warning("Supabase unavailable — result not saved: %s", status)
        return

    s = _get_settings()
    default_balance = getattr(s, "account_balance", 50000)

    data: Dict[str, Any] = {
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
        "account_id": payload.get("_account_id") or "default",
    }
    tk = (payload.get("trade_key") or "").strip()
    if tk:
        data["trade_key"] = tk
    if broker_profile_id is not None:
        data["broker_profile_id"] = broker_profile_id
    if account_name is not None:
        data["account_name"] = account_name

    extra_columns, zone_reason = extract_zone_and_metrics(payload)
    data.update(extra_columns)

    # Optional: honour signal_time from Pine for created_at
    signal_time_str = payload.get("signal_time")
    if signal_time_str:
        try:
            from datetime import datetime, timezone
            dt = datetime.strptime(signal_time_str, "%Y-%m-%d %H:%M:%S")
            data["created_at"] = dt.replace(tzinfo=timezone.utc).isoformat()
        except Exception as e:
            logger.warning("Failed to parse signal_time '%s': %s", signal_time_str, e)

    # Build merged ai_reasoning for frontend Debug View / Feature Snapshot
    merged_reason: Dict[str, Any] = {**zone_reason}
    if ai_reasoning:
        merged_reason.update(ai_reasoning)
    if "decision_trace" not in merged_reason:
        merged_reason["decision_trace"] = {
            "features_snapshot": {**zone_reason},
            "interpretation": "Trade rejected by internal guard before reaching AI ensemble processing.",
        }
    if merged_reason:
        merged_reason.setdefault("decision", status)
        merged_reason.setdefault("reason", note)
        data["ai_reasoning"] = json.dumps(merged_reason)

    receipt_id = (payload.get("_webhook_receipt_id") or "").strip()
    try:
        if receipt_id:
            existing = (
                sb.table("trading_signals")
                .select("id")
                .eq("webhook_receipt_id", receipt_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                sig_id = int(existing.data[0]["id"])
                data.pop("created_at", None)
                sb.table("trading_signals").update(data).eq("id", sig_id).execute()
                payload["_signal_id"] = sig_id
                _link_ai_run(sb, payload.get("_correlation_id"), sig_id)
                logger.info("Updated: %s | %s (receipt_id=%s)", status, note, receipt_id[:8])
                return
        # INSERT (no receipt or receipt not found)
        resp = sb.table("trading_signals").insert(data).execute()
        if resp.data:
            sig_id = int(resp.data[0]["id"])
            payload["_signal_id"] = sig_id
            _link_ai_run(sb, payload.get("_correlation_id"), sig_id)
        logger.info("Saved: %s | %s", status, note)
    except Exception as e:
        logger.error("DB write failed: %s", e)


def _link_ai_run(sb, correlation_id: Optional[str], sig_id: int) -> None:
    if sb and correlation_id:
        try:
            from src.services.ai_run_service import link_ai_run_to_signal
            link_ai_run_to_signal(sb, correlation_id, sig_id)
        except Exception:
            pass


# ── ML reasoning builder ──────────────────────────────────────────────────────

def build_ml_rejection_reasoning(
    payload: Dict[str, Any],
    win_prob: float,
    features_used: Dict[str, Any],
    note: str,
    ml_min_confidence: float = 0.60,
) -> Dict[str, Any]:
    """Build the ``ai_reasoning`` dict for a signal rejected by the ML guardian."""
    reasoning: Dict[str, Any] = {
        "decision": "rejected",
        "confidence": round(win_prob, 4),
        "threshold": ml_min_confidence,
        "reason": note,
    }
    for k in ("zone_id", "zone_type", "zone_grade", "entry_model", "score"):
        if payload.get(k) is not None:
            reasoning[k if k != "score" else "zone_score"] = payload[k]
    if features_used:
        reasoning["features_used"] = {
            k: float(v) if isinstance(v, (int, float)) else v
            for k, v in features_used.items()
            if v is not None
        }
    return reasoning


# ── Guard notification helper ─────────────────────────────────────────────────

_NOTIFY_GUARD_PREFIXES = (
    "weekly loss limit",
    "monthly loss limit",
    "circuit breaker",
    "profit lock",
    "drawdown scale",
    "spread gate",
)


def notify_guard_activation(
    reason: str,
    symbol: str,
    payload: Dict[str, Any],
) -> None:
    """Fire a Discord/Telegram alert when an important risk guard activates."""
    reason_lower = reason.lower()
    if not any(reason_lower.startswith(p) for p in _NOTIFY_GUARD_PREFIXES):
        return
    try:
        from src.adapters.discord import send_guard_notification_async
        send_guard_notification_async(signal_id=0, symbol=symbol, reason=reason)
    except Exception as _e:
        logger.debug("Guard notification skipped: %s", _e)
