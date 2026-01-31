"""
Trade Executor (Consumer) with Trinity Engine Integration.

Architecture:
1. Loop: blpop trading_queue -> parse JSON
2. TRINITY ENGINE (if enabled):
   a. CORRELATION GUARD: Check portfolio exposure, reject correlated positions
   b. RISK GUARDIAN: Check daily loss, drawdown, per-trade risk limits
   c. MARKET ADAPTER: Validate/recalculate lot size for asset class
3. PINE GUARDIAN: Validate position sizing against Pine Script formulas
4. ML GUARDIAN: Predict win probability using trained RandomForest model
5. AI GUARDIAN: If enabled, validate against Liquidity S&D rules (LLM-based)
6. Execute: logic.process_trade(data)

On failure: log to Supabase with rejection reason and continue.
Worker never crashes - robust against all errors.

Trinity Engine Rules Enforced:
- CORRELATION: Max 3 positions, no currency over-exposure, no correlated groups
- RISK GUARDIAN: 4% daily loss limit, 8% drawdown kill switch, 1% max per trade
- MARKET ADAPTER: Asset-specific lot sizing (Forex, Gold, Indices, Crypto)

ML Guardian Rules Enforced:
- Win probability prediction using trained RandomForest model
- Rejects trades with win probability < ML_MIN_CONFIDENCE (default 60%)

AI Guardian Rules Enforced (LLM-based):
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

# Load .env from backend directory
from dotenv import load_dotenv
_backend = Path(__file__).resolve().parent
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

# Global ML Guardian instance (lazy initialized)
_ml_guardian = None
_ml_guardian_initialized = False

# Global Pine Guardian instance (lazy initialized)
_pine_guardian = None
_pine_guardian_initialized = False

# Global Trinity Engine instances (lazy initialized)
_risk_guardian = None
_risk_guardian_initialized = False
_correlation_manager = None
_correlation_manager_initialized = False
_market_adapter = None
_market_adapter_initialized = False


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
        from backend.ai_guardian import create_ai_guardian_from_settings
        _ai_guardian = create_ai_guardian_from_settings()
        if _ai_guardian:
            logger.info("AI Guardian initialized successfully")
        else:
            logger.info("AI Guardian disabled or not configured")
    except Exception as e:
        logger.error(f"Failed to initialize AI Guardian: {e}")
        _ai_guardian = None

    return _ai_guardian


def _get_ml_guardian():
    """
    Lazy-load ML Guardian singleton.

    ML Guardian uses the trained RandomForest model to predict
    win probability for incoming trade signals.

    Returns None if:
    - ML_GUARDIAN_ENABLED=False
    - Model files not found
    - Import/initialization error
    """
    global _ml_guardian, _ml_guardian_initialized

    if _ml_guardian_initialized:
        return _ml_guardian

    _ml_guardian_initialized = True

    try:
        from backend.ml_guardian import create_ml_guardian_from_settings
        _ml_guardian = create_ml_guardian_from_settings()
        if _ml_guardian:
            logger.info("ML Guardian initialized successfully")
        else:
            logger.info("ML Guardian disabled or model not found")
    except Exception as e:
        logger.error(f"Failed to initialize ML Guardian: {e}")
        _ml_guardian = None

    return _ml_guardian


def _get_pine_guardian():
    """
    Lazy-load Pine Guardian singleton.

    Pine Guardian validates position sizing and risk limits against
    the exact formulas from SND_Strategy.pine (Source of Truth).

    Returns:
        PineGuardian instance or None on error
    """
    global _pine_guardian, _pine_guardian_initialized

    if _pine_guardian_initialized:
        return _pine_guardian

    _pine_guardian_initialized = True

    try:
        from backend.pine_guardian import create_pine_guardian_from_settings
        _pine_guardian = create_pine_guardian_from_settings()
        logger.info("Pine Guardian initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Pine Guardian: {e}")
        _pine_guardian = None

    return _pine_guardian


# ══════════════════════════════════════════════════════════
# TRINITY ENGINE LAZY INITIALIZATION
# ══════════════════════════════════════════════════════════


def _get_risk_guardian():
    """
    Lazy-load Risk Guardian singleton.

    Risk Guardian enforces prop firm risk limits:
    - 4% daily loss limit
    - 8% total drawdown kill switch
    - 1% max risk per trade

    Returns:
        RiskGuardian instance or None on error
    """
    global _risk_guardian, _risk_guardian_initialized

    if _risk_guardian_initialized:
        return _risk_guardian

    _risk_guardian_initialized = True

    try:
        from backend.risk_guardian import create_risk_guardian_from_settings
        _risk_guardian = create_risk_guardian_from_settings()
        logger.info("Risk Guardian initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Risk Guardian: {e}")
        _risk_guardian = None

    return _risk_guardian


def _get_correlation_manager():
    """
    Lazy-load Correlation Manager singleton.

    Correlation Manager prevents over-exposure:
    - Max 3 open positions
    - No duplicate same-direction positions
    - No currency over-exposure
    - No correlated group stacking

    Returns:
        CorrelationManager instance or None on error
    """
    global _correlation_manager, _correlation_manager_initialized

    if _correlation_manager_initialized:
        return _correlation_manager

    _correlation_manager_initialized = True

    try:
        from backend.correlation_manager import create_correlation_manager_from_settings
        _correlation_manager = create_correlation_manager_from_settings()
        logger.info("Correlation Manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Correlation Manager: {e}")
        _correlation_manager = None

    return _correlation_manager


def _get_market_adapter():
    """
    Lazy-load Market Adapter singleton.

    Market Adapter handles multi-asset lot sizing:
    - Forex: 100,000 units/lot, $10/pip
    - Gold: 100 oz/lot, $1/pip
    - Indices: Variable point values
    - Crypto: Fractional lots

    Returns:
        MarketAdapter instance or None on error
    """
    global _market_adapter, _market_adapter_initialized

    if _market_adapter_initialized:
        return _market_adapter

    _market_adapter_initialized = True

    try:
        from backend.market_adapter import create_market_adapter_from_settings
        _market_adapter = create_market_adapter_from_settings()
        logger.info("Market Adapter initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Market Adapter: {e}")
        _market_adapter = None

    return _market_adapter


# ══════════════════════════════════════════════════════════
# TRINITY ENGINE VALIDATION FUNCTIONS
# ══════════════════════════════════════════════════════════


def _run_correlation_check(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Run Correlation Manager check on trade signal.

    Validates portfolio exposure to prevent:
    - Exceeding max open positions (default: 3)
    - Currency over-exposure (double USD, etc.)
    - Correlated position stacking

    Args:
        data: Raw trade payload from queue

    Returns:
        Tuple of (should_proceed, rejection_reason, details_dict)
    """
    manager = _get_correlation_manager()

    if manager is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "Correlation Manager not initialized"}

    try:
        from backend.correlation_manager import get_active_positions_from_db

        # Fetch active positions from DB
        active_positions = get_active_positions_from_db()

        # Run correlation check
        result = manager.check(
            symbol=str(data.get("symbol", "UNKNOWN")),
            side=str(data.get("side", "buy")),
            active_positions=active_positions,
            data=data,
        )

        result_dict = {
            "passed": result.passed,
            "rejection_reason": result.rejection_reason,
            "rejection_message": result.rejection_message,
            "exposure_details": result.exposure_details,
        }

        if not result.passed:
            return False, result.rejection_message, result_dict

        return True, None, result_dict

    except Exception as e:
        logger.error(f"Correlation Manager error: {e} - allowing trade (fail-open)")
        return True, None, {"decision": "SKIP_CHECK", "reason": f"Error: {str(e)[:100]}"}


