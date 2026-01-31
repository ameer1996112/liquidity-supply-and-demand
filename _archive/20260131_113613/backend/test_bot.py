#!/usr/bin/env python3
"""
Trading Bot Health & Performance Test Script
============================================
Tests all bot components to ensure optimal performance
"""

import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
RAILWAY_URL = os.getenv('RAILWAY_URL', 'http://localhost:3000')  # Set your Railway URL
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    """Print section header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    """Print success message"""
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    """Print error message"""
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}⚠{RESET} {text}")

def test_health():
    """Test 1: Health Check"""
    print_header("Test 1: Health Check")
    
    try:
        response = requests.get(f"{RAILWAY_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Server is healthy!")
            print(f"  Discord: {'✓' if data.get('discord') else '✗'}")
            print(f"  Telegram: {'✓' if data.get('telegram') else '✗'}")
            print(f"  Database: {'✓' if data.get('database') else '✗'}")
            print(f"  Timestamp: {data.get('timestamp')}")
            return True
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot connect to server: {e}")
        print_warning(f"Make sure RAILWAY_URL is set correctly")
        return False

def test_webhook_good_signal():
    """Test 2: Send Good Quality Signal"""
    print_header("Test 2: Good Quality Signal (Should Pass)")
    
    # Simulate a high-quality XAUUSD trade from Pine Script
    payload = {
        "symbol": "XAUUSD",
        "side": "buy",
        "entry": 2050.00,
        "sl": 2040.00,
        "tp": 2070.00,  # 1:2 R:R
        "size": 0.10,
        "zone_id": "D-TEST-001",
        "zone_type": "demand",
        "zone_top": 2052.00,
        "zone_bottom": 2048.00,
        "zone_size_pips": 40.0,
        "entry_model": "FLIP",
        "liq_swept": True,
        "target_swept": True,
        "caused_sweep": True,
        "is_accuracy": True,
        # V3 AI Features
        "score": 75,
        "freshness": 5,
        "session": 2,  # London
        "atr_ratio": 0.8,
        "is_accuracy": 1,
        "trend": 1,
        "rsi": 55,
        "htf_trend": 1,  # Bullish HTF
        "rvol": 1.5  # High volume
    }
    
    try:
        response = requests.post(f"{RAILWAY_URL}/webhook", json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            if data.get('status') == 'success':
                print_success(f"Signal accepted! Alert ID: {data.get('alert_id')}")
                print(f"  Discord sent: {'✓' if data.get('discord') else '✗'}")
                print(f"  Telegram sent: {'✓' if data.get('telegram') else '✗'}")
                return True
            elif data.get('status') == 'filtered':
                print_warning(f"Signal filtered: {data.get('reason')}")
                return True
        else:
            print_error(f"Webhook failed: {response.text}")
            return False
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False

def test_webhook_bad_signal():
    """Test 3: Send Low Quality Signal (Should Filter)"""
    print_header("Test 3: Low Quality Signal (Should Filter)")
    
    # Simulate a low-quality trade that should be filtered
    payload = {
        "symbol": "XAUUSD",
        "side": "sell",
        "entry": 2050.00,
        "sl": 2055.00,
        "tp": 2048.00,  # 1:0.4 R:R (too low)
        "size": 0.10,
        "zone_id": "S-TEST-002",
        # V3 AI Features (low quality)
        "score": 30,
        "freshness": 20,
        "session": 1,  # Asian session
        "atr_ratio": 0.3,
        "is_accuracy": 0,
        "trend": -1,
        "rsi": 30,
        "htf_trend": -1,
        "rvol": 0.5  # Low volume
    }
    
    try:
        response = requests.post(f"{RAILWAY_URL}/webhook", json=payload, timeout=10)
        data = response.json()
        
        if data.get('status') == 'filtered':
            print_success(f"Correctly filtered: {data.get('reason')}")
            return True
        elif data.get('status') == 'success':
            print_warning("Signal was accepted (filters may be too loose)")
            return True
        else:
            print_error(f"Unexpected response: {data}")
            return False
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False

def test_ai_filter():
    """Test 4: AI Model Predictions"""
    print_header("Test 4: AI Model Filter")
    
    # Test with high-probability setup
    high_prob = {
        "symbol": "XAUUSD",
        "side": "buy",
        "entry": 2050.00,
        "sl": 2040.00,
        "tp": 2070.00,
        "size": 0.10,
        "score": 85,
        "freshness": 3,
        "session": 2,  # London
        "atr_ratio": 1.2,
        "is_accuracy": 1,
        "trend": 1,
        "rsi": 60,
        "htf_trend": 1,
        "rvol": 2.0
    }
    
    try:
        response = requests.post(f"{RAILWAY_URL}/webhook", json=high_prob, timeout=10)
        data = response.json()
        
        if data.get('status') in ['success', 'filtered']:
            print_success("AI model is processing signals")
            if 'AI Win Probability' in data.get('reason', ''):
                prob = data.get('reason').split('AI Win Probability ')[1].split('%')[0]
                print(f"  Predicted Win Probability: {prob}%")
            return True
        else:
            print_warning("AI filter status unclear")
            return True
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False

def test_statistics():
    """Test 5: Statistics Endpoint"""
    print_header("Test 5: Statistics & Database")
    
    try:
        response = requests.get(f"{RAILWAY_URL}/stats", timeout=5)
        
        if response.status_code == 200:
            stats = response.json()
            print_success("Statistics endpoint working!")
            print(f"  Total alerts: {stats.get('total_alerts', 0)}")
            print(f"  Win rate: {stats.get('win_rate', 0):.1f}%")
            print(f"  Total P&L: ${stats.get('total_pnl', 0):.2f}")
            print(f"  Today's alerts: {stats.get('today_alerts', 0)}")
            return True
        else:
            print_error(f"Stats failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False

def test_position_sizing():
    """Test 6: Position Size Calculator"""
    print_header("Test 6: Position Size Calculator")
    
    try:
        params = {
            "sl_pips": 20,
            "symbol": "XAUUSD",
            "balance": 10000,
            "risk": 1.0
        }
        
        response = requests.get(f"{RAILWAY_URL}/position-size", params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Position calculator working!")
            print(f"  Lot size for 20 pip SL: {data.get('lots', 0):.2f}")
            print(f"  Risk amount: ${data.get('risk_amount', 0):.2f}")
            return True
        else:
            print_error(f"Calculator failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and generate report"""
    print_header("🚀 Trading Bot Comprehensive Test Suite")
    print(f"Testing bot at: {RAILWAY_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Health Check", test_health),
        ("Good Signal Processing", test_webhook_good_signal),
        ("Bad Signal Filtering", test_webhook_bad_signal),
        ("AI Model Filter", test_ai_filter),
        ("Statistics Tracking", test_statistics),
        ("Position Sizing", test_position_sizing),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            time.sleep(1)  # Pause between tests
        except Exception as e:
            print_error(f"Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Final Report
    print_header("📊 Test Results Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")
    
    print(f"\n{BLUE}Score: {passed}/{total} tests passed ({passed/total*100:.0f}%){RESET}")
    
    if passed == total:
        print_success("\n🎉 All systems operational! Your bot is ready.")
    elif passed >= total * 0.8:
        print_warning(f"\n⚠️  Bot is mostly working, but {total-passed} test(s) failed.")
    else:
        print_error("\n❌ Multiple failures detected. Check Railway logs.")
    
    # Recommendations
    print_header("💡 Recommendations")
    
    if not RAILWAY_URL.startswith('http'):
        print_warning("Set RAILWAY_URL environment variable to your Railway app URL")
    
    if not DISCORD_WEBHOOK_URL:
        print_warning("DISCORD_WEBHOOK_URL not set - notifications disabled")
    
    print_success("Check Railway dashboard for live logs")
    print_success("Update Pine Script in TradingView to activate filters")
    print_success("Monitor first few live signals to verify behavior")

if __name__ == "__main__":
    run_all_tests()
