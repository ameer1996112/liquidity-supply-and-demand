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


def _max_position_size(payload: Dict[str, Any]) -> float:
    s = get_settings()
    return _calculate_max_position_size_impl(
        payload,
        account_balance=float(payload.get("account_balance", s.account_balance)),
        risk_percent=float(payload.get("risk_percent", s.risk_percent)),
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

    max_allowed_size = _max_position_size(payload)
    logger.info("Risk Check: size %s vs limit %s", size, round(max_allowed_size, 2))
    if size > max_allowed_size:
        save_result(payload, "risk_rejected", f"Size {size} > Limit {max_allowed_size:.2f}", 0.0)
        logger.warning("RISK REJECTED: %s size %s exceeds limit %s", symbol, size, max_allowed_size)
        return

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
    # Ensemble Brain decision (RF + RAG + LLM)
    # ------------------------------------------------------------------
    ai_result = ensemble_decision(payload)

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

    # If we reach here, either AI said GO or shadow mode is allowing it
    win_prob = float(ai_result.get("rf_prob", 0.0))
    try:
        dry_run = not getattr(s, "live_trading_enabled", False)
        if dry_run:
            logger.info("DRY_RUN: LIVE_TRADING=false — saving alert + notify only")
        logic.process_trade(payload, dry_run=dry_run)
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
    logger.info("=" * 60)

    backoff = 5
    redis_client = get_redis()
    while True:
        try:
            task = redis_client.blpop(QUEUE_NAME, timeout=5)
            backoff = 5
            if task is None:
                continue
            _key, payload_str = task
            payload = json.loads(payload_str)
            if payload.get("event_type") == "exit":
                logger.info("Exit event for %s - skipping", payload.get("symbol"))
                continue
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
