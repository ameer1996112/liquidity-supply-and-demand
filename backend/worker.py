"""
Trade Executor (Consumer) with AI Guardian Integration.

Architecture:
1. Loop: blpop trading_queue -> parse JSON
2. AI GUARDIAN: If enabled, validate signal against Liquidity S&D rules
   - REJECT: Log to Supabase as status=ai_rejected and continue
   - APPROVE: Proceed to execution with AI reasoning appended to alerts
   - SKIP_CHECK: On timeout/error, allow trade (fail-open)
3. Execute: logic.process_trade(data)

On failure: log to Supabase as status=FAILED (execution_failed) and continue.
Worker never crashes - robust against all errors.

AI Guardian Rules Enforced:
- THE INDUCEMENT RULE: Liquidity must be swept before entry (liq_swept=True)
- THE ARRIVAL RULE: Price must arrive aggressively, not compressed
- THE INVALIDATION RULE: Entry candle must reject, not close inside zone
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Ensure backend is on path and .env is loaded
_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
os.chdir(_backend)

from dotenv import load_dotenv
load_dotenv(_backend / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

QUEUE_NAME = "trading_queue"
REDIS_RETRY_SEC = 5
REDIS_RETRY_MAX_SEC = 60

# Global AI Guardian instance (lazy initialized)
_ai_guardian = None
_ai_guardian_initialized = False


def _get_ai_guardian():
    """
    Lazy-load AI Guardian singleton.

    Returns None if:
    - AI_FILTER_ENABLED=False
    - No API key configured
    - Import/initialization error
    """
    global _ai_guardian, _ai_guardian_initialized

    if _ai_guardian_initialized:
        return _ai_guardian

    _ai_guardian_initialized = True

    try:
        from ai_guardian import create_ai_guardian_from_settings
        _ai_guardian = create_ai_guardian_from_settings()
        if _ai_guardian:
            logger.info("AI Guardian initialized successfully")
        else:
            logger.info("AI Guardian disabled or not configured")
    except Exception as e:
        logger.error(f"Failed to initialize AI Guardian: {e}")
        _ai_guardian = None

    return _ai_guardian


async def _run_ai_validation(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Run AI Guardian validation on trade signal.

    Args:
        data: Raw trade payload from queue

    Returns:
        Tuple of (should_proceed, rejection_reason, ai_result_dict)
        - should_proceed: True to execute trade, False to skip
        - rejection_reason: Human-readable reason if rejected
        - ai_result_dict: Full AI analysis result for logging
    """
    from config import get_settings

    guardian = _get_ai_guardian()

    # If AI Guardian is disabled or unavailable, allow trade through
    if guardian is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "AI Guardian disabled"}

    try:
        from ai_guardian import build_trade_context, AIDecision

        # Build context from trade data
        context = build_trade_context(data)

        # Run AI analysis
        result = await guardian.analyze_signal(context)

        # Convert to dict for logging
        result_dict = {
            "decision": result.decision.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "rule_checks": result.rule_checks,
        }

        # Check decision
        if result.decision == AIDecision.REJECT:
            settings = get_settings()
            # Also check confidence threshold
            if result.confidence < settings.ai_min_confidence:
                reason = f"AI REJECT (confidence {result.confidence}% < {settings.ai_min_confidence}%): {result.reasoning}"
            else:
                reason = f"AI REJECT: {result.reasoning}"
            return False, reason, result_dict

        # Fail-open: AI returned APPROVE due to error/timeout (e.g. openai not installed)
        # Do not apply confidence threshold so the trade is allowed
        is_fail_open = (
            "SKIP_CHECK" in (result.reasoning or "")
            or "fail-open" in (result.reasoning or "").lower()
            or result.rule_checks.get("error")
            or result.rule_checks.get("timeout")
        )
        if is_fail_open:
            return True, None, result_dict

        # APPROVE - check confidence threshold (only for real AI decisions)
        settings = get_settings()
        if result.confidence < settings.ai_min_confidence:
            reason = f"AI confidence too low ({result.confidence}% < {settings.ai_min_confidence}%): {result.reasoning}"
            result_dict["decision"] = "REJECT_LOW_CONFIDENCE"
            return False, reason, result_dict

        # Approved
        return True, None, result_dict

    except Exception as e:
        logger.error(f"AI validation error: {e}")
        # Fail-open: allow trade on error
        return True, None, {"decision": "SKIP_CHECK", "reason": f"Error: {str(e)[:100]}"}