def _run_risk_guardian_check(
    data: Dict[str, Any],
    current_equity: float,
    daily_pnl: float,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Run Risk Guardian check on trade signal.

    Validates against prop firm risk limits:
    - Daily loss limit (4%)
    - Total drawdown kill switch (8%)
    - Per-trade risk limit (1%)

    Args:
        data: Raw trade payload from queue
        current_equity: Current account equity in USD
        daily_pnl: Today's P&L in USD

    Returns:
        Tuple of (should_proceed, rejection_reason, details_dict)
    """
    guardian = _get_risk_guardian()

    if guardian is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "Risk Guardian not initialized"}

    try:
        result = guardian.check(
            data=data,
            current_equity=current_equity,
            daily_pnl=daily_pnl,
        )

        result_dict = {
            "passed": result.passed,
            "rejection_reason": result.rejection_reason,
            "rejection_message": result.rejection_message,
            "risk_metrics": result.risk_metrics,
        }

        if not result.passed:
            return False, result.rejection_message, result_dict

        return True, None, result_dict

    except Exception as e:
        logger.error(f"Risk Guardian error: {e} - allowing trade (fail-open)")
        return True, None, {"decision": "SKIP_CHECK", "reason": f"Error: {str(e)[:100]}"}


def _run_market_adapter_validation(
    data: Dict[str, Any],
    risk_usd: float,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[float]]:
    """
    Run Market Adapter validation on trade signal.

    Validates/recalculates lot size for the asset class:
    - Forex: Standard pip value calculations
    - Gold: 100 oz contracts
    - Indices: Point value handling
    - Crypto: Fractional lots

    Args:
        data: Raw trade payload from queue
        risk_usd: Risk amount in USD for this trade

    Returns:
        Tuple of (should_proceed, rejection_reason, details_dict, calculated_lots)
    """
    adapter = _get_market_adapter()

    if adapter is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "Market Adapter not initialized"}, None

    try:
        symbol = str(data.get("symbol", "UNKNOWN"))
        entry = float(data.get("entry", 0))
        stop_loss = float(data.get("sl", 0))
        requested_lots = float(data.get("size", 0))

        if entry <= 0 or stop_loss <= 0:
            return True, None, {"decision": "SKIP_CHECK", "reason": "Invalid entry/SL"}, None

        # Calculate correct lot size
        result = adapter.calculate_lot_size(
            symbol=symbol,
            entry_price=entry,
            stop_loss=stop_loss,
            risk_usd=risk_usd,
        )

        result_dict = {
            "lots": result.lots,
            "lots_rounded": result.lots_rounded,
            "risk_usd": result.risk_usd,
            "asset_class": result.asset_class,
            "pip_value": result.pip_value,
            "sl_pips": result.sl_pips,
            "calculation_details": result.calculation_details,
            "requested_lots": requested_lots,
        }

        # Validate requested lots against calculated (10% variance threshold)
        is_valid, error_msg, _ = adapter.validate_lot_size(
            symbol=symbol,
            requested_lots=requested_lots,
            entry_price=entry,
            stop_loss=stop_loss,
            risk_usd=risk_usd,
            variance_threshold=0.10,  # 10% allowed
        )

        if not is_valid and error_msg:
            # Log warning but don't reject - use calculated size
            logger.warning(f"Market Adapter: {error_msg}")
            result_dict["lot_size_warning"] = error_msg

        return True, None, result_dict, result.lots_rounded

    except Exception as e:
        logger.error(f"Market Adapter error: {e} - allowing trade with original size")
        return True, None, {"decision": "SKIP_CHECK", "reason": f"Error: {str(e)[:100]}"}, None


def _run_pine_validation(data: Dict[str, Any], current_balance: float) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Run Pine Guardian validation on trade signal.

    Validates position sizing against Pine Script formulas to catch:
    - Fat finger errors (oversized positions)
    - Calculation bugs in TradingView signals
    - Daily limit violations

    Args:
        data: Raw trade payload from queue
        current_balance: Current account balance in USD

    Returns:
        Tuple of (should_proceed, rejection_reason, details_dict)
        - should_proceed: True to continue, False to reject
        - rejection_reason: Human-readable reason if rejected
        - details_dict: Validation details for logging
    """
    guardian = _get_pine_guardian()

    if guardian is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "Pine Guardian not initialized"}

    try:
        from backend.pine_guardian import ValidationResult

        result = guardian.validate_signal(data, current_balance)

        result_dict = {
            "is_valid": result.is_valid,
            "rejection_reason": result.rejection_reason.value if result.rejection_reason else None,
            "calculated_lots": result.calculated_lots,
            "requested_lots": result.requested_lots,
            "variance_percent": result.variance_percent,
            "details": result.details,
        }

        if not result.is_valid:
            return False, result.rejection_message, result_dict

        return True, None, result_dict

    except Exception as e:
        logger.error(f"Pine Guardian error: {e} - allowing trade (fail-open)")
        return True, None, {"decision": "SKIP_CHECK", "reason": f"Error: {str(e)[:100]}"}


