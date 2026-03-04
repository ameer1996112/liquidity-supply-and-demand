"""
Supabase Database Helper
Replaces SQLite with Supabase for persistent cloud storage

V2.0 - Added:
- run_mode / run_id for live vs backtest separation
- trade_key for entry↔exit correlation
- entry_time / exit_time for lifecycle tracking
- filter_reason_json for structured filter reasons
- pnl_usd for actual USD P&L from strategy engine
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from project root
_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env")

logger = logging.getLogger(__name__)

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')

# Initialize Supabase client
supabase: Optional[Client] = None

def init_supabase() -> Client:
    """Initialize Supabase client"""
    global supabase, SUPABASE_URL, SUPABASE_KEY

    # Forcefully re-read from environment at init time to bypass any early-binding issues
    url = (os.environ.get('SUPABASE_URL') or SUPABASE_URL or "").strip('"\'').strip()
    raw_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('SUPABASE_KEY') or SUPABASE_KEY or ""
    
    key = raw_key.strip().strip('"\'').strip()
    if key.upper().startswith("SUPA") and "=" in key[:50]:
        key = key.split("=", 1)[-1].strip().strip('"\'').strip()
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY (or ANON_KEY/SERVICE_ROLE_KEY) must be set in environment variables")
        
    SUPABASE_URL = url
    SUPABASE_KEY = key

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase client initialized successfully")
        return supabase
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        raise


def get_supabase() -> Client:
    """Get Supabase client, initializing if needed"""
    global supabase
    if supabase is None:
        return init_supabase()
    return supabase


def save_alert(
    data: dict,
    mode: str = 'manual',
    filter_reasons: List[str] = None,
    broker_profile_id: int | None = None,
) -> int:
    """
    Save alert to Supabase trading_signals table.

    Args:
        data: Alert data dictionary
        mode: Trading mode ('manual', 'paper', 'live')
        filter_reasons: List of filter reason codes (if filtered)
        broker_profile_id: Optional; for multi-account, one row per (trade_key, broker_profile_id)

    Returns:
        alert_id: The ID of the inserted row
    """
    if not supabase:
        init_supabase()

    # Calculate R:R
    entry = float(data['entry'])
    sl = float(data['sl'])
    tp = float(data['tp'])
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr_ratio = reward / risk if risk > 0 else 0

    # Extract run_mode and run_id from payload (default to LIVE for backward compatibility)
    run_mode = data.get('run_mode', 'LIVE')
    run_id = data.get('run_id', 'live-default')
    trade_key = data.get('trade_key', '')

    execution_source = 'signal_only'
    if run_mode == 'LIVE':
        execution_source = 'metaapi'
    elif run_mode == 'PAPER':
        execution_source = 'paper'

    # Extract entry_time from bar_time (or fallback to server time)
    entry_time = data.get('bar_time', datetime.utcnow().isoformat())

    # Prepare insert data
    insert_data = {
        'symbol': data['symbol'],
        'side': data['side'],
        'entry': entry,
        'sl': sl,
        'tp': tp,
        'size': data['size'],
        'rr_ratio': rr_ratio,
        'zone_id': data.get('zone_id'),
        'zone_type': data.get('zone_type'),
        'zone_top': data.get('zone_top'),
        'zone_bottom': data.get('zone_bottom'),
        'zone_size_pips': data.get('zone_size_pips'),
        'entry_model': data.get('entry_model'),
        'liq_swept': bool(data.get('liq_swept', False)),
        'target_swept': bool(data.get('target_swept', False)),
        'caused_sweep': bool(data.get('caused_sweep', False)),
        'is_accuracy': bool(data.get('is_accuracy', False)),
        'mode': mode,
        'status': 'PENDING',
        'execution_source': execution_source,
        # V7.1 AI Features
        'score': data.get('score'),
        'freshness': data.get('freshness'),
        'session': data.get('session'),
        'atr_ratio': data.get('atr_ratio'),
        'trend': data.get('trend'),
        'rsi': data.get('rsi'),
        'htf_trend': data.get('htf_trend'),
        'rvol': data.get('rvol'),
        'adx': data.get('adx'),
        'touch_count': data.get('touch_count'),
        'base_quality': data.get('base_quality'),
        'departure_strength': data.get('departure_strength'),
        'liquidity_distance': data.get('liquidity_distance'),
        'liquidity_spread': data.get('liquidity_spread'),
        'return_strength': data.get('return_strength'),
        'liquidity_distance_pips': data.get('liquidity_distance_pips'),
        'liquidity_spread_pips': data.get('liquidity_spread_pips'),
        # V2.0 Telemetry Fields
        'run_mode': run_mode,
        'run_id': run_id,
        'trade_key': trade_key,
        'entry_time': entry_time,
    }

    # Sprint 6.2: Persist advanced strategy vocabulary hints when present.
    # These columns are optional and added via migrations/037_signal_actions.sql.
    action = data.get('action')
    if action is not None:
        insert_data['signal_action'] = str(action)
    order_type = data.get('order_type')
    if order_type is not None:
        insert_data['order_type'] = str(order_type)
    if 'trailing_stop' in data:
        insert_data['trailing_stop'] = data.get('trailing_stop')
    if 'multi_tp' in data:
        insert_data['multi_tp'] = data.get('multi_tp')
    if 'partial_close_percent' in data:
        insert_data['partial_close_percent'] = data.get('partial_close_percent')
    if broker_profile_id is not None:
        insert_data['broker_profile_id'] = broker_profile_id

    # Add filter reasons if provided
    if filter_reasons:
        insert_data['filter_reason_json'] = json.dumps(filter_reasons)

    # Optional: attach AI ensemble reasoning + confidence if present on the payload
    ai_reasoning = data.get('ai_reasoning')
    if ai_reasoning is not None:
        insert_data['ai_reasoning'] = ai_reasoning
    ai_conf = data.get('ai_confidence')
    if ai_conf is not None:
        # Stored as numeric 0-100; frontend maps this into the AI confidence bar
        insert_data['ai_confidence'] = float(ai_conf)

    try:
        response = supabase.table('trading_signals').insert(insert_data).execute()
        alert_id = response.data[0]['id']
        logger.info(f"✅ Alert saved to Supabase: ID={alert_id}, zone_id={data.get('zone_id')}, run_mode={run_mode}")
        return alert_id
    except Exception as e:
        logger.error(f"❌ Failed to save alert to Supabase: {e}")
        raise


def update_alert_exit(zone_id: int, exit_data: dict, trade_key: str = None) -> bool:
    """
    Update alert with exit telemetry data

    Args:
        zone_id: The zone_id to update (fallback if trade_key not provided)
        exit_data: Dictionary with exit telemetry (outcome, bars_held, pnl_r, etc.)
        trade_key: Unique trade key for correlation (preferred over zone_id)

    Returns:
        bool: True if update successful
    """
    if not supabase:
        init_supabase()

    # Extract exit_time from payload (prefer explicit exit_time over close_time)
    exit_time = exit_data.get('exit_time') or exit_data.get('close_time') or datetime.utcnow().isoformat()

    update_data = {
        'status': 'CLOSED',
        'closed_at': exit_time,
        'outcome': exit_data.get('outcome'),
        'bars_held': exit_data.get('bars_held'),
        'pnl_r': exit_data.get('pnl_r'),
        'pnl_usd': exit_data.get('pnl_usd'),  # Actual USD P&L from strategy engine
        'exit_type': exit_data.get('exit_type'),
        'mae_pips': exit_data.get('mae_pips'),
        'close_price': exit_data.get('close_price'),
        'close_time': exit_data.get('close_time', datetime.utcnow().isoformat()),
        'exit_time': exit_time,
        # Mark the high-level action explicitly for UI consumers (Signals drawer)
        'signal_action': 'exit',
    }

    try:
        # Prefer trade_key correlation if provided and non-empty
        if trade_key and trade_key.strip():
            response = supabase.table('trading_signals').update(update_data).eq('trade_key', trade_key).execute()
            match_type = f"trade_key={trade_key}"
        else:
            # Fallback to zone_id (original behavior)
            response = supabase.table('trading_signals').update(update_data).eq('zone_id', zone_id).execute()
            match_type = f"zone_id={zone_id}"

        if response.data:
            logger.info(f"✅ Alert exit updated: {match_type}, outcome={exit_data.get('outcome')}, pnl_usd={exit_data.get('pnl_usd')}")
            # Sprint 4.3: Create reflection on close (when MEMORY_ENABLED)
            try:
                from src.services.reflection_service import create_reflection_on_close_safe
                row = response.data[0] if isinstance(response.data, list) else response.data
                merged = {**row, **exit_data} if isinstance(row, dict) else None
                trade_id = row.get("id") if isinstance(row, dict) else None
                if trade_id and merged:
                    create_reflection_on_close_safe(supabase, trade_id, merged)
            except Exception:
                pass
            return True
        else:
            logger.warning(f"⚠️  No alert found with {match_type}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to update alert exit: {e}")
        raise


def update_alert_exit_by_trade_key(trade_key: str, exit_data: dict) -> bool:
    """
    Update alert with exit telemetry using trade_key (preferred method)

    Args:
        trade_key: Unique trade key for correlation
        exit_data: Dictionary with exit telemetry

    Returns:
        bool: True if update successful
    """
    return update_alert_exit(zone_id=None, exit_data=exit_data, trade_key=trade_key)


def get_alert_by_zone_id(zone_id: int) -> Optional[Dict[str, Any]]:
    """Get alert by zone_id"""
    if not supabase:
        init_supabase()

    try:
        response = supabase.table('trading_signals').select('*').eq('zone_id', zone_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get alert: {e}")
        return None


def get_alert_by_trade_key(trade_key: str) -> Optional[Dict[str, Any]]:
    """
    Get alert by trade_key (idempotency key).
    Returns full row (including broker_order_id, etc.) for execution paths.
    """
    if not trade_key or not str(trade_key).strip():
        return None
    if not supabase:
        init_supabase()
    try:
        response = supabase.table('trading_signals').select('*').eq('trade_key', trade_key.strip()).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get alert by trade_key: {e}")
        return None


def exists_by_signal_id(signal_id: str) -> bool:
    """Return True if an alert already exists for this signal_id (trade_key). Used for idempotency."""
    return get_alert_by_trade_key(signal_id) is not None


def get_recent_alerts(limit: int = 10, run_mode: str = None, run_id: str = None) -> List[Dict[str, Any]]:
    """
    Get recent alerts ordered by created_at

    Args:
        limit: Maximum number of alerts to return
        run_mode: Filter by run_mode ('LIVE', 'BACKTEST', 'REPLAY'). None = all modes
        run_id: Filter by specific run_id. None = all run_ids

    Returns:
        List of alert dictionaries
    """
    if not supabase:
        init_supabase()

    try:
        query = supabase.table('trading_signals').select('*')

        # Apply run_mode filter (default to LIVE for dashboard)
        if run_mode:
            query = query.eq('run_mode', run_mode)

        # Apply run_id filter if specified
        if run_id:
            query = query.eq('run_id', run_id)

        response = query.order('created_at', desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        logger.error(f"❌ Failed to get recent alerts: {e}")
        return []


def get_alert(alert_id: int) -> Optional[Dict[str, Any]]:
    """Get single alert by ID"""
    if not supabase:
        init_supabase()

    try:
        response = supabase.table('trading_signals').select('*').eq('id', alert_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get alert: {e}")
        return None


def update_alert_status(alert_id: int, status: str, outcome: str = None, pnl: float = None, notes: str = None):
    """Update alert status"""
    if not supabase:
        init_supabase()

    update_data = {
        'status': status,
        'updated_at': datetime.utcnow().isoformat()
    }
    if outcome is not None:
        update_data['outcome'] = outcome
    if pnl is not None:
        update_data['pnl'] = pnl
    if notes is not None:
        update_data['notes'] = notes

    try:
        supabase.table('trading_signals').update(update_data).eq('id', alert_id).execute()
        logger.info(f"✅ Alert status updated: ID={alert_id}, status={status}")
    except Exception as e:
        logger.error(f"❌ Failed to update alert status: {e}")
        raise


def log_execution_failure(data: dict, error: str) -> None:
    """
    Log EXECUTION_FAILED to Supabase: save payload then mark status as execution_failed.
    Used by worker when logic.execute_trade() raises.
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields for save_alert
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    try:
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=None)
        update_alert_status(alert_id, 'ERROR', notes=f"EXECUTION_FAILED: {error}")
        logger.warning(f"EXECUTION_FAILED logged: alert_id={alert_id}, error={error[:200]}")
    except Exception as e:
        logger.error(f"❌ Failed to log execution failure to Supabase: {e}")


