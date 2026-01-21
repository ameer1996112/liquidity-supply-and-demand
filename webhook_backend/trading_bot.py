"""
TradingView Alert Server - Full Featured Edition
=================================================
Features:
- Discord & Telegram notifications
- Trade tracking with SQLite database
- Position size calculator
- Alert filtering (sessions, R:R)
- Web dashboard with statistics
- Cloud-ready (Railway/Render)

Author: Trading Bot System
Version: 4.0.0
"""

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import requests
import pytz
import pickle
from news_filter import NewsFilter
from paper_trader import get_paper_trader

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Discord
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

# Telegram (optional)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Server
# Railway assigns PORT env var automatically, fallback to WEBHOOK_PORT for local dev
WEBHOOK_PORT = int(os.getenv('PORT', os.getenv('WEBHOOK_PORT', '3000')))

# Alert Filtering
MIN_RR_RATIO = float(os.getenv('MIN_RR_RATIO', '1.0'))  # Minimum R:R to forward
TRADING_SESSIONS = os.getenv('TRADING_SESSIONS', '')  # e.g., "08:00-17:00" (UTC)

# News Filter
NEWS_FILTER_ENABLED = os.getenv('NEWS_FILTER_ENABLED', 'true').lower() == 'true'
NEWS_PRE_MINUTES = int(os.getenv('NEWS_PRE_MINUTES', '30'))
NEWS_POST_MINUTES = int(os.getenv('NEWS_POST_MINUTES', '30'))
news_filter = NewsFilter(block_minutes_before=NEWS_PRE_MINUTES, block_minutes_after=NEWS_POST_MINUTES)

# AI Model Filter
AI_FILTER_ENABLED = os.getenv('AI_FILTER_ENABLED', 'false').lower() == 'true'
AI_MIN_WIN_PROBABILITY = float(os.getenv('AI_MIN_WIN_PROBABILITY', '0.5'))
UNIVERSAL_MODEL_PATH = Path(__file__).parent / 'model_universal.pkl'
DEFAULT_MODEL_PATH = Path(__file__).parent / 'model.pkl'

# Prioritize Universal Model
MODEL_PATH = UNIVERSAL_MODEL_PATH if UNIVERSAL_MODEL_PATH.exists() else DEFAULT_MODEL_PATH

# Load AI model if enabled and exists
ai_model = None
if AI_FILTER_ENABLED and MODEL_PATH.exists():
    try:
        with open(MODEL_PATH, 'rb') as f:
            ai_model = pickle.load(f)
        logging.info(f"AI Model loaded from {MODEL_PATH}")
    except Exception as e:
        logging.warning(f"Failed to load AI model: {e}")
        ai_model = None

# Swap Hours Filter
SWAP_HOURS_ENABLED = os.getenv('SWAP_HOURS_ENABLED', 'true').lower() == 'true'
SWAP_HOURS_UTC = os.getenv('SWAP_HOURS_UTC', '21:50-22:10')  # Default: 10 min before/after 22:00 UTC

# Paper Trading Mode
PAPER_TRADING_ENABLED = os.getenv('PAPER_TRADING_ENABLED', 'false').lower() == 'true'
PAPER_AUTO_EXECUTE = os.getenv('PAPER_AUTO_EXECUTE', 'true').lower() == 'true'
PAPER_SYMBOLS = [s.strip() for s in os.getenv('PAPER_SYMBOLS', '').split(',') if s.strip()]
PAPER_MAX_POSITIONS = int(os.getenv('PAPER_MAX_POSITIONS', '10'))
PAPER_ACCOUNT_BALANCE = float(os.getenv('PAPER_ACCOUNT_BALANCE', '10000'))

# Initialize paper trader if enabled
paper_trader = get_paper_trader(DB_PATH) if PAPER_TRADING_ENABLED else None

# Position Sizing
DEFAULT_ACCOUNT_BALANCE = float(os.getenv('ACCOUNT_BALANCE', '10000'))
DEFAULT_RISK_PERCENT = float(os.getenv('RISK_PERCENT', '1.0'))

