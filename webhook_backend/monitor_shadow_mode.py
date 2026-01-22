#!/usr/bin/env python3
"""
Shadow Mode Monitor
===================
Tracks AI model predictions vs actual outcomes WITHOUT filtering trades.

Usage:
    python monitor_shadow_mode.py

Generates:
    - shadow_mode_report.json (daily metrics)
    - Console output with key statistics
"""

import supabase_db
from datetime import datetime, timedelta
import json
from pathlib import Path
import pickle
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Load AI model
MODEL_PATH = Path('models/model_ultimate.pkl')
if not MODEL_PATH.exists():
    MODEL_PATH = Path('model_universal.pkl')

def load_model():
    """Load trained model"""
    if not MODEL_PATH.exists():
        logging.error(f"❌ Model not found at {MODEL_PATH}")
        return None

    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    logging.info(f"✅ Loaded model from {MODEL_PATH}")
    return model

def extract_features_from_trade(trade):
    """Extract 17 features from trade data for prediction"""
    # V7.1 format: 17 features
    features = [
        float(trade.get('score', 50)),
        int(trade.get('freshness', 10)),
        int(trade.get('session', 1)),
        0 if trade.get('side', '').lower() == 'buy' else 1,  # zone_type
        float(trade.get('atr_ratio', 0.5)),
        int(trade.get('is_accuracy', 0)),
        int(trade.get('trend', 1)),
        float(trade.get('rsi', 50)),
        int(trade.get('htf_trend', 1)),
        float(trade.get('rvol', 1.0)),
        float(trade.get('adx', 25.0)),
        int(trade.get('touch_count', 0)),
        float(trade.get('base_quality', 50.0)),
        float(trade.get('departure_strength', 50.0)),
        float(trade.get('liquidity_distance', 50.0)),
        float(trade.get('liquidity_spread', 50.0)),
        float(trade.get('return_strength', 50.0)),
    ]
    return features