def _run_ml_guardian_check(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Run ML Guardian check on trade signal.

    Uses the trained RandomForest model to predict win probability.
    Rejects trades with win probability below ML_MIN_CONFIDENCE threshold.

    Args:
        data: Raw trade payload from queue

    Returns:
        Tuple of (should_proceed, rejection_reason, details_dict)
    """
    from backend.config import get_settings

    settings = get_settings()

    # Check if ML Guardian is enabled
    if not getattr(settings, 'ml_guardian_enabled', True):
        return True, None, {"decision": "SKIP_CHECK", "reason": "ML Guardian disabled"}

    guardian = _get_ml_guardian()

    if guardian is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "ML Guardian not initialized"}

    try:
        # Run ML prediction
        should_proceed, win_probability, ml_result = guardian.analyze(data)

        if not should_proceed:
            min_conf = getattr(settings, 'ml_min_confidence', 0.60)
            reason = (
                f"ML Guardian REJECT: win probability {win_probability:.1%} "
                f"< threshold {min_conf:.1%}"
            )
            return False, reason, ml_result

        return True, None, ml_result

    except Exception as e:
        logger.error(f"ML Guardian error: {e} - allowing trade (fail-open)")
        return True, None, {"decision": "SKIP_CHECK", "reason": f"Error: {str(e)[:100]}"}


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
    from backend.config import get_settings

    guardian = _get_ai_guardian()

    # If AI Guardian is disabled or unavailable, allow trade through
    if guardian is None:
        return True, None, {"decision": "SKIP_CHECK", "reason": "AI Guardian disabled"}

    try:
        from backend.ai_guardian import build_trade_context, AIDecision

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
    Main worker loop with Trinity Engine pipeline.

    Execution Pipeline:
    1. Connect to Redis
    2. Pop trade signals from queue
    3. TRINITY ENGINE (if enabled):
       a. Correlation Guard - Check portfolio exposure
       b. Risk Guardian - Check daily loss, drawdown, per-trade risk
       c. Market Adapter - Validate/recalculate lot size
    4. Pine Guardian - Validate position sizing
    5. ML Guardian - Predict win probability (RandomForest model)
    6. AI Guardian - Validate against Liquidity S&D rules (LLM)
    7. Execute trade
    8. Log results to Supabase
    """
    from backend.config import get_settings
    from backend import logic
    from backend import supabase_db
    import redis

    s = get_settings()
    r = redis.from_url(s.redis_url, decode_responses=True)

    # Log Trinity Engine status
    trinity_enabled = getattr(s, "trinity_enabled", True)
    if trinity_enabled:
        logger.info(
            f"Worker started with TRINITY ENGINE ENABLED "
            f"(max_daily_loss={getattr(s, 'trinity_max_daily_loss_pct', 4.0)}%, "
            f"max_drawdown={getattr(s, 'trinity_max_drawdown_pct', 8.0)}%, "
            f"max_positions={getattr(s, 'trinity_max_positions', 3)})"
        )
    else:
        logger.info("Worker started with Trinity Engine DISABLED")

    # Log ML Guardian status
    ml_guardian_enabled = getattr(s, "ml_guardian_enabled", True)
    ml_min_confidence = getattr(s, "ml_min_confidence", 0.60)
    if ml_guardian_enabled:
        logger.info(
            f"ML Guardian ENABLED "
            f"(min_confidence={ml_min_confidence:.0%})"
        )
    else:
        logger.info("ML Guardian DISABLED (passthrough mode)")

    # Log AI Guardian status (LLM-based)
    if s.ai_filter_enabled:
        logger.info(
            f"AI Guardian (LLM) ENABLED "
            f"(provider={s.ai_provider}, min_confidence={s.ai_min_confidence}%)"
        )
    else:
        logger.info("AI Guardian (LLM) DISABLED (passthrough mode)")

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

        # === VALIDATION PIPELINE ===
        # Skip for exit events (only validate entries)
        is_entry_event = data.get("event_type") != "exit"

        if is_entry_event:
            # ══════════════════════════════════════════════════════════
            # STEP 1: CORRELATION GUARD (Trinity Engine)
            # ══════════════════════════════════════════════════════════
            if trinity_enabled:
                try:
                    should_proceed, rejection_reason, correlation_result = _run_correlation_check(data)

                    if not should_proceed:
                        # Log rejection to Supabase
                        try:
                            supabase_db.log_correlation_rejection(data, rejection_reason, correlation_result)
                        except Exception as log_err:
                            logger.error(f"Failed to log Correlation rejection to Supabase: {log_err}")

                        logger.warning(
                            f"Correlation Guard REJECTED: {data.get('symbol')} {data.get('side')} "
                            f"- {rejection_reason}"
                        )
                        continue  # Skip this trade

                    # Append correlation details to data for logging
                    if correlation_result:
                        data["correlation_check"] = correlation_result.get("exposure_details", {})

                    logger.info(
                        f"Correlation Guard PASSED: {data.get('symbol')} {data.get('side')} "
                        f"(positions: {correlation_result.get('exposure_details', {}).get('total_positions', 0)}/"
                        f"{correlation_result.get('exposure_details', {}).get('max_positions', 3)})"
                    )

                except Exception as e:
                    logger.error(f"Correlation Guard error: {e} - allowing trade (fail-open)")

            # ══════════════════════════════════════════════════════════
            # STEP 2: RISK GUARDIAN (Trinity Engine)
            # ══════════════════════════════════════════════════════════
            if trinity_enabled:
                try:
                    # Get current daily P&L from DB
                    daily_pnl = supabase_db.get_daily_pnl()

                    should_proceed, rejection_reason, risk_result = _run_risk_guardian_check(
                        data,
                        current_equity=s.account_balance,
                        daily_pnl=daily_pnl,
                    )

                    if not should_proceed:
                        # Log rejection to Supabase
                        try:
                            supabase_db.log_risk_guardian_rejection(data, rejection_reason, risk_result)
                        except Exception as log_err:
                            logger.error(f"Failed to log Risk Guardian rejection to Supabase: {log_err}")

                        logger.warning(
                            f"Risk Guardian REJECTED: {data.get('symbol')} {data.get('side')} "
                            f"- {rejection_reason}"
                        )
                        continue  # Skip this trade

                    # Append risk details to data for logging
                    if risk_result:
                        data["risk_check"] = risk_result.get("risk_metrics", {})

                    logger.info(
                        f"Risk Guardian PASSED: {data.get('symbol')} {data.get('side')} "
                        f"(daily_pnl=${daily_pnl:,.2f}, drawdown="
                        f"{risk_result.get('risk_metrics', {}).get('total_drawdown_pct', 0):.2f}%)"
                    )

                except Exception as e:
                    logger.error(f"Risk Guardian error: {e} - allowing trade (fail-open)")

            # ══════════════════════════════════════════════════════════
            # STEP 3: MARKET ADAPTER (Trinity Engine)
            # ══════════════════════════════════════════════════════════
            if trinity_enabled:
                try:
                    # Calculate risk amount for this trade
                    risk_usd = s.account_balance * (s.risk_percent / 100.0)

                    should_proceed, rejection_reason, adapter_result, calculated_lots = _run_market_adapter_validation(
                        data, risk_usd=risk_usd
                    )

                    # Market Adapter doesn't reject, but may adjust lot size
                    if adapter_result:
                        data["adapter_asset_class"] = adapter_result.get("asset_class")
                        data["adapter_calculated_lots"] = calculated_lots
                        data["adapter_sl_pips"] = adapter_result.get("sl_pips")

                        # Log any lot size warnings
                        if adapter_result.get("lot_size_warning"):
                            logger.warning(f"Market Adapter: {adapter_result['lot_size_warning']}")

                    logger.info(
                        f"Market Adapter: {data.get('symbol')} ({adapter_result.get('asset_class', 'unknown')}) "
                        f"-> {calculated_lots or data.get('size')} lots "
                        f"(SL: {adapter_result.get('sl_pips', 0):.1f} pips)"
                    )

                except Exception as e:
                    logger.error(f"Market Adapter error: {e} - using original lot size")

            # ══════════════════════════════════════════════════════════
            # STEP 4: PINE GUARDIAN (Position Sizing Validation)
            # ══════════════════════════════════════════════════════════
            try:
                should_proceed, rejection_reason, pine_result = _run_pine_validation(
                    data, current_balance=s.account_balance
                )

                if not should_proceed:
                    # Log rejection to Supabase
                    try:
                        supabase_db.log_pine_rejection(data, rejection_reason, pine_result)
                    except Exception as log_err:
                        logger.error(f"Failed to log Pine Guardian rejection to Supabase: {log_err}")

                    logger.warning(
                        f"Pine Guardian REJECTED: {data.get('symbol')} {data.get('side')} "
                        f"size={data.get('size')} - {rejection_reason}"
                    )
                    continue  # Skip this trade

                # Append Pine validation details to data for logging
                if pine_result:
                    data["pine_calculated_lots"] = pine_result.get("calculated_lots")
                    data["pine_variance_pct"] = pine_result.get("variance_percent")

                logger.info(
                    f"Pine Guardian APPROVED: {data.get('symbol')} {data.get('side')} "
                    f"size={data.get('size')} (variance={pine_result.get('variance_percent', 0):.1f}%)"
                )

            except Exception as e:
                logger.error(f"Pine Guardian wrapper error: {e} - allowing trade (fail-open)")

            # ══════════════════════════════════════════════════════════
            # STEP 5: ML GUARDIAN (Win Probability Prediction)
            # ══════════════════════════════════════════════════════════
            # Uses trained RandomForest model to predict win probability
            # Only runs in PAPER or LIVE mode (not DRY_RUN)
            run_mode = "PAPER" if s.paper_trading_enabled else "LIVE"

            if run_mode in ("PAPER", "LIVE"):
                try:
                    should_proceed, rejection_reason, ml_result = _run_ml_guardian_check(data)

                    # Always save ML confidence to data for logging
                    if ml_result:
                        data["ml_win_probability"] = ml_result.get("win_probability", 0)
                        data["ml_decision"] = ml_result.get("decision")

                    if not should_proceed:
                        # Log rejection to Supabase with ML confidence score
                        try:
                            supabase_db.log_ml_rejection(data, rejection_reason, ml_result)
                        except Exception as log_err:
                            logger.error(f"Failed to log ML Guardian rejection to Supabase: {log_err}")

                        logger.warning(
                            f"ML Guardian REJECTED: {data.get('symbol')} {data.get('side')} "
                            f"win_prob={ml_result.get('win_probability', 0):.1%} - {rejection_reason}"
                        )
                        continue  # Skip this trade

                    logger.info(
                        f"ML Guardian APPROVED: {data.get('symbol')} {data.get('side')} "
                        f"(win_prob={ml_result.get('win_probability', 0):.1%})"
                    )

                except Exception as e:
                    logger.error(f"ML Guardian wrapper error: {e} - allowing trade (fail-open)")

        # ══════════════════════════════════════════════════════════
        # STEP 6: AI GUARDIAN (Liquidity S&D Validation)
        # ══════════════════════════════════════════════════════════
        # Skip AI check for exit events (only validate entries)

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

        # ══════════════════════════════════════════════════════════
        # STEP 7: EXECUTE TRADE
        # ══════════════════════════════════════════════════════════
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
