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

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

# Initialize Supabase client
supabase: Optional[Client] = None

def init_supabase() -> Client:
    """Initialize Supabase client"""
    global supabase

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase client initialized successfully")
        return supabase
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        raise


def save_alert(data: dict, mode: str = 'manual', filter_reasons: List[str] = None) -> int:
    """
    Save alert to Supabase trading_signals table

    Args:
        data: Alert data dictionary
        mode: Trading mode ('manual', 'paper', 'live')
        filter_reasons: List of filter reason codes (if filtered)

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
        'status': 'active',
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
        # V2.0 Telemetry Fields
        'run_mode': run_mode,
        'run_id': run_id,
        'trade_key': trade_key,
        'entry_time': entry_time,
    }

    # Add filter reasons if provided
    if filter_reasons:
        insert_data['filter_reason_json'] = json.dumps(filter_reasons)

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
        'status': 'closed',
        'outcome': exit_data.get('outcome'),
        'bars_held': exit_data.get('bars_held'),
        'pnl_r': exit_data.get('pnl_r'),
        'pnl_usd': exit_data.get('pnl_usd'),  # Actual USD P&L from strategy engine
        'exit_type': exit_data.get('exit_type'),
        'mae_pips': exit_data.get('mae_pips'),
        'close_price': exit_data.get('close_price'),
        'close_time': exit_data.get('close_time', datetime.utcnow().isoformat()),
        'exit_time': exit_time,
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