# Database
DB_PATH = Path(__file__).parent / 'trades.db'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE
# =============================================================================

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry REAL NOT NULL,
            sl REAL NOT NULL,
            tp REAL NOT NULL,
            size REAL NOT NULL,
            rr_ratio REAL,
            zone_id TEXT,
            status TEXT DEFAULT 'pending',
            outcome TEXT,
            pnl REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            zone_type TEXT,
            zone_top REAL,
            zone_bottom REAL,
            zone_size_pips REAL,
            entry_model TEXT,
            liq_swept INTEGER DEFAULT 0,
            target_swept INTEGER DEFAULT 0,
            caused_sweep INTEGER DEFAULT 0,
            is_accuracy INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'manual',
            simulated_pnl REAL,
            close_price REAL,
            close_time TIMESTAMP
        )
    ''')

    # Add new columns if they don't exist (for existing databases)
    new_columns = [
        ('zone_type', 'TEXT'),
        ('zone_top', 'REAL'),
        ('zone_bottom', 'REAL'),
        ('zone_size_pips', 'REAL'),
        ('entry_model', 'TEXT'),
        ('liq_swept', 'INTEGER DEFAULT 0'),
        ('target_swept', 'INTEGER DEFAULT 0'),
        ('caused_sweep', 'INTEGER DEFAULT 0'),
        ('is_accuracy', 'INTEGER DEFAULT 0'),
        ('mode', "TEXT DEFAULT 'manual'"),
        ('simulated_pnl', 'REAL'),
        ('close_price', 'REAL'),
        ('close_time', 'TIMESTAMP'),
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f'ALTER TABLE alerts ADD COLUMN {col_name} {col_type}')
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def save_alert(data: dict, mode: str = 'manual') -> int:
    """Save alert to database, return alert ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Calculate R:R
    entry = float(data['entry'])
    sl = float(data['sl'])
    tp = float(data['tp'])
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr_ratio = reward / risk if risk > 0 else 0

    cursor.execute('''
        INSERT INTO alerts (symbol, side, entry, sl, tp, size, rr_ratio, zone_id,
                           zone_type, zone_top, zone_bottom, zone_size_pips, entry_model,
                           liq_swept, target_swept, caused_sweep, is_accuracy, mode, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['symbol'],
        data['side'],
        entry,
        sl,
        tp,
        data['size'],
        rr_ratio,
        data.get('zone_id'),
        data.get('zone_type'),
        data.get('zone_top'),
        data.get('zone_bottom'),
        data.get('zone_size_pips'),
        data.get('entry_model'),
        1 if data.get('liq_swept') else 0,
        1 if data.get('target_swept') else 0,
        1 if data.get('caused_sweep') else 0,
        1 if data.get('is_accuracy') else 0,
        mode,
        'open' if mode == 'paper' else 'pending'
    ))

    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return alert_id


def update_alert_status(alert_id: int, status: str, outcome: str = None, pnl: float = None, notes: str = None):
    """Update alert status."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE alerts
        SET status = ?, outcome = ?, pnl = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, outcome, pnl, notes, alert_id))

    conn.commit()
    conn.close()


def get_alert(alert_id: int) -> Optional[dict]:
    """Get single alert by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_recent_alerts(limit: int = 50) -> List[dict]:
    """Get recent alerts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_statistics() -> dict:
    """Calculate trading statistics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {}

    # Total alerts
    cursor.execute('SELECT COUNT(*) FROM alerts')
    stats['total_alerts'] = cursor.fetchone()[0]

    # By status
    cursor.execute('SELECT status, COUNT(*) FROM alerts GROUP BY status')
    stats['by_status'] = dict(cursor.fetchall())

    # By outcome (for taken trades)
    cursor.execute("SELECT outcome, COUNT(*) FROM alerts WHERE status = 'taken' AND outcome IS NOT NULL GROUP BY outcome")
    stats['by_outcome'] = dict(cursor.fetchall())

    # Win rate
    wins = stats['by_outcome'].get('win', 0)
    losses = stats['by_outcome'].get('loss', 0)
    total_closed = wins + losses
    stats['win_rate'] = (wins / total_closed * 100) if total_closed > 0 else 0

    # Total P&L
    cursor.execute("SELECT SUM(pnl) FROM alerts WHERE pnl IS NOT NULL")
    stats['total_pnl'] = cursor.fetchone()[0] or 0

    # By symbol
    cursor.execute('SELECT symbol, COUNT(*) FROM alerts GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 10')
    stats['by_symbol'] = dict(cursor.fetchall())

    # Average R:R
    cursor.execute('SELECT AVG(rr_ratio) FROM alerts')
    stats['avg_rr'] = cursor.fetchone()[0] or 0

    # Today's alerts
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE DATE(created_at) = DATE('now')")
    stats['today_alerts'] = cursor.fetchone()[0]

    conn.close()
    return stats


# =============================================================================
# NOTIFICATIONS
# =============================================================================