def analyze_shadow_mode(model, days=7):
    """
    Analyze what model WOULD have done vs actual outcomes
    """
    logging.info("="*60)
    logging.info("SHADOW MODE ANALYSIS")
    logging.info("="*60)

    # Initialize Supabase
    supabase_db.init_supabase()

    # Get all trades from last N days
    all_trades = supabase_db.supabase.table('trading_signals').select('*').execute().data

    # Filter to last N days
    from datetime import timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent_trades = [
        t for t in all_trades
        if datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')) >= cutoff
    ]

    logging.info(f"Analyzing {len(recent_trades)} trades from last {days} days")

    if len(recent_trades) == 0:
        logging.warning("⚠️  No trades found. System needs more data.")
        return

    # Separate into closed vs open trades
    closed_trades = [t for t in recent_trades if t.get('status') == 'closed']
    open_trades = [t for t in recent_trades if t.get('status') != 'closed']

    logging.info(f"   Closed: {len(closed_trades)}, Open: {len(open_trades)}")

    if len(closed_trades) == 0:
        logging.warning("⚠️  No closed trades yet. Cannot calculate accuracy.")
        logging.info("\n📊 OPEN TRADES - Model Predictions:")
        for trade in open_trades:
            try:
                features = [extract_features_from_trade(trade)]
                win_prob = model.predict_proba(features)[0][1]
                prediction = "ACCEPT" if win_prob >= 0.5 else "REJECT"

                logging.info(f"   #{trade['id']} {trade['symbol']} {trade['side'].upper():4s} | "
                           f"Win Prob: {win_prob:.1%} | Model: {prediction}")
            except Exception as e:
                logging.warning(f"   #{trade['id']} - Prediction failed: {e}")
        return

    # Analyze closed trades
    results = {
        'total_closed': len(closed_trades),
        'wins': 0,
        'losses': 0,
        'model_would_accept': 0,
        'model_would_reject': 0,
        'correct_accepts': 0,  # TP
        'correct_rejects': 0,  # TN
        'false_accepts': 0,    # FP
        'false_rejects': 0,    # FN (missed winners)
        'threshold': 0.5,
        'predictions': []
    }

    for trade in closed_trades:
        # Get actual outcome
        outcome = trade.get('outcome', 'unknown')
        if outcome not in ['win', 'loss']:
            continue  # Skip breakevens/unknowns

        is_win = outcome == 'win'
        if is_win:
            results['wins'] += 1
        else:
            results['losses'] += 1

        # Get model prediction
        try:
            features = [extract_features_from_trade(trade)]
            win_prob = model.predict_proba(features)[0][1]
            would_accept = win_prob >= 0.5

            if would_accept:
                results['model_would_accept'] += 1
                if is_win:
                    results['correct_accepts'] += 1  # TP
                else:
                    results['false_accepts'] += 1    # FP
            else:
                results['model_would_reject'] += 1
                if not is_win:
                    results['correct_rejects'] += 1  # TN
                else:
                    results['false_rejects'] += 1    # FN - MISSED WINNER!

            results['predictions'].append({
                'trade_id': trade['id'],
                'symbol': trade['symbol'],
                'side': trade['side'],
                'win_prob': win_prob,
                'actual_outcome': outcome,
                'would_accept': would_accept
            })

        except Exception as e:
            logging.warning(f"   Trade #{trade.get('id')} prediction failed: {e}")

    # Calculate metrics
    total = results['wins'] + results['losses']
    actual_win_rate = results['wins'] / total if total > 0 else 0

    # Model metrics
    tp = results['correct_accepts']
    tn = results['correct_rejects']
    fp = results['false_accepts']
    fn = results['false_rejects']

    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    # Print results
    logging.info("\n" + "="*60)
    logging.info("📊 RESULTS")
    logging.info("="*60)
    logging.info(f"Actual Performance (All Trades):")
    logging.info(f"   Total: {total} | Wins: {results['wins']} | Losses: {results['losses']}")
    logging.info(f"   Win Rate: {actual_win_rate:.1%}")

    logging.info(f"\nModel Performance (Shadow Mode):")
    logging.info(f"   Would Accept: {results['model_would_accept']} trades")
    logging.info(f"   Would Reject: {results['model_would_reject']} trades")
    logging.info(f"   Accuracy: {accuracy:.1%}")
    logging.info(f"   Precision: {precision:.1%} (of accepted, how many won)")
    logging.info(f"   Recall: {recall:.1%} (of all winners, how many caught)")
    logging.info(f"   F1-Score: {f1:.3f}")

    logging.info(f"\n⚠️  CRITICAL METRIC:")
    logging.info(f"   Missed Winners (False Negatives): {fn} out of {results['wins']} winners")
    if results['wins'] > 0:
        miss_rate = fn / results['wins']
        logging.info(f"   Miss Rate: {miss_rate:.1%}")

    # Recommendation
    logging.info("\n" + "="*60)
    if total < 50:
        logging.info("⏳ RECOMMENDATION: Collect more data (need 50+ closed trades)")
        logging.info(f"   Current: {total} trades | Target: 50+")
    elif accuracy < 0.6:
        logging.info("❌ RECOMMENDATION: Do NOT enable AI filter")
        logging.info("   Model accuracy too low. Needs retraining.")
    elif fn > tp:
        logging.info("⚠️  RECOMMENDATION: Do NOT enable AI filter yet")
        logging.info(f"   Model missing too many winners ({fn} missed vs {tp} caught)")
        logging.info("   Consider lowering threshold to 0.40 or retraining.")
    elif precision >= 0.65 and recall >= 0.50:
        logging.info("✅ RECOMMENDATION: Consider enabling AI filter")
        logging.info("   Model shows value. Enable with threshold=0.45-0.50")
    else:
        logging.info("⏸️  RECOMMENDATION: Continue monitoring")
        logging.info("   Model shows potential but needs more validation.")

    logging.info("="*60)

    # Save report
    report_path = Path('shadow_mode_report.json')
    results['analyzed_at'] = datetime.utcnow().isoformat()
    results['actual_win_rate'] = actual_win_rate
    results['model_accuracy'] = accuracy
    results['model_precision'] = precision
    results['model_recall'] = recall
    results['model_f1'] = f1

    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)

    logging.info(f"\n💾 Report saved to {report_path}")

def main():
    model = load_model()
    if model is None:
        return

    # Run analysis
    analyze_shadow_mode(model, days=30)  # Look at last 30 days

if __name__ == '__main__':
    main()