def log_ai_rejection(data: dict, rejection_reason: str, ai_result: dict = None) -> Optional[int]:
    """
    Log AI Guardian rejection to Supabase.

    Creates a trading_signals entry with status='ai_rejected' for tracking
    and analysis of AI filtering decisions.

    AI Guardian Rules Enforced:
    - THE INDUCEMENT RULE: Liquidity must be swept before entry
    - THE ARRIVAL RULE: Price must arrive aggressively (not compressed)
    - THE INVALIDATION RULE: Entry candle must show clear rejection

    Args:
        data: Original trade payload from TradingView webhook
        rejection_reason: Human-readable reason for rejection
        ai_result: Full AI analysis result dict with decision, confidence, reasoning, rule_checks

    Returns:
        alert_id if logged successfully, None on error
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    # Build AI-specific filter reasons
    filter_reasons = ["AI_REJECTED"]
    if ai_result:
        filter_reasons.append(f"decision={ai_result.get('decision', 'UNKNOWN')}")
        filter_reasons.append(f"confidence={ai_result.get('confidence', 0)}%")

        # Add rule check failures
        rule_checks = ai_result.get('rule_checks', {})
        for rule, passed in rule_checks.items():
            if not passed:
                filter_reasons.append(f"FAILED:{rule}")

    try:
        # Save alert with ai_rejected status
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=filter_reasons)

        # Build notes with full AI analysis
        notes_parts = [f"AI_REJECTION: {rejection_reason}"]
        if ai_result:
            notes_parts.append(f"Confidence: {ai_result.get('confidence', 0)}%")
            notes_parts.append(f"Reasoning: {ai_result.get('reasoning', 'N/A')}")
            if ai_result.get('rule_checks'):
                notes_parts.append(f"Rule Checks: {json.dumps(ai_result['rule_checks'])}")

        notes = " | ".join(notes_parts)

        # Update status to ai_rejected
        update_alert_status(alert_id, 'ai_rejected', notes=notes[:1000])  # Truncate if too long

        logger.info(
            f"✅ AI rejection logged: alert_id={alert_id}, "
            f"symbol={data.get('symbol')}, zone_id={data.get('zone_id')}, "
            f"reason={rejection_reason[:100]}"
        )
        return alert_id

    except Exception as e:
        logger.error(f"❌ Failed to log AI rejection to Supabase: {e}")
        return None


def log_ml_rejection(data: dict, rejection_reason: str, ml_result: dict = None) -> Optional[int]:
    """
    Log ML Guardian rejection to Supabase.

    Creates a trading_signals entry with status='ml_rejected' for tracking
    and analysis of ML model filtering decisions.

    ML Guardian Rules Enforced:
    - WIN PROBABILITY: Rejects trades with predicted win probability below threshold

    Args:
        data: Original trade payload from TradingView webhook
        rejection_reason: Human-readable reason for rejection
        ml_result: Full ML analysis result dict with win_probability, decision, features

    Returns:
        alert_id if logged successfully, None on error
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    # Build ML-specific filter reasons
    filter_reasons = ["ML_REJECTED"]
    if ml_result:
        win_prob = ml_result.get('win_probability', 0)
        threshold = ml_result.get('threshold', 0.60)
        filter_reasons.append(f"win_prob={win_prob:.1%}")
        filter_reasons.append(f"threshold={threshold:.1%}")
        filter_reasons.append(f"decision={ml_result.get('decision', 'UNKNOWN')}")

    try:
        # Save alert with ml_rejected status
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=filter_reasons)

        # Build notes with full ML analysis
        notes_parts = [f"ML_REJECTION: {rejection_reason}"]
        if ml_result:
            notes_parts.append(f"Win Probability: {ml_result.get('win_probability', 0):.1%}")
            notes_parts.append(f"Threshold: {ml_result.get('threshold', 0.60):.1%}")
            if ml_result.get('feature_names') and ml_result.get('features'):
                feature_str = ", ".join(
                    f"{name}={val}"
                    for name, val in zip(ml_result['feature_names'], ml_result['features'])
                )
                notes_parts.append(f"Features: {feature_str}")

        notes = " | ".join(notes_parts)

        # Update status to ml_rejected
        update_alert_status(alert_id, 'ml_rejected', notes=notes[:1000])  # Truncate if too long

        logger.info(
            f"✅ ML rejection logged: alert_id={alert_id}, "
            f"symbol={data.get('symbol')}, "
            f"win_prob={ml_result.get('win_probability', 0):.1%}"
        )
        return alert_id

    except Exception as e:
        logger.error(f"❌ Failed to log ML rejection to Supabase: {e}")
        return None