def send_discord(data: dict, alert_id: int, mode: str = 'manual') -> bool:
    """Send alert to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return False

    try:
        side = data['side'].upper()
        emoji = "📈" if side == "BUY" else "📉"
        
        # Color: Blue for paper, Green for buy, Red for sell
        if mode == 'paper':
            color = 0x3498DB  # Blue
            mode_prefix = "🔵 PAPER | "
        else:
            color = 0x00FF00 if side == "BUY" else 0xFF0000
            mode_prefix = ""

        entry = float(data['entry'])
        sl = float(data['sl'])
        tp = float(data['tp'])
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0

        # Calculate pips
        symbol = data['symbol'].upper()
        if 'JPY' in symbol:
            pip_divisor = 0.01
        elif 'XAU' in symbol or 'GOLD' in symbol:
            pip_divisor = 0.1
        else:
            pip_divisor = 0.0001

        sl_pips = abs(entry - sl) / pip_divisor
        tp_pips = abs(tp - entry) / pip_divisor

        # Calculate position size
        position_info = calculate_position_size(sl_pips, symbol)

        embed = {
            "title": f"{mode_prefix}{emoji} New {side} Signal - #{alert_id}",
            "description": f"**{'Auto-executed (paper)' if mode == 'paper' else 'Execute manually'}** | Reply with outcome later",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {"name": "Symbol", "value": f"**{data['symbol']}**", "inline": True},
                {"name": "Type", "value": side, "inline": True},
                {"name": "R:R", "value": f"1:{rr_ratio:.2f}", "inline": True},
                {"name": "Entry", "value": str(data['entry']), "inline": True},
                {"name": "Stop Loss", "value": f"{data['sl']} ({sl_pips:.1f} pips)", "inline": True},
                {"name": "Take Profit", "value": f"{data['tp']} ({tp_pips:.1f} pips)", "inline": True},
                {"name": "Suggested Size", "value": f"{position_info['lots']:.2f} lots", "inline": True},
                {"name": "Risk Amount", "value": f"${position_info['risk_amount']:.2f}", "inline": True},
            ],
            "footer": {"text": f"Alert #{alert_id} | Update: /alert/{alert_id}/taken or /skipped"}
        }

        # === ZONE INSPECTOR DATA ===
        # Zone ID
        if 'zone_id' in data:
            embed["fields"].append({"name": "Zone ID", "value": str(data['zone_id']), "inline": True})
        
        # Zone Type with emoji
        if 'zone_type' in data:
            zone_emoji = "🟢" if data['zone_type'] == 'demand' else "🔴"
            embed["fields"].append({"name": "Zone Type", "value": f"{zone_emoji} {data['zone_type'].upper()}", "inline": True})
        
        # Zone Range
        if 'zone_top' in data and 'zone_bottom' in data:
            zone_range = f"{data['zone_bottom']} → {data['zone_top']}"
            zone_size = data.get('zone_size_pips', '')
            if zone_size:
                zone_range += f" ({zone_size} pips)"
            embed["fields"].append({"name": "Zone Range", "value": zone_range, "inline": True})
        
        # Entry Model
        if 'entry_model' in data:
            model_emojis = {"FLIP": "🔄", "DIR_CLOSE": "📊", "BREAK_CANDLE": "💥"}
            model_emoji = model_emojis.get(data['entry_model'], "")
            embed["fields"].append({"name": "Entry Model", "value": f"{model_emoji} {data['entry_model']}", "inline": True})
        
        # Sweep Status (combined into one field)
        sweep_parts = []
        if data.get('liq_swept'):
            sweep_parts.append("✓ Liq Swept")
        if data.get('target_swept'):
            sweep_parts.append("✓ Target Swept")
        if data.get('caused_sweep'):
            sweep_parts.append("✓ Caused Sweep")
        if sweep_parts:
            embed["fields"].append({"name": "Sweep Status", "value": " | ".join(sweep_parts), "inline": False})
        
        # Accuracy Badge (add to title)
        if data.get('is_accuracy'):
            embed["title"] = f"⭐ ACC | {embed['title']}"

        payload = {
            "content": f"@here **New Trade Signal #{alert_id}!**",
            "embeds": [embed]
        }

        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

        if response.status_code == 204:
            logger.info(f"Discord alert sent: #{alert_id} {data['symbol']} {side}")
            return True
        else:
            logger.error(f"Discord failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Discord error: {e}")
        return False


def send_telegram(data: dict, alert_id: int) -> bool:
    """Send alert to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        side = data['side'].upper()
        emoji = "📈" if side == "BUY" else "📉"

        entry = float(data['entry'])
        sl = float(data['sl'])
        tp = float(data['tp'])
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0

        # Calculate pips
        symbol = data['symbol'].upper()
        if 'JPY' in symbol:
            pip_divisor = 0.01
        elif 'XAU' in symbol or 'GOLD' in symbol:
            pip_divisor = 0.1
        else:
            pip_divisor = 0.0001

        sl_pips = abs(entry - sl) / pip_divisor
        tp_pips = abs(tp - entry) / pip_divisor

        position_info = calculate_position_size(sl_pips, symbol)

        message = f"""
{emoji} <b>NEW {side} SIGNAL #{alert_id}</b>

<b>Symbol:</b> {data['symbol']}
<b>Entry:</b> {data['entry']}
<b>Stop Loss:</b> {data['sl']} ({sl_pips:.1f} pips)
<b>Take Profit:</b> {data['tp']} ({tp_pips:.1f} pips)
<b>R:R:</b> 1:{rr_ratio:.2f}

<b>Suggested Size:</b> {position_info['lots']:.2f} lots
<b>Risk:</b> ${position_info['risk_amount']:.2f}

Execute manually, then update status.
        """.strip()

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info(f"Telegram alert sent: #{alert_id}")
            return True
        else:
            logger.error(f"Telegram failed: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


# =============================================================================
# POSITION SIZING
# =============================================================================

def calculate_position_size(sl_pips: float, symbol: str,
                           account_balance: float = None,
                           risk_percent: float = None) -> dict:
    """Calculate position size based on risk."""
    account_balance = account_balance or DEFAULT_ACCOUNT_BALANCE
    risk_percent = risk_percent or DEFAULT_RISK_PERCENT

    risk_amount = account_balance * (risk_percent / 100)

    # Pip value estimation (simplified)
    symbol = symbol.upper()
    if 'JPY' in symbol:
        pip_value_per_lot = 1000 / 100  # ~$10 per pip per lot for JPY pairs
    elif 'XAU' in symbol or 'GOLD' in symbol:
        pip_value_per_lot = 1  # $1 per 0.1 move per lot
    else:
        pip_value_per_lot = 10  # ~$10 per pip per lot for major pairs

    if sl_pips > 0:
        lots = risk_amount / (sl_pips * pip_value_per_lot)
    else:
        lots = 0.01

    # Round to 2 decimal places, min 0.01
    lots = max(0.01, round(lots, 2))

    return {
        "lots": lots,
        "risk_amount": risk_amount,
        "sl_pips": sl_pips,
        "account_balance": account_balance,
        "risk_percent": risk_percent
    }


# =============================================================================
# ALERT FILTERING
# =============================================================================

def should_forward_alert(data: dict) -> tuple[bool, str]:
    """Check if alert should be forwarded based on filters."""

    # Check if manual test (placeholders detected)
    if data.get('entry') is None or data.get('sl') is None or data.get('tp') is None:
        return True, "TEST MODE (Unresolved Placeholders)"

    # Check R:R ratio
    try:
        entry = float(data['entry'])
        sl = float(data['sl'])
        tp = float(data['tp'])
    except (ValueError, TypeError):
         return True, "TEST MODE (Invalid Data Types)"
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr_ratio = reward / risk if risk > 0 else 0

    if rr_ratio < MIN_RR_RATIO:
        return False, f"R:R {rr_ratio:.2f} below minimum {MIN_RR_RATIO}"

    # Check trading session
    if TRADING_SESSIONS:
        try:
            start_str, end_str = TRADING_SESSIONS.split('-')
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))

            now = datetime.utcnow()
            start_time = now.replace(hour=start_hour, minute=start_min, second=0)
            end_time = now.replace(hour=end_hour, minute=end_min, second=0)

            if not (start_time <= now <= end_time):
                return False, f"Outside trading session {TRADING_SESSIONS} UTC"
        except:
            pass  # Invalid session format, skip filter

    # Check Swap Hours Filter
    if SWAP_HOURS_ENABLED:
        try:
            start_str, end_str = SWAP_HOURS_UTC.split('-')
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))

            now = datetime.utcnow()
            swap_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
            swap_end = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

            if swap_start <= now <= swap_end:
                return False, f"Swap hours ({SWAP_HOURS_UTC} UTC) - spreads widen"
        except:
            pass  # Invalid swap hours format, skip filter

    # Check News Filter
    if NEWS_FILTER_ENABLED:
        if news_filter.is_news_imminent(data.get('symbol', '')):
            return False, "High Impact News Imminent"

    # Check AI Model Filter
    if AI_FILTER_ENABLED and ai_model is not None:
        win_prob = predict_win_probability(data)
        if win_prob is not None and win_prob < AI_MIN_WIN_PROBABILITY:
            return False, f"AI Win Probability {win_prob:.1%} below {AI_MIN_WIN_PROBABILITY:.1%}"

    return True, "OK"