def _sync_run_ai_validation(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Synchronous wrapper for async AI validation.

    Uses asyncio.run() to execute the async validation in a sync context.
    """
    return asyncio.run(_run_ai_validation(data))


def run():
    """
    Main worker loop.

    1. Connect to Redis
    2. Pop trade signals from queue
    3. Run AI Guardian validation (if enabled)
    4. Execute or reject trade
    5. Log results to Supabase
    """
    from config import get_settings
    import redis
    import logic
    import supabase_db

    s = get_settings()
    r = redis.from_url(s.redis_url, decode_responses=True)

    # Log AI Guardian status
    if s.ai_filter_enabled:
        logger.info(
            f"Worker started with AI Guardian ENABLED "
            f"(provider={s.ai_provider}, min_confidence={s.ai_min_confidence}%)"
        )
    else:
        logger.info("Worker started with AI Guardian DISABLED (passthrough mode)")

    logger.info(f"Listening on queue={QUEUE_NAME}")

    backoff = REDIS_RETRY_SEC
    while True:
        try:
            result = r.blpop(QUEUE_NAME, timeout=30)
            backoff = REDIS_RETRY_SEC
            if result is None:
                continue
            _key, payload_str = result
            data = json.loads(payload_str)
        except (redis.exceptions.ConnectionError, OSError) as e:
            logger.warning(
                "Redis unreachable (%s). Retry in %ds. Ensure Redis is in the same Railway project and linked.",
                e.__class__.__name__,
                backoff,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, REDIS_RETRY_MAX_SEC)
            continue
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from queue: %s", e)
            continue
        except Exception as e:
            logger.exception("Queue read error: %s", e)
            continue

        # === AI GUARDIAN VALIDATION ===
        # Skip AI check for exit events (only validate entries)
        is_entry_event = data.get("event_type") != "exit"

        if is_entry_event and s.ai_filter_enabled:
            try:
                should_proceed, rejection_reason, ai_result = _sync_run_ai_validation(data)

                if not should_proceed:
                    # Log rejection to Supabase
                    try:
                        supabase_db.log_ai_rejection(data, rejection_reason, ai_result)
                    except Exception as log_err:
                        logger.error(f"Failed to log AI rejection to Supabase: {log_err}")

                    logger.warning(
                        f"AI Guardian REJECTED: {data.get('symbol')} {data.get('side')} "
                        f"zone_id={data.get('zone_id')} - {rejection_reason}"
                    )
                    continue  # Skip this trade

                # Append AI reasoning to data for Discord/Telegram alerts
                if ai_result and ai_result.get("reasoning"):
                    data["ai_reasoning"] = ai_result.get("reasoning")
                    data["ai_confidence"] = ai_result.get("confidence")
                    data["ai_decision"] = ai_result.get("decision")

                logger.info(
                    f"AI Guardian APPROVED: {data.get('symbol')} {data.get('side')} "
                    f"zone_id={data.get('zone_id')} (confidence={ai_result.get('confidence', 'N/A')}%)"
                )

            except Exception as e:
                logger.error(f"AI validation wrapper error: {e} - allowing trade (fail-open)")
                # Fail-open: continue to execution on any error

        # === EXECUTE TRADE ===
        try:
            logic.process_trade(data)
        except Exception as e:
            logger.exception("EXECUTION_FAILED: %s", e)
            try:
                supabase_db.log_execution_failure(data, str(e))
            except Exception as log_err:
                logger.error("Failed to log EXECUTION_FAILED to Supabase: %s", log_err)


if __name__ == "__main__":
    run()