def log_pine_rejection(data: dict, rejection_reason: str, pine_result: dict = None) -> Optional[int]:
    """
    Log Pine Guardian rejection to Supabase.

    Creates a trading_signals entry with status='pine_rejected' for tracking
    position sizing mismatches and risk limit violations.

    Pine Guardian Rules Enforced:
    - POSITION SIZE VALIDATION: Recalculates lot size using Pine Script formula
    - DAILY LOSS LIMIT: Blocks if daily loss exceeds max_daily_loss_pct
    - DAILY PROFIT TARGET: Blocks if daily profit reaches max_daily_profit_pct
    - MAX TRADES/DAY: Blocks if trade count exceeds limit

    Args:
        data: Original trade payload from TradingView webhook
        rejection_reason: Human-readable reason for rejection
        pine_result: Pine Guardian validation result dict

    Returns:
        alert_id if logged successfully, None on error
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    # Build Pine-specific filter reasons
    filter_reasons = ["PINE_REJECTED"]
    if pine_result:
        reason_type = pine_result.get('rejection_reason', 'UNKNOWN')
        filter_reasons.append(f"reason={reason_type}")

        if pine_result.get('variance_percent'):
            filter_reasons.append(f"variance={pine_result['variance_percent']:.1f}%")

        if pine_result.get('calculated_lots') and pine_result.get('requested_lots'):
            filter_reasons.append(
                f"calc={pine_result['calculated_lots']:.3f}_vs_req={pine_result['requested_lots']:.3f}"
            )

    try:
        # Save alert with pine_rejected status
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=filter_reasons)

        # Build notes with full Pine validation details
        notes_parts = [f"PINE_REJECTION: {rejection_reason}"]
        if pine_result:
            if pine_result.get('calculated_lots'):
                notes_parts.append(f"Calculated: {pine_result['calculated_lots']:.3f} lots")
            if pine_result.get('requested_lots'):
                notes_parts.append(f"Requested: {pine_result['requested_lots']:.3f} lots")
            if pine_result.get('variance_percent'):
                notes_parts.append(f"Variance: {pine_result['variance_percent']:.1f}%")
            if pine_result.get('details'):
                details = pine_result['details']
                if details.get('risk_pct'):
                    notes_parts.append(f"Risk: {details['risk_pct']}%")
                if details.get('sl_pips'):
                    notes_parts.append(f"SL: {details['sl_pips']:.1f} pips")

        notes = " | ".join(notes_parts)

        # Update status to pine_rejected
        update_alert_status(alert_id, 'pine_rejected', notes=notes[:1000])

        logger.info(
            f"✅ Pine rejection logged: alert_id={alert_id}, "
            f"symbol={data.get('symbol')}, zone_id={data.get('zone_id')}, "
            f"reason={rejection_reason[:100]}"
        )
        return alert_id

    except Exception as e:
        logger.error(f"❌ Failed to log Pine rejection to Supabase: {e}")
        return None


def get_statistics(run_mode: str = None, run_id: str = None) -> Dict[str, Any]:
    """
    Calculate trading statistics

    Args:
        run_mode: Filter by run_mode ('LIVE', 'BACKTEST', 'REPLAY'). None = all modes
        run_id: Filter by specific run_id. None = all run_ids

    Returns:
        Dictionary with trading statistics
    """
    if not supabase:
        init_supabase()

    try:
        # Build query with optional filters
        query = supabase.table('trading_signals').select('*')

        if run_mode:
            query = query.eq('run_mode', run_mode)
        if run_id:
            query = query.eq('run_id', run_id)

        all_trades = query.execute().data

        stats = {}

        # Total alerts
        stats['total_alerts'] = len(all_trades)

        # By status
        stats['by_status'] = {}
        for trade in all_trades:
            status = trade.get('status', 'unknown')
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

        # By outcome (for closed trades)
        stats['by_outcome'] = {}
        for trade in all_trades:
            if trade.get('status') == 'closed' and trade.get('outcome'):
                outcome = trade['outcome']
                stats['by_outcome'][outcome] = stats['by_outcome'].get(outcome, 0) + 1

        # Win rate
        wins = stats['by_outcome'].get('win', 0)
        losses = stats['by_outcome'].get('loss', 0)
        total_closed = wins + losses
        stats['win_rate'] = (wins / total_closed * 100) if total_closed > 0 else 0

        # Total P&L - prefer pnl_usd (actual), fallback to pnl (manual)
        total_pnl = 0.0
        for t in all_trades:
            if t.get('status') == 'closed':
                pnl_usd = t.get('pnl_usd')
                pnl = t.get('pnl')
                if pnl_usd is not None:
                    total_pnl += float(pnl_usd)
                elif pnl is not None:
                    total_pnl += float(pnl)
        stats['total_pnl'] = total_pnl

        # By symbol
        symbol_counts = {}
        for trade in all_trades:
            symbol = trade.get('symbol', 'Unknown')
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        stats['by_symbol'] = dict(sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:10])

        # Average R:R
        rr_ratios = [t['rr_ratio'] for t in all_trades if t.get('rr_ratio') is not None]
        stats['avg_rr'] = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0

        # Today's alerts
        from datetime import date
        today = date.today().isoformat()
        stats['today_alerts'] = sum(1 for t in all_trades if t.get('created_at', '').startswith(today))

        # Additional stats for dashboard
        stats['filtered_count'] = stats['by_status'].get('filtered', 0)
        stats['active_count'] = stats['by_status'].get('active', 0)
        stats['closed_count'] = total_closed

        return stats
    except Exception as e:
        logger.error(f"❌ Failed to get statistics: {e}")
        return {
            'total_alerts': 0,
            'by_status': {},
            'by_outcome': {},
            'win_rate': 0,
            'total_pnl': 0,
            'by_symbol': {},
            'avg_rr': 0,
            'today_alerts': 0,
            'filtered_count': 0,
            'active_count': 0,
            'closed_count': 0
        }


def get_stats(run_mode: str = None, run_id: str = None) -> Dict[str, Any]:
    """Get trading statistics (alias for get_statistics)"""
    return get_statistics(run_mode=run_mode, run_id=run_id)


def get_distinct_run_ids() -> List[Dict[str, str]]:
    """
    Get distinct run_ids grouped by run_mode for dashboard dropdown

    Returns:
        List of dicts with run_mode and run_id
    """
    if not supabase:
        init_supabase()

    try:
        # Get unique run_mode/run_id combinations
        response = supabase.table('trading_signals').select('run_mode, run_id').execute()

        # Deduplicate
        seen = set()
        result = []
        for row in response.data:
            run_mode = row.get('run_mode', 'LIVE')
            run_id = row.get('run_id', 'live-default')
            key = f"{run_mode}|{run_id}"
            if key not in seen:
                seen.add(key)
                result.append({'run_mode': run_mode, 'run_id': run_id})

        # Sort: LIVE first, then BACKTEST, then REPLAY
        mode_order = {'LIVE': 0, 'BACKTEST': 1, 'REPLAY': 2}
        result.sort(key=lambda x: (mode_order.get(x['run_mode'], 99), x['run_id']))

        return result
    except Exception as e:
        logger.error(f"❌ Failed to get distinct run_ids: {e}")
        return []


def check_supabase_health() -> bool:
    """
    Check if Supabase is reachable

    Returns:
        bool: True if healthy
    """
    if not supabase:
        try:
            init_supabase()
        except Exception:
            return False

    try:
        # Simple query to check connectivity
        supabase.table('trading_signals').select('id').limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"❌ Supabase health check failed: {e}")
        return False


# ══════════════════════════════════════════════════════════
# TRINITY ENGINE LOGGING FUNCTIONS
# ══════════════════════════════════════════════════════════


def log_risk_guardian_rejection(data: dict, rejection_reason: str, risk_result: dict = None) -> Optional[int]:
    """
    Log Risk Guardian rejection to Supabase.

    Creates a trading_signals entry with status='risk_rejected' for tracking
    risk management violations (daily loss limit, drawdown, anti-gambling).

    Risk Guardian Rules Enforced:
    - DAILY LOSS LIMIT: Blocks all trades if daily loss > 4%
    - EQUITY PROTECTOR: Kill switch if drawdown > 8%
    - ANTI-GAMBLING: Rejects trades with > 1% equity risk

    Args:
        data: Original trade payload from TradingView webhook
        rejection_reason: Human-readable reason for rejection
        risk_result: RiskCheckResult dict with risk_metrics

    Returns:
        alert_id if logged successfully, None on error
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    # Build Risk Guardian-specific filter reasons
    filter_reasons = ["RISK_REJECTED"]
    if risk_result:
        reason_type = risk_result.get('rejection_reason', 'UNKNOWN')
        filter_reasons.append(f"type={reason_type}")

        metrics = risk_result.get('risk_metrics', {})
        if metrics.get('daily_loss_pct'):
            filter_reasons.append(f"daily_loss={metrics['daily_loss_pct']:.2f}%")
        if metrics.get('total_drawdown_pct'):
            filter_reasons.append(f"drawdown={metrics['total_drawdown_pct']:.2f}%")
        if metrics.get('trade_risk_pct'):
            filter_reasons.append(f"trade_risk={metrics['trade_risk_pct']:.2f}%")
        if metrics.get('kill_switch_active'):
            filter_reasons.append("KILL_SWITCH_ACTIVE")

    try:
        # Save alert with risk_rejected status
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=filter_reasons)

        # Build notes with full risk analysis
        notes_parts = [f"RISK_GUARDIAN: {rejection_reason}"]
        if risk_result and risk_result.get('risk_metrics'):
            metrics = risk_result['risk_metrics']
            notes_parts.append(f"Equity: ${metrics.get('current_equity', 0):,.2f}")
            notes_parts.append(f"Daily P&L: ${metrics.get('daily_pnl', 0):,.2f}")
            if metrics.get('trade_risk_usd'):
                notes_parts.append(f"Trade Risk: ${metrics['trade_risk_usd']:,.2f}")

        notes = " | ".join(notes_parts)

        # Update status to risk_rejected
        update_alert_status(alert_id, 'risk_rejected', notes=notes[:1000])

        logger.info(
            f"✅ Risk Guardian rejection logged: alert_id={alert_id}, "
            f"symbol={data.get('symbol')}, reason={rejection_reason[:100]}"
        )
        return alert_id

    except Exception as e:
        logger.error(f"❌ Failed to log Risk Guardian rejection to Supabase: {e}")
        return None