def predict_win_probability(data: dict) -> Optional[float]:
    """
    Predict win probability using the trained AI model.
    Extracts features from webhook data and returns probability.
    """
    if ai_model is None:
        return None
    
    try:
        # Extract features from webhook data
        # The webhook should contain these fields (sent from Pine Script)
        features = []
        
        # Try to get AI features from the data
        # V3 format: Score, Freshness, Session, ZoneType, ATR_Ratio, isAccuracy, Trend, RSI, HTF_Trend, RVOL
        score = float(data.get('score', data.get('zone_score', 50)))
        freshness = int(data.get('freshness', 10))
        session = int(data.get('session', 1))
        zone_type = 0 if data.get('side', '').lower() == 'buy' else 1
        atr_ratio = float(data.get('atr_ratio', 0.5))
        is_accuracy = int(data.get('is_accuracy', 0))
        trend = int(data.get('trend', 1))
        rsi = float(data.get('rsi', 50))
        htf_trend = int(data.get('htf_trend', 1)) # V3
        rvol = float(data.get('rvol', 1.0))       # V3
        adx = float(data.get('adx', 25.0))        # V4
        touch_count = int(data.get('touch_count', 0))  # V5
        base_quality = float(data.get('base_quality', 50.0))  # V6
        departure_strength = float(data.get('departure_strength', 50.0))  # V6
        liquidity_distance = float(data.get('liquidity_distance', 50.0))  # V7.1
        liquidity_spread = float(data.get('liquidity_spread', 50.0))  # V7.1
        return_strength = float(data.get('return_strength', 50.0))  # V7
        
        # Check model feature count to ensure compatibility
        expected_features = ai_model.n_features_in_
        
        if expected_features == 17:
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol, adx, touch_count, base_quality, departure_strength, liquidity_distance, liquidity_spread, return_strength]]
        elif expected_features == 16:
            # Old V7 model with liquidity_quality - use distance as fallback
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol, adx, touch_count, base_quality, departure_strength, liquidity_distance, return_strength]]
        elif expected_features == 14:
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol, adx, touch_count, base_quality, departure_strength]]
        elif expected_features == 12:
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol, adx, touch_count]]
        elif expected_features == 11:
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol, adx]]
        elif expected_features == 10:
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol]]
        elif expected_features == 8:
            features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi]]
        else:
             features = [[score, 3, freshness, 1, trend, rsi]] # V1 fallback (6 features)
        
        # Get probability prediction
        proba = ai_model.predict_proba(features)
        win_prob = proba[0][1]  # Probability of class 1 (win)
        
        logger.info(f"AI Prediction: Win Probability = {win_prob:.2%}")
        return win_prob
        
    except Exception as e:
        logger.warning(f"AI prediction failed: {e}")
        return None


