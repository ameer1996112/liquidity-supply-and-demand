"""
Supabase Database Helper
Replaces SQLite with Supabase for persistent cloud storage
"""

import os
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


def save_alert(data: dict, mode: str = 'manual') -> int:
    """
    Save alert to Supabase trading_signals table

    Args:
        data: Alert data dictionary
        mode: Trading mode ('manual', 'paper', 'live')

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
    }

    try:
        response = supabase.table('trading_signals').insert(insert_data).execute()
        alert_id = response.data[0]['id']
        logger.info(f"✅ Alert saved to Supabase: ID={alert_id}, zone_id={data.get('zone_id')}")
        return alert_id
    except Exception as e:
        logger.error(f"❌ Failed to save alert to Supabase: {e}")
        raise


def update_alert_exit(zone_id: int, exit_data: dict) -> bool:
    """
    Update alert with exit telemetry data

    Args:
        zone_id: The zone_id to update
        exit_data: Dictionary with exit telemetry (outcome, bars_held, pnl_r, etc.)

    Returns:
        bool: True if update successful
    """
    if not supabase:
        init_supabase()

    update_data = {
        'status': 'closed',
        'outcome': exit_data.get('outcome'),
        'bars_held': exit_data.get('bars_held'),
        'pnl_r': exit_data.get('pnl_r'),
        'exit_type': exit_data.get('exit_type'),
        'mae_pips': exit_data.get('mae_pips'),
        'close_price': exit_data.get('close_price'),
        'close_time': exit_data.get('close_time', datetime.utcnow().isoformat()),
    }

    try:
        response = supabase.table('trading_signals').update(update_data).eq('zone_id', zone_id).execute()

        if response.data:
            logger.info(f"✅ Alert exit updated: zone_id={zone_id}, outcome={exit_data.get('outcome')}")
            return True
        else:
            logger.warning(f"⚠️  No alert found with zone_id={zone_id}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to update alert exit: {e}")
        raise


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


def get_recent_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent alerts ordered by created_at"""
    if not supabase:
        init_supabase()

    try:
        response = supabase.table('trading_signals').select('*').order('created_at', desc=True).limit(limit).execute()
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


def get_statistics() -> Dict[str, Any]:
    """Calculate trading statistics"""
    if not supabase:
        init_supabase()

    try:
        # Get all trades
        all_trades = supabase.table('trading_signals').select('*').execute().data

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

        # Total P&L
        stats['total_pnl'] = sum(t.get('pnl', 0) or 0 for t in all_trades if t.get('pnl') is not None)

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
            'today_alerts': 0
        }


def get_stats() -> Dict[str, Any]:
    """Get trading statistics (alias for get_statistics)"""
    return get_statistics()