def log_correlation_rejection(data: dict, rejection_reason: str, correlation_result: dict = None) -> Optional[int]:
    """
    Log Correlation Manager rejection to Supabase.

    Creates a trading_signals entry with status='correlation_rejected' for tracking
    portfolio diversification violations.

    Correlation Manager Rules Enforced:
    - MAX POSITIONS: Max 3 open positions
    - CURRENCY EXPOSURE: No double USD/EUR/etc exposure
    - CORRELATION GROUP: No multiple positions in correlated assets

    Args:
        data: Original trade payload from TradingView webhook
        rejection_reason: Human-readable reason for rejection
        correlation_result: CorrelationCheckResult dict with exposure_details

    Returns:
        alert_id if logged successfully, None on error
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    # Build Correlation-specific filter reasons
    filter_reasons = ["CORRELATION_REJECTED"]
    if correlation_result:
        reason_type = correlation_result.get('rejection_reason', 'UNKNOWN')
        filter_reasons.append(f"type={reason_type}")

        details = correlation_result.get('exposure_details', {})
        if details.get('total_positions'):
            filter_reasons.append(f"positions={details['total_positions']}/{details.get('max_positions', 3)}")
        if details.get('base_currency'):
            filter_reasons.append(f"base={details['base_currency']}")
        if details.get('correlation_groups'):
            groups = list(details['correlation_groups'].keys())[:2]
            filter_reasons.append(f"groups={','.join(groups)}")

    try:
        # Save alert with correlation_rejected status
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=filter_reasons)

        # Build notes with full correlation analysis
        notes_parts = [f"CORRELATION_GUARD: {rejection_reason}"]
        if correlation_result and correlation_result.get('exposure_details'):
            details = correlation_result['exposure_details']
            notes_parts.append(f"Positions: {details.get('total_positions', 0)}/{details.get('max_positions', 3)}")
            if details.get('base_currency'):
                notes_parts.append(f"Base: {details['base_currency']}, Quote: {details.get('quote_currency', 'N/A')}")

        notes = " | ".join(notes_parts)

        # Update status to correlation_rejected
        update_alert_status(alert_id, 'correlation_rejected', notes=notes[:1000])

        logger.info(
            f"✅ Correlation rejection logged: alert_id={alert_id}, "
            f"symbol={data.get('symbol')}, reason={rejection_reason[:100]}"
        )
        return alert_id

    except Exception as e:
        logger.error(f"❌ Failed to log Correlation rejection to Supabase: {e}")
        return None


def log_market_adapter_rejection(data: dict, rejection_reason: str, adapter_result: dict = None) -> Optional[int]:
    """
    Log Market Adapter rejection to Supabase.

    Creates a trading_signals entry with status='adapter_rejected' for tracking
    lot size calculation failures or mismatches.

    Args:
        data: Original trade payload from TradingView webhook
        rejection_reason: Human-readable reason for rejection
        adapter_result: LotSizeResult dict with calculation_details

    Returns:
        alert_id if logged successfully, None on error
    """
    if not supabase:
        init_supabase()

    # Ensure minimal required fields
    entry_data = dict(data)
    defaults = {'symbol': 'unknown', 'side': 'buy', 'entry': 0.0, 'sl': 0.0, 'tp': 0.0, 'size': 0.0}
    for k in ('symbol', 'side', 'entry', 'sl', 'tp', 'size'):
        if k not in entry_data or entry_data[k] is None:
            entry_data[k] = defaults.get(k, 0.0)

    # Build Adapter-specific filter reasons
    filter_reasons = ["ADAPTER_REJECTED"]
    if adapter_result:
        filter_reasons.append(f"asset_class={adapter_result.get('asset_class', 'unknown')}")
        if adapter_result.get('lots_rounded'):
            filter_reasons.append(f"calc_lots={adapter_result['lots_rounded']:.3f}")
        if adapter_result.get('sl_pips'):
            filter_reasons.append(f"sl_pips={adapter_result['sl_pips']:.1f}")

    try:
        # Save alert with adapter_rejected status
        alert_id = save_alert(entry_data, mode='manual', filter_reasons=filter_reasons)

        # Build notes with calculation details
        notes_parts = [f"MARKET_ADAPTER: {rejection_reason}"]
        if adapter_result:
            notes_parts.append(f"Asset: {adapter_result.get('asset_class', 'unknown')}")
            if adapter_result.get('lots_rounded'):
                notes_parts.append(f"Calculated: {adapter_result['lots_rounded']:.3f} lots")
            if adapter_result.get('risk_usd'):
                notes_parts.append(f"Risk: ${adapter_result['risk_usd']:.2f}")

        notes = " | ".join(notes_parts)

        # Update status to adapter_rejected
        update_alert_status(alert_id, 'adapter_rejected', notes=notes[:1000])

        logger.info(
            f"✅ Market Adapter rejection logged: alert_id={alert_id}, "
            f"symbol={data.get('symbol')}, reason={rejection_reason[:100]}"
        )
        return alert_id

    except Exception as e:
        logger.error(f"❌ Failed to log Market Adapter rejection to Supabase: {e}")
        return None


def get_daily_pnl(start_of_day: str = None) -> float:
    """
    Get total P&L for today from closed trades.

    Used by Risk Guardian for daily loss limit enforcement.

    Args:
        start_of_day: ISO format date string (defaults to today)

    Returns:
        Total P&L in USD for today
    """
    if not supabase:
        init_supabase()

    from datetime import date

    if start_of_day is None:
        start_of_day = date.today().isoformat()

    try:
        # Get all closed trades from today
        response = supabase.table('trading_signals').select(
            'pnl_usd, pnl, closed_at'
        ).eq('status', 'closed').gte('closed_at', start_of_day).execute()

        total_pnl = 0.0
        for trade in response.data:
            # Prefer pnl_usd (actual), fallback to pnl (manual)
            pnl_usd = trade.get('pnl_usd')
            pnl = trade.get('pnl')
            if pnl_usd is not None:
                total_pnl += float(pnl_usd)
            elif pnl is not None:
                total_pnl += float(pnl)

        logger.info(f"Daily P&L for {start_of_day}: ${total_pnl:,.2f}")
        return total_pnl

    except Exception as e:
        logger.error(f"❌ Failed to get daily P&L: {e}")
        return 0.0