# =============================================================================
# FLASK APP
# =============================================================================

app = Flask(__name__)

@app.template_filter('jerusalem_time')
def format_jerusalem_time(utc_ts_str):
    """Convert UTC timestamp string to Jerusalem time."""
    if not utc_ts_str:
        return "-"
    try:
        # Parse UTC string from SQLite (e.g., '2023-10-27 10:00:00')
        utc_dt = datetime.strptime(str(utc_ts_str).split('.')[0], '%Y-%m-%d %H:%M:%S')
        utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        
        # Convert to Jerusalem time
        jerusalem_tz = pytz.timezone('Asia/Jerusalem')
        local_dt = utc_dt.astimezone(jerusalem_tz)
        local_now = datetime.now(jerusalem_tz)
        
        # If today, show only time
        if local_dt.date() == local_now.date():
            return local_dt.strftime('%H:%M')
        
        # Otherwise show date and time
        return local_dt.strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        return str(utc_ts_str)[:16]


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Receive TradingView alerts."""
    if request.method == 'GET':
        return jsonify({"status": "online", "message": "Webhook endpoint is active. Send POST requests here."}), 200


    try:
        data = None
        try:
            # First try standard parsing
            data = request.get_json(force=True)
        except Exception as e:
            # Fallback: Extract JSON from mixed content (e.g. headers in body)
            logger.warning(f"Standard JSON parse failed, attempting robust parse: {e}")
            raw_data = request.data.decode('utf-8')
            
            # Find all potential start indices for a JSON object
            start_indices = [i for i, char in enumerate(raw_data) if char == '{']
            if not start_indices:
                 logger.error(f"Fatal: No '{{' found in payload: {raw_data}")
                 return jsonify({"status": "error", "message": "No JSON start found"}), 400

            end_index = raw_data.rfind('}') + 1
            
            parse_success = False
            for start in start_indices:
                if start >= end_index:
                    break
                
                try:
                    candidate = raw_data[start:end_index]
                    
                    # 1. Sanitize Smart Quotes (common copy-paste issue)
                    candidate_sanitized = candidate.replace('“', '"').replace('”', '"')
                    
                    # 2. Sanitize TradingView placeholders {{...}} -> null
                    # Use DOTALL to match placeholders even if they span lines
                    candidate_sanitized = re.sub(r'\{\{.*?\}\}', 'null', candidate_sanitized, flags=re.DOTALL)
                    
                    # 3. Sanitize trailing commas (common JSON error)
                    # matches ,} or ,] and removes the comma
                    candidate_sanitized = re.sub(r',\s*([}\]])', r'\1', candidate_sanitized)

                    data = json.loads(candidate_sanitized, strict=False)
                    logger.info(f"Robust JSON parse successful at index {start}")
                    parse_success = True
                    break
                except Exception as loop_e:
                    # Log failure for first few attempts to help debug
                    if start == start_indices[0] or start == 17: # Debug index 17 specifically based on logs
                         logger.warning(f"Parse failed at idx {start}: {loop_e}")
                         logger.warning(f"Sanitized substring (first 100): {candidate_sanitized[:100]}...")
                    continue
            
            if not parse_success:
                logger.error(f"Fatal: No valid JSON found after scanning. Raw start: {raw_data[:100]}...")
                return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        logger.info(f"Webhook received: {data}")

        # Validate
        required = ['symbol', 'side', 'entry', 'sl', 'tp', 'size']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"status": "error", "message": f"Missing: {missing}"}), 400

        if data['side'].lower() not in ['buy', 'sell']:
            return jsonify({"status": "error", "message": "Invalid side"}), 400

        # Check filters
        should_forward, reason = should_forward_alert(data)

        # Determine mode (paper or manual)
        mode = 'manual'
        symbol = data['symbol'].upper()
        
        if PAPER_TRADING_ENABLED and PAPER_AUTO_EXECUTE:
            # Check if symbol should be paper traded
            if not PAPER_SYMBOLS or symbol in PAPER_SYMBOLS:
                # Check max positions limit
                if paper_trader and len(paper_trader.get_open_positions()) < PAPER_MAX_POSITIONS:
                    mode = 'paper'
        
        # Save to database
        alert_id = save_alert(data, mode=mode)

        if not should_forward:
            logger.info(f"Alert #{alert_id} filtered: {reason}")
            update_alert_status(alert_id, 'filtered', notes=reason)
            return jsonify({
                "status": "filtered",
                "alert_id": alert_id,
                "reason": reason,
                "mode": mode
            }), 200

        # If paper trading mode, open virtual position
        if mode == 'paper' and paper_trader:
            entry = float(data['entry'])
            sl = float(data['sl'])
            tp = float(data['tp'])
            size = float(data['size'])
            
            # Calculate R:R
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            paper_trader.open_position(
                alert_id,
                symbol,
                data['side'].lower(),
                entry,
                sl,
                tp,
                size,
                rr_ratio
            )
            logger.info(f"🔵 Paper position #{alert_id} opened automatically")

        # Send notifications (always send, even for paper trades)
        discord_sent = send_discord(data, alert_id, mode=mode)
        telegram_sent = send_telegram(data, alert_id)

        return jsonify({
            "status": "success",
            "alert_id": alert_id,
            "mode": mode,
            "discord": discord_sent,
            "telegram": telegram_sent
        }), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/alert/<int:alert_id>/taken', methods=['POST', 'GET'])
def mark_taken(alert_id: int):
    """Mark alert as taken."""
    update_alert_status(alert_id, 'taken')
    return jsonify({"status": "success", "alert_id": alert_id, "marked": "taken"})


@app.route('/alert/<int:alert_id>/skipped', methods=['POST', 'GET'])
def mark_skipped(alert_id: int):
    """Mark alert as skipped."""
    update_alert_status(alert_id, 'skipped')
    return jsonify({"status": "success", "alert_id": alert_id, "marked": "skipped"})


@app.route('/alert/<int:alert_id>/missed', methods=['POST', 'GET'])
def mark_missed(alert_id: int):
    """Mark alert as missed."""
    update_alert_status(alert_id, 'missed')
    return jsonify({"status": "success", "alert_id": alert_id, "marked": "missed"})


@app.route('/alert/<int:alert_id>/outcome', methods=['POST'])
def record_outcome(alert_id: int):
    """Record trade outcome."""
    data = request.get_json(force=True)
    outcome = data.get('outcome')  # win, loss, breakeven
    pnl = data.get('pnl', 0)
    notes = data.get('notes', '')

    if outcome not in ['win', 'loss', 'breakeven']:
        return jsonify({"status": "error", "message": "Invalid outcome"}), 400

    update_alert_status(alert_id, 'taken', outcome=outcome, pnl=pnl, notes=notes)
    return jsonify({"status": "success", "alert_id": alert_id, "outcome": outcome, "pnl": pnl})


@app.route('/alert/<int:alert_id>', methods=['GET'])
def get_alert_details(alert_id: int):
    """Get alert details."""
    alert = get_alert(alert_id)
    if not alert:
        return jsonify({"status": "error", "message": "Alert not found"}), 404
    return jsonify(alert)


@app.route('/alerts', methods=['GET'])
def list_alerts():
    """List recent alerts."""
    limit = request.args.get('limit', 50, type=int)
    alerts = get_recent_alerts(limit)
    return jsonify(alerts)


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get trading statistics."""
    return jsonify(get_statistics())


