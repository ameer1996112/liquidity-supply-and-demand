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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import requests
import pytz
import pickle
from backend.news_filter import NewsFilter
from backend.paper_trader import get_paper_trader
from backend import supabase_db

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
DEFAULT_MODEL_PATH = Path(__file__).parent / 'models' / 'model_ultimate.pkl'

# AI Filter Exclusions (symbols that skip AI filter)
AI_FILTER_EXCLUDE_SYMBOLS = [s.strip().upper() for s in os.getenv('AI_FILTER_EXCLUDE_SYMBOLS', 'NAS100,US100,NDX,SPX,US500,DJI,US30').split(',') if s.strip()]

# Gold pip divisor (configurable)
GOLD_PIP_DIVISOR = float(os.getenv('GOLD_PIP_DIVISOR', '0.1'))

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
paper_trader = get_paper_trader('trades.db') if PAPER_TRADING_ENABLED else None

# Position Sizing
DEFAULT_ACCOUNT_BALANCE = float(os.getenv('ACCOUNT_BALANCE', '10000'))
DEFAULT_RISK_PERCENT = float(os.getenv('RISK_PERCENT', '1.0'))

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
    """Initialize Supabase database."""
    try:
        supabase_db.init_supabase()
        logger.info("✅ Supabase database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        raise


def save_alert(data: dict, mode: str = 'manual', filter_reasons: List[str] = None) -> int:
    """Save alert to Supabase with AI features, return alert ID."""
    return supabase_db.save_alert(data, mode, filter_reasons)


def update_alert_status(alert_id: int, status: str, outcome: str = None, pnl: float = None, notes: str = None):
    """Update alert status."""
    supabase_db.update_alert_status(alert_id, status, outcome, pnl, notes)


def get_alert(alert_id: int) -> Optional[dict]:
    """Get single alert by ID."""
    return supabase_db.get_alert(alert_id)


def get_recent_alerts(limit: int = 50, run_mode: str = None, run_id: str = None) -> List[dict]:
    """Get recent alerts with optional run_mode/run_id filtering."""
    return supabase_db.get_recent_alerts(limit, run_mode=run_mode, run_id=run_id)


def get_statistics(run_mode: str = None, run_id: str = None) -> dict:
    """Calculate trading statistics with optional filtering."""
    return supabase_db.get_statistics(run_mode=run_mode, run_id=run_id)


# =============================================================================
# NOTIFICATIONS
# =============================================================================

def get_pip_divisor(symbol: str) -> float:
    """
    Get the pip/point divisor for a symbol.

    For forex pairs: pip = 0.0001 (or 0.01 for JPY)
    For gold: configurable via GOLD_PIP_DIVISOR (default 0.1)
    For indices (NAS100, SPX, etc.): 1.0 (points, not pips)
    """
    symbol = symbol.upper()

    # Check for indices first (points, not pips)
    index_patterns = ['NAS', 'US100', 'NDX', 'SPX', 'US500', 'DJI', 'US30', 'DAX', 'FTSE', 'NIK']
    if any(pattern in symbol for pattern in index_patterns):
        return 1.0  # Points for indices

    # JPY pairs
    if 'JPY' in symbol:
        return 0.01

    # Gold
    if 'XAU' in symbol or 'GOLD' in symbol:
        return GOLD_PIP_DIVISOR

    # Default forex
    return 0.0001


def send_discord(data: dict, alert_id: int, mode: str = 'manual') -> tuple[bool, str]:
    """
    Send alert to Discord.

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured")
        return False, "DISCORD_WEBHOOK_URL not configured"

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

        # Calculate pips/points using unified function
        symbol = data['symbol'].upper()
        pip_divisor = get_pip_divisor(symbol)

        # Determine unit label (pips for forex, points for indices)
        is_index = pip_divisor == 1.0
        unit_label = "pts" if is_index else "pips"

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
                {"name": "Stop Loss", "value": f"{data['sl']} ({sl_pips:.1f} {unit_label})", "inline": True},
                {"name": "Take Profit", "value": f"{data['tp']} ({tp_pips:.1f} {unit_label})", "inline": True},
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
            return True, None
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200] if response.text else 'No response body'}"
            logger.error(f"Discord failed: {error_msg}")
            return False, error_msg

    except requests.exceptions.Timeout:
        error_msg = "Request timed out after 10 seconds"
        logger.error(f"Discord error: {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Discord error: {error_msg}")
        return False, error_msg


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

def should_forward_alert(data: dict) -> tuple[bool, List[str], dict]:
    """
    Check if alert should be forwarded based on filters.

    Returns:
        tuple: (should_forward: bool, reasons: list[str], debug_meta: dict)
        - If should_forward is True, reasons = ["OK"]
        - If should_forward is False, reasons contains ALL failing filter codes
        - debug_meta contains additional diagnostic info
    """
    reasons = []
    debug_meta = {}

    # Check if manual test (placeholders detected)
    if data.get('entry') is None or data.get('sl') is None or data.get('tp') is None:
        return True, ["Test: Unresolved placeholders"], {'test_mode': True}

    # Check R:R ratio
    try:
        entry = float(data['entry'])
        sl = float(data['sl'])
        tp = float(data['tp'])
    except (ValueError, TypeError):
        return True, ["Test: Invalid entry/SL/TP data types"], {'test_mode': True}

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr_ratio = reward / risk if risk > 0 else 0
    debug_meta['rr_ratio'] = rr_ratio

    if rr_ratio < MIN_RR_RATIO:
        reasons.append(f"R:R {rr_ratio:.2f} below minimum required ({MIN_RR_RATIO})")

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
                reasons.append(f"Outside trading session (allowed: {TRADING_SESSIONS} UTC)")
        except Exception:
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
                reasons.append(f"Within swap hours (avoid {SWAP_HOURS_UTC} UTC)")
        except Exception:
            pass  # Invalid swap hours format, skip filter

    # Check News Filter
    if NEWS_FILTER_ENABLED:
        if news_filter.is_news_imminent(data.get('symbol', '')):
            reasons.append("News event imminent")

    # Check AI Model Filter
    symbol = data.get('symbol', '').upper()
    is_excluded_symbol = any(excl in symbol for excl in AI_FILTER_EXCLUDE_SYMBOLS)

    if AI_FILTER_ENABLED and ai_model is not None:
        if is_excluded_symbol:
            debug_meta['ai_filter_skipped'] = f"Symbol {symbol} in AI_FILTER_EXCLUDE_SYMBOLS"
            logger.info(f"AI filter skipped for {symbol} (in exclusion list)")
        else:
            win_prob = predict_win_probability(data)
            debug_meta['ai_win_prob'] = win_prob
            if win_prob is not None and win_prob < AI_MIN_WIN_PROBABILITY:
                reasons.append(f"AI win probability {win_prob:.0%} below minimum ({AI_MIN_WIN_PROBABILITY:.0%})")

    # Determine final result
    if reasons:
        return False, reasons, debug_meta
    else:
        return True, ["OK"], debug_meta


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
        
        if expected_features == 22:
             # V8/Ultimate Model (17 features + 5 placeholders)
             features = [[score, freshness, session, zone_type, atr_ratio, is_accuracy, trend, rsi, htf_trend, rvol, adx, touch_count, base_quality, departure_strength, liquidity_distance, liquidity_spread, return_strength, 0, 0, 0, 0, 0]]
        elif expected_features == 17:
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

def _format_filter_reason(notes: str) -> str:
    """Convert stored filter codes (e.g. RR_BELOW_MIN:2.00<2.0) to readable text."""
    if not notes or not isinstance(notes, str):
        return "-"
    s = notes.strip()
    if not s:
        return "-"
    s = re.sub(r"RR_BELOW_MIN:([\d.]+)<([\d.]+)", r"R:R \1 below minimum required (\2)", s)
    s = re.sub(r"AI_WINPROB:([^;<]+)<([^;<]+)", r"AI win probability \1 below minimum (\2)", s)
    s = re.sub(r"OUTSIDE_SESSION:([^;]+)", r"Outside trading session (allowed: \1)", s)
    s = re.sub(r"SWAP_HOURS:([^;]+)", r"Within swap hours (avoid \1)", s)
    s = re.sub(r"\bNEWS_IMMINENT\b", "News event imminent", s)
    s = re.sub(r"TEST_MODE:Unresolved_Placeholders", "Test: Unresolved placeholders", s)
    s = re.sub(r"TEST_MODE:Invalid_Data_Types", "Test: Invalid entry/SL/TP data types", s)
    s = re.sub(r";\s*", " · ", s)
    return s.strip()


@app.template_filter("format_filter_reason")
def format_filter_reason(notes):
    return _format_filter_reason(notes)


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

    # === ENHANCED DEBUG LOGGING ===
    logger.info("=" * 60)
    logger.info("📥 WEBHOOK REQUEST RECEIVED")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"Content-Length: {request.content_length}")
    logger.info(f"Method: {request.method}")
    
    # Log raw data
    raw_data = request.data.decode('utf-8', errors='replace')
    logger.info(f"Raw Body Length: {len(raw_data)} bytes")
    logger.info(f"Raw Body (first 500 chars): {raw_data[:500]}")
    
    # Log headers (sanitize sensitive info)
    logger.info("Headers:")
    for key, value in request.headers:
        if key.lower() not in ['authorization', 'cookie']:
            logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    try:
        data = None
        try:
            # First try standard parsing
            data = request.get_json(force=True)
            logger.info("✅ Standard JSON parsing succeeded")
        except Exception as e:
            # Fallback: Extract JSON from mixed content (e.g. headers in body)
            logger.warning(f"⚠️ Standard JSON parse failed, attempting robust parse: {e}")
            
            # Find all potential start indices for a JSON object
            start_indices = [i for i, char in enumerate(raw_data) if char == '{']
            if not start_indices:
                 logger.error(f"❌ Fatal: No '{{' found in payload: {raw_data}")
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

        # Check if data is None (happens when get_json returns None without exception)
        if data is None:
            logger.error("Fatal: JSON parsing returned None. Check content-type and payload.")
            return jsonify({"status": "error", "message": "Invalid or empty JSON payload"}), 400

        logger.info(f"Webhook received: {data}")

        if data.get('event_type') == 'exit':
            logger.info(f"Routing to exit logic: {data}")
            # Validate required fields for exit
            required_exit = ['zone_id', 'outcome', 'bars_held', 'close_price', 'exit_type', 'mae_pips']
            missing_exit = [f for f in required_exit if f not in data]
            if missing_exit:
                return jsonify({"status": "error", "message": f"Missing exit fields: {missing_exit}"}), 400
            
            # Update trade exit data in Supabase
            exit_data = {
                'outcome': data['outcome'],
                'close_price': data['close_price'],
                'close_time': data.get('close_time'),
                'exit_time': data.get('exit_time'),  # New: explicit exit time
                'entry_time': data.get('entry_time'),  # New: from Pine
                'pnl_r': data.get('pnl_r', 0),
                'pnl_usd': data.get('pnl_usd'),  # New: actual USD P&L from strategy
                'exit_type': data['exit_type'],
                'mae_pips': data['mae_pips'],
                'bars_held': data['bars_held']
            }

            # Use trade_key for correlation if available (preferred), fallback to zone_id
            trade_key = data.get('trade_key', '').strip()
            success = supabase_db.update_alert_exit(data['zone_id'], exit_data, trade_key=trade_key)

            if not success:
                match_method = f"trade_key={trade_key}" if trade_key else f"zone_id={data['zone_id']}"
                logger.warning(f"No open trade found for {match_method}")
                return jsonify({"status": "warning", "message": "No matching open trade found", "match_method": match_method}), 200

            pnl_display = f"${data.get('pnl_usd', 0):.2f}" if data.get('pnl_usd') else f"{data.get('pnl_r', 0):.2f}R"
            logger.info(f"✅ Exit recorded for zone #{data['zone_id']}: {data['outcome']} | P&L: {pnl_display} | MAE: {data['mae_pips']:.1f} pips")
            return jsonify({"status": "success", "zone_id": data['zone_id'], "outcome": data['outcome'], "pnl_usd": data.get('pnl_usd')}), 200

        # Validate Entry Fields
        required = ['symbol', 'side', 'entry', 'sl', 'tp', 'size']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"status": "error", "message": f"Missing fields: {missing}"}), 400

        # DETECT TEST MODE (Unresolved Placeholders)
        # If side is "null" (string) or entry is None (null in JSON), it's a test.
        is_test_mode = data.get('side') == 'null' or data.get('entry') is None
        
        if is_test_mode:
            logger.info("🧪 TEST MODE: Sanitizing placeholder values for dashboard storage")
            # Set safe defaults so test alerts can be saved to DB
            data['side'] = data.get('side') if data.get('side') not in ['null', None] else 'buy'
            data['entry'] = data.get('entry') if data.get('entry') is not None else 0.0
            data['sl'] = data.get('sl') if data.get('sl') is not None else 0.0
            data['tp'] = data.get('tp') if data.get('tp') is not None else 0.0
            data['size'] = data.get('size') if data.get('size') is not None else 0.0
            data['symbol'] = data.get('symbol', 'TEST')
            data['_test_mode'] = True  # Flag for later use

        if data['side'].lower() not in ['buy', 'sell']:
            return jsonify({"status": "error", "message": "Invalid side"}), 400

        # Check filters (returns all failing reasons, not just first)
        should_forward, filter_reasons, debug_meta = should_forward_alert(data)

        # Determine mode (paper or manual)
        mode = 'manual'
        symbol = data['symbol'].upper()

        if PAPER_TRADING_ENABLED and PAPER_AUTO_EXECUTE:
            # Check if symbol should be paper traded
            if not PAPER_SYMBOLS or symbol in PAPER_SYMBOLS:
                # Check max positions limit
                if paper_trader and len(paper_trader.get_open_positions()) < PAPER_MAX_POSITIONS:
                    mode = 'paper'

        # Save to database (include filter_reasons for filtered alerts)
        alert_id = save_alert(data, mode=mode, filter_reasons=filter_reasons if not should_forward else None)

        if not should_forward:
            # Join all reasons with separator for notes field
            reason_str = "; ".join(filter_reasons)
            logger.info(f"Alert #{alert_id} filtered: {reason_str}")
            update_alert_status(alert_id, 'filtered', notes=reason_str)
            return jsonify({
                "status": "filtered",
                "alert_id": alert_id,
                "reasons": filter_reasons,
                "reason": reason_str,  # Backward compatible single string
                "mode": mode,
                "debug": debug_meta
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
        discord_sent, discord_error = send_discord(data, alert_id, mode=mode)
        telegram_sent = send_telegram(data, alert_id)

        response_data = {
            "status": "success",
            "alert_id": alert_id,
            "mode": mode,
            "run_mode": data.get('run_mode', 'LIVE'),
            "run_id": data.get('run_id', 'live-default'),
            "discord_sent": discord_sent,
            "telegram_sent": telegram_sent
        }

        # Include discord error if present
        if discord_error:
            response_data["discord_error"] = discord_error

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/webhook/exit', methods=['POST'])
def webhook_exit():
    """Receive trade exit events from TradingView."""
    try:
        data = request.get_json(force=True)
        logger.info(f"Exit webhook received: {data}")

        # Validate event type
        if data.get('event_type') != 'exit':
            return jsonify({"status": "error", "message": "Invalid event type"}), 400

        # Required fields
        required = ['zone_id', 'outcome', 'bars_held', 'close_price', 'exit_type', 'mae_pips']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"status": "error", "message": f"Missing fields: {missing}"}), 400

        # Update trade exit data in Supabase
        exit_data = {
            'outcome': data['outcome'],
            'close_price': data['close_price'],
            'close_time': data.get('close_time'),
            'exit_time': data.get('exit_time'),  # New: explicit exit time from Pine
            'entry_time': data.get('entry_time'),  # New: from Pine
            'pnl_r': data.get('pnl_r', 0),  # P&L in R units
            'pnl_usd': data.get('pnl_usd'),  # New: actual USD P&L from strategy
            'exit_type': data['exit_type'],
            'mae_pips': data['mae_pips'],
            'bars_held': data['bars_held']
        }

        # Use trade_key for correlation if available (preferred), fallback to zone_id
        trade_key = data.get('trade_key', '').strip()
        success = supabase_db.update_alert_exit(data['zone_id'], exit_data, trade_key=trade_key)

        if not success:
            match_method = f"trade_key={trade_key}" if trade_key else f"zone_id={data['zone_id']}"
            logger.warning(f"No open trade found for {match_method}")
            return jsonify({"status": "warning", "message": "No matching open trade found", "match_method": match_method}), 200

        pnl_display = f"${data.get('pnl_usd', 0):.2f}" if data.get('pnl_usd') else f"{data.get('pnl_r', 0):.2f}R"
        logger.info(f"✅ Exit recorded for zone #{data['zone_id']}: {data['outcome']} | P&L: {pnl_display} | MAE: {data['mae_pips']:.1f} pips | Bars: {data['bars_held']}")
        return jsonify({
            "status": "success",
            "zone_id": data['zone_id'],
            "outcome": data['outcome'],
            "pnl_usd": data.get('pnl_usd'),
            "run_mode": data.get('run_mode', 'LIVE'),
            "run_id": data.get('run_id', 'live-default')
        }), 200

    except Exception as e:
        logger.error(f"Exit webhook error: {e}", exc_info=True)
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
    """Comprehensive health check."""
    # Check Supabase connectivity
    supabase_healthy = supabase_db.check_supabase_health()

    # Check paper trader status
    paper_trader_status = {
        "enabled": PAPER_TRADING_ENABLED,
        "auto_execute": PAPER_AUTO_EXECUTE,
        "open_positions": len(paper_trader.get_open_positions()) if paper_trader else 0,
        "max_positions": PAPER_MAX_POSITIONS
    }

    # Determine overall health
    is_healthy = supabase_healthy

    return jsonify({
        "status": "healthy" if is_healthy else "degraded",
        "server": True,
        "discord_configured": bool(DISCORD_WEBHOOK_URL),
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "supabase_reachable": supabase_healthy,
        "paper_trader": paper_trader_status,
        "ai_model_loaded": ai_model is not None,
        "ai_model_type": "universal" if 'universal' in str(MODEL_PATH) else "standard",
        "ai_filter_enabled": AI_FILTER_ENABLED,
        "ai_filter_exclude_symbols": AI_FILTER_EXCLUDE_SYMBOLS,
        "news_filter_enabled": NEWS_FILTER_ENABLED,
        "min_rr_ratio": MIN_RR_RATIO,
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
        .container { max-width: 1600px; margin: 0 auto; }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
        .mode-badge { padding: 5px 12px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }
        .mode-live { background: #00ff88; color: #1a1a2e; }
        .mode-backtest { background: #ff9900; color: #1a1a2e; }
        .mode-replay { background: #9966ff; color: #fff; }
        .mode-selector { display: flex; gap: 10px; align-items: center; }
        .mode-selector select { padding: 8px 12px; border-radius: 5px; border: 1px solid #2a2a4a; background: #16213e; color: #eee; font-size: 0.9em; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: #16213e; padding: 15px; border-radius: 10px; text-align: center; }
        .stat-value { font-size: 1.8em; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #888; margin-top: 5px; font-size: 0.85em; }
        .win { color: #00ff88; }
        .loss { color: #ff4444; }
        table { width: 100%; border-collapse: collapse; background: #16213e; border-radius: 10px; overflow: hidden; font-size: 0.85em; }
        th, td { padding: 10px 8px; text-align: center; border-bottom: 1px solid #2a2a4a; white-space: nowrap; }
        th { background: #0f3460; color: #00d4ff; font-weight: 600; text-transform: uppercase; font-size: 0.75em; letter-spacing: 0.5px; position: sticky; top: 0; }
        td { color: #ddd; }
        tr:hover { background: #1f3a5f; }
        .symbol-col { text-align: left; font-weight: bold; }
        .status-active { color: #00d4ff; background: rgba(0, 212, 255, 0.1); padding: 3px 6px; border-radius: 4px; }
        .status-taken { color: #00ff88; background: rgba(0, 255, 136, 0.1); padding: 3px 6px; border-radius: 4px; }
        .status-closed { color: #00ff88; background: rgba(0, 255, 136, 0.1); padding: 3px 6px; border-radius: 4px; }
        .status-skipped { color: #888; background: rgba(136, 136, 136, 0.1); padding: 3px 6px; border-radius: 4px; }
        .status-missed { color: #ff4444; background: rgba(255, 68, 68, 0.1); padding: 3px 6px; border-radius: 4px; }
        .status-pending { color: #ffaa00; background: rgba(255, 170, 0, 0.1); padding: 3px 6px; border-radius: 4px; }
        .status-filtered { color: #666; background: rgba(102, 102, 102, 0.1); padding: 3px 6px; border-radius: 4px; }
        .buy { color: #00ff88; font-weight: bold; }
        .sell { color: #ff4444; font-weight: bold; }
        .outcome-win { color: #00ff88; font-weight: bold; }
        .outcome-loss { color: #ff4444; font-weight: bold; }
        .pnl-positive { color: #00ff88; }
        .pnl-negative { color: #ff4444; }
        .filter-reason { color: #ff9900; font-size: 0.85em; max-width: 320px; white-space: normal; word-break: break-word; }
        .refresh-btn { background: #00d4ff; color: #1a1a2e; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 0.9em; }
        .refresh-btn:hover { background: #00b4df; }
        .actions a { color: #00d4ff; text-decoration: none; margin: 0 3px; font-size: 0.85em; }
        .actions a:hover { text-decoration: underline; }
        .time-col { font-size: 0.8em; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-row">
            <div>
                <h1>Trading Dashboard</h1>
                <span class="mode-badge mode-{{ current_mode|lower }}">{{ current_mode }}</span>
                {% if current_run_id and current_run_id != 'live-default' %}
                <span style="color:#888; margin-left:10px;">Run: {{ current_run_id }}</span>
                {% endif %}
            </div>
            <div class="mode-selector">
                <form method="get" action="/" style="display:flex; gap:10px; align-items:center;">
                    <select name="mode" onchange="this.form.submit()">
                        <option value="LIVE" {% if current_mode == 'LIVE' %}selected{% endif %}>LIVE</option>
                        <option value="BACKTEST" {% if current_mode == 'BACKTEST' %}selected{% endif %}>BACKTEST</option>
                        <option value="REPLAY" {% if current_mode == 'REPLAY' %}selected{% endif %}>REPLAY</option>
                        <option value="" {% if not current_mode %}selected{% endif %}>ALL</option>
                    </select>
                    <input type="text" name="run_id" placeholder="Run ID (optional)" value="{{ current_run_id or '' }}" style="padding:8px; border-radius:5px; border:1px solid #2a2a4a; background:#16213e; color:#eee; width:150px;">
                    <button type="submit" class="refresh-btn">Filter</button>
                </form>
                <button class="refresh-btn" onclick="location.reload()">Refresh</button>
            </div>
        </div>

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
                <div class="stat-value">{{ stats.active_count }}</div>
                <div class="stat-label">Active</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.closed_count }}</div>
                <div class="stat-label">Closed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#ff9900;">{{ stats.filtered_count }}</div>
                <div class="stat-label">Filtered</div>
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
        </div>

        <h2 style="margin-bottom: 15px;">Recent Alerts</h2>
        <div style="overflow-x: auto; max-height: 600px; overflow-y: auto;">
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Open Time</th>
                    <th>Close Time</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>SL</th>
                    <th>TP</th>
                    <th>R:R</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>P&L ($)</th>
                    <th>P&L (R)</th>
                    <th>Filter Reason</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for alert in alerts %}
                <tr>
                    <td>#{{ alert.id }}</td>
                    <td class="time-col">{{ (alert.entry_time or alert.created_at) | jerusalem_time }}</td>
                    <td class="time-col">{{ alert.exit_time | jerusalem_time if alert.exit_time else (alert.close_time | jerusalem_time if alert.close_time else '-') }}</td>
                    <td class="symbol-col"><strong>{{ alert.symbol }}</strong></td>
                    <td class="{{ alert.side }}">{{ alert.side|upper }}</td>
                    <td style="color:#00d4ff">{{ alert.entry }}</td>
                    <td style="color:#ff4444">{{ alert.sl }}</td>
                    <td style="color:#00ff88">{{ alert.tp }}</td>
                    <td>1:{{ "%.2f"|format(alert.rr_ratio or 0) }}</td>
                    <td><span class="status-{{ alert.status }}">{{ alert.status }}</span></td>
                    <td>
                        {% if alert.outcome == 'win' %}
                        <span class="outcome-win">WIN</span>
                        {% elif alert.outcome == 'loss' %}
                        <span class="outcome-loss">LOSS</span>
                        {% else %}
                        -
                        {% endif %}
                    </td>
                    <td>
                        {% if alert.pnl_usd is not none %}
                        <span class="{% if alert.pnl_usd >= 0 %}pnl-positive{% else %}pnl-negative{% endif %}">
                            ${{ "%.2f"|format(alert.pnl_usd) }}
                        </span>
                        {% elif alert.pnl is not none %}
                        <span class="{% if alert.pnl >= 0 %}pnl-positive{% else %}pnl-negative{% endif %}">
                            ${{ "%.2f"|format(alert.pnl) }}
                        </span>
                        {% else %}
                        -
                        {% endif %}
                    </td>
                    <td>
                        {% if alert.pnl_r is not none %}
                        <span class="{% if alert.pnl_r >= 0 %}pnl-positive{% else %}pnl-negative{% endif %}">
                            {{ "%.2f"|format(alert.pnl_r) }}R
                        </span>
                        {% else %}
                        -
                        {% endif %}
                    </td>
                    <td class="filter-reason" title="{{ (alert.notes or '') | format_filter_reason }}">
                        {% if alert.status == 'filtered' %}
                        {{ (alert.notes or '') | format_filter_reason }}
                        {% else %}
                        -
                        {% endif %}
                    </td>
                    <td class="actions">
                        {% if alert.status == 'pending' or alert.status == 'active' %}
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
    """Web dashboard with run_mode/run_id filtering."""
    run_mode = request.args.get('mode', 'LIVE')
    run_id = request.args.get('run_id', '').strip() or None
    if run_mode == '':
        run_mode = None

    stats = get_statistics(run_mode=run_mode, run_id=run_id)
    alerts = get_recent_alerts(100, run_mode=run_mode, run_id=run_id)

    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        alerts=alerts,
        current_mode=run_mode or 'ALL',
        current_run_id=run_id
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Trading Alert Server v5.0 - Enhanced Telemetry Edition")
    logger.info("=" * 60)

    # Initialize database
    init_db()

    # === NOTIFICATION CHANNELS ===
    logger.info("")
    logger.info("📢 NOTIFICATION CHANNELS:")
    if not DISCORD_WEBHOOK_URL and not TELEGRAM_BOT_TOKEN:
        logger.warning("  ⚠️ No notification channels configured!")
        logger.warning("  Add DISCORD_WEBHOOK_URL or TELEGRAM_BOT_TOKEN to .env")
    if DISCORD_WEBHOOK_URL:
        logger.info("  ✅ Discord: Configured")
    else:
        logger.info("  ❌ Discord: Not configured")
    if TELEGRAM_BOT_TOKEN:
        logger.info("  ✅ Telegram: Configured")
    else:
        logger.info("  ❌ Telegram: Not configured")

    # === FILTERS ===
    logger.info("")
    logger.info("🔍 FILTERS:")
    logger.info(f"  Min R:R Ratio: {MIN_RR_RATIO}")
    if TRADING_SESSIONS:
        logger.info(f"  Trading Sessions: {TRADING_SESSIONS} UTC")
    else:
        logger.info("  Trading Sessions: Disabled (24/7)")
    logger.info(f"  Swap Hours Filter: {'Enabled' if SWAP_HOURS_ENABLED else 'Disabled'} ({SWAP_HOURS_UTC} UTC)")
    logger.info(f"  News Filter: {'Enabled' if NEWS_FILTER_ENABLED else 'Disabled'}")

    # === AI MODEL ===
    logger.info("")
    logger.info("🧠 AI MODEL:")
    if ai_model:
        model_type = 'Universal' if 'universal' in str(MODEL_PATH) else 'Standard'
        logger.info(f"  ✅ Status: LOADED ({model_type})")
        logger.info(f"  AI Filter: {'Enabled' if AI_FILTER_ENABLED else 'Disabled'}")
        logger.info(f"  Min Win Probability: {AI_MIN_WIN_PROBABILITY:.0%}")
        logger.info(f"  Excluded Symbols: {', '.join(AI_FILTER_EXCLUDE_SYMBOLS) if AI_FILTER_EXCLUDE_SYMBOLS else 'None'}")
    else:
        logger.warning("  ⚠️ Status: NOT LOADED (Check MODEL_PATH)")

    # === PAPER TRADING ===
    logger.info("")
    logger.info("📝 PAPER TRADING:")
    logger.info(f"  Enabled: {PAPER_TRADING_ENABLED}")
    if PAPER_TRADING_ENABLED:
        logger.info(f"  Auto-Execute: {PAPER_AUTO_EXECUTE}")
        logger.info(f"  Max Positions: {PAPER_MAX_POSITIONS}")
        logger.info(f"  Symbols: {', '.join(PAPER_SYMBOLS) if PAPER_SYMBOLS else 'All'}")
        if paper_trader:
            open_pos = len(paper_trader.get_open_positions())
            logger.info(f"  Open Positions: {open_pos}")

    # === ENDPOINTS ===
    logger.info("")
    logger.info("🌐 ENDPOINTS:")
    logger.info(f"  Dashboard: http://localhost:{WEBHOOK_PORT}/")
    logger.info(f"  Webhook: http://localhost:{WEBHOOK_PORT}/webhook")
    logger.info(f"  Health: http://localhost:{WEBHOOK_PORT}/health")
    logger.info(f"  Stats API: http://localhost:{WEBHOOK_PORT}/stats")

    logger.info("")
    logger.info("=" * 60)
    logger.info("Server starting... Press Ctrl+C to stop.")
    logger.info("=" * 60)

    app.run(host='0.0.0.0', port=WEBHOOK_PORT, debug=False)


if __name__ == "__main__":
    main()