@app.route('/position-size', methods=['GET', 'POST'])
def position_size():
    """Calculate position size."""
    if request.method == 'POST':
        data = request.get_json(force=True)
    else:
        data = request.args

    sl_pips = float(data.get('sl_pips', 20))
    symbol = data.get('symbol', 'EURUSD')
    balance = float(data.get('balance', DEFAULT_ACCOUNT_BALANCE))
    risk = float(data.get('risk', DEFAULT_RISK_PERCENT))

    result = calculate_position_size(sl_pips, symbol, balance, risk)
    return jsonify(result)


@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({
        "status": "healthy",
        "discord": bool(DISCORD_WEBHOOK_URL),
        "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "database": DB_PATH.exists(),
        "ai_model_loaded": ai_model is not None,
        "ai_model_type": "universal" if 'universal' in str(MODEL_PATH) else "standard",
        "timestamp": datetime.utcnow().isoformat()
    })


# =============================================================================
# WEB DASHBOARD
# =============================================================================

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Trading Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #00d4ff; margin-bottom: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #16213e; padding: 20px; border-radius: 10px; text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #888; margin-top: 5px; }
        .win { color: #00ff88; }
        .loss { color: #ff4444; }
        table { width: 100%; border-collapse: collapse; background: #16213e; border-radius: 10px; overflow: hidden; font-size: 0.95em; }
        th, td { padding: 12px 15px; text-align: center; border-bottom: 1px solid #2a2a4a; white-space: nowrap; }
        th { background: #0f3460; color: #00d4ff; font-weight: 600; text-transform: uppercase; font-size: 0.85em; letter-spacing: 0.5px; }
        td { color: #ddd; }
        tr:hover { background: #1f3a5f; }
        td:nth-child(3), th:nth-child(3) { text-align: left; font-weight: bold; } /* Symbol left align */
        .status-taken { color: #00ff88; background: rgba(0, 255, 136, 0.1); padding: 4px 8px; border-radius: 4px; }
        .status-skipped { color: #888; background: rgba(136, 136, 136, 0.1); padding: 4px 8px; border-radius: 4px; }
        .status-missed { color: #ff4444; background: rgba(255, 68, 68, 0.1); padding: 4px 8px; border-radius: 4px; }
        .status-pending { color: #ffaa00; background: rgba(255, 170, 0, 0.1); padding: 4px 8px; border-radius: 4px; }
        .status-filtered { color: #666; }
        .buy { color: #00ff88; font-weight: bold; }
        .sell { color: #ff4444; font-weight: bold; }
        .refresh-btn { background: #00d4ff; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; font-weight: bold; }
        .refresh-btn:hover { background: #00b4df; }
        .actions a { color: #00d4ff; text-decoration: none; margin: 0 5px; font-size: 0.9em; }
        .actions a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Trading Dashboard</h1>
        <button class="refresh-btn" onclick="location.reload()">Refresh</button>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ stats.total_alerts }}</div>
                <div class="stat-label">Total Alerts</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.today_alerts }}</div>
                <div class="stat-label">Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {% if stats.win_rate >= 50 %}win{% else %}loss{% endif %}">{{ "%.1f"|format(stats.win_rate) }}%</div>
                <div class="stat-label">Win Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {% if stats.total_pnl >= 0 %}win{% else %}loss{% endif %}">${{ "%.2f"|format(stats.total_pnl) }}</div>
                <div class="stat-label">Total P&L</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ "%.2f"|format(stats.avg_rr) }}</div>
                <div class="stat-label">Avg R:R</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.by_status.get('taken', 0) }}</div>
                <div class="stat-label">Trades Taken</div>
            </div>
        </div>

        <h2 style="margin-bottom: 15px;">Recent Alerts</h2>
        <div style="overflow-x: auto;">
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Zone</th>
                    <th>Type</th>
                    <th>Entry</th>
                    <th>SL</th>
                    <th>TP</th>
                    <th>R:R</th>
                    <th>Model</th>
                    <th>Liq</th>
                    <th>Target</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for alert in alerts %}
                <tr>
                    <td>#{{ alert.id }}</td>
                    <td>{{ alert.created_at | jerusalem_time }}</td>
                    <td><strong>{{ alert.symbol }}</strong></td>
                    <td class="{{ alert.side }}">{{ alert.side|upper }}</td>
                    <td>{% if alert.zone_type == 'demand' %}<span style="color:#00ff88">▲ DEM</span>{% elif alert.zone_type == 'supply' %}<span style="color:#ff4444">▼ SUP</span>{% else %}-{% endif %}</td>
                    <td>{% if alert.is_accuracy %}<span style="color:#ffd700">⭐ ACC</span>{% else %}<span style="color:#888">Normal</span>{% endif %}</td>
                    <td style="color:#00d4ff">{{ alert.entry }}</td>
                    <td style="color:#ff4444">{{ alert.sl }}</td>
                    <td style="color:#00ff88">{{ alert.tp }}</td>
                    <td>1:{{ "%.2f"|format(alert.rr_ratio or 0) }}</td>
                    <td>{{ alert.entry_model or '-' }}</td>
                    <td>{% if alert.liq_swept %}<span style="color:#00ff88">✓</span>{% else %}<span style="color:#666">✗</span>{% endif %}</td>
                    <td>{% if alert.target_swept %}<span style="color:#00ff88">✓</span>{% else %}<span style="color:#666">✗</span>{% endif %}</td>
                    <td class="status-{{ alert.status }}">{{ alert.status }}</td>
                    <td class="actions">
                        {% if alert.status == 'pending' %}
                        <a href="/alert/{{ alert.id }}/taken">Taken</a>
                        <a href="/alert/{{ alert.id }}/skipped">Skip</a>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        </div>
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET'])
def dashboard():
    """Web dashboard."""
    stats = get_statistics()
    alerts = get_recent_alerts(50)
    return render_template_string(DASHBOARD_HTML, stats=stats, alerts=alerts)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Trading Alert Server v4.0 - Full Featured")
    logger.info("=" * 60)

    # Initialize database
    init_db()

    # Check configuration
    if not DISCORD_WEBHOOK_URL and not TELEGRAM_BOT_TOKEN:
        logger.warning("No notification channels configured!")
        logger.warning("Add DISCORD_WEBHOOK_URL or TELEGRAM_BOT_TOKEN to .env")

    if DISCORD_WEBHOOK_URL:
        logger.info(f"Discord: Configured")
    if TELEGRAM_BOT_TOKEN:
        logger.info(f"Telegram: Configured")

    logger.info(f"Min R:R Filter: {MIN_RR_RATIO}")
    if TRADING_SESSIONS:
        logger.info(f"Trading Sessions: {TRADING_SESSIONS} UTC")

    logger.info("")
    logger.info(f"Dashboard: http://localhost:{WEBHOOK_PORT}/")
    logger.info(f"Webhook: http://localhost:{WEBHOOK_PORT}/webhook")
    logger.info(f"Stats API: http://localhost:{WEBHOOK_PORT}/stats")
    
    if ai_model:
        logger.info(f"🧠 AI Model: LOADED ({'Universal' if 'universal' in str(MODEL_PATH) else 'Standard'})")
    else:
        logger.warning("⚠️ AI Model: NOT LOADED (Check MODEL_PATH)")

    logger.info("")
    logger.info("Press Ctrl+C to stop.")

    app.run(host='0.0.0.0', port=WEBHOOK_PORT, debug=False)


if __name__ == "__main__":
    main()
