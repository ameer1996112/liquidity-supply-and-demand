#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 📊 Collect More Training Data - Comprehensive Guide
# ═══════════════════════════════════════════════════════════════
#
# This script helps you collect 5,000+ trades for better AI accuracy
#
# Current data: 2,194 trades (ROC-AUC: 0.543 - too weak)
# Target: 5,000+ trades (ROC-AUC: >0.65 - usable)
#
# ═══════════════════════════════════════════════════════════════

set -e

echo "════════════════════════════════════════════════════════════════"
echo "📊 STEP 1: Export MORE Backtest Data from TradingView"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "You currently have 2,194 trades from 5 symbols."
echo "To improve model accuracy, export backtests for these additional symbols:"
echo ""
echo "🔹 Major Forex Pairs (high volume):"
echo "   - EURUSD, GBPUSD, USDJPY, GBPJPY (already done ✓)"
echo "   - AUDUSD, NZDUSD, USDCAD, EURGBP, EURJPY, GBPAUD"
echo ""
echo "🔹 Indices (trending markets):"
echo "   - NAS100, SPX500, US30, GER40, UK100"
echo ""
echo "🔹 Crypto (high volatility):"
echo "   - BTCUSD, ETHUSD"
echo ""
echo "🔹 Commodities:"
echo "   - XAUUSD (already done ✓), XAGUSD, USOIL, UKOIL"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📝 Export Instructions:"
echo "════════════════════════════════════════════════════════════════"
echo "1. Open TradingView.com"
echo "2. Load your S&D_Algo_[Pro] strategy on a chart"
echo "3. For EACH symbol above:"
echo "   a. Select symbol (e.g., AUDUSD)"
echo "   b. Set timeframe: 5 minutes"
echo "   c. Set date range: Jan 1, 2023 → Today"
echo "   d. Wait for backtest to complete"
echo "   e. Go to Strategy Tester → List of Trades"
echo "   f. Select All (Cmd+A) → Copy (Cmd+C)"
echo "   g. Paste in Excel → Save As CSV:"
echo "      ~/Downloads/backtest_audusd.csv"
echo ""
echo "4. Repeat for all symbols"
echo ""
echo "⚠️  CRITICAL: Make sure the 'Signal' column contains AI features!"
echo "   Should look like: | F:score=95 | F:fresh=14 | F:session=2 | ..."
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Press Enter when you've exported all backtest CSVs to ~/Downloads/"
echo "════════════════════════════════════════════════════════════════"
read -p ""

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 STEP 2: Combine All Backtest Files"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Count how many backtest files we have
backtest_count=$(ls ~/Downloads/backtest_*.csv 2>/dev/null | wc -l | tr -d ' ')
echo "Found $backtest_count backtest files in ~/Downloads/"

if [ "$backtest_count" -lt 5 ]; then
    echo ""
    echo "⚠️  WARNING: Only $backtest_count backtest files found."
    echo "   You should have at least 10+ files for good model performance."
    echo ""
    read -p "Continue anyway? (y/n): " continue_choice
    if [ "$continue_choice" != "y" ]; then
        echo "❌ Cancelled. Export more backtests first."
        exit 1
    fi
fi

echo ""
echo "Combining all backtest files..."

# Combine all backtest files
cd ~/Downloads
head -1 backtest_eurusd.csv > backtest_combined_all.csv 2>/dev/null || head -1 backtest_*.csv | head -1 > backtest_combined_all.csv
for f in backtest_*.csv; do
    if [ "$f" != "backtest_combined_all.csv" ] && [ "$f" != "backtest_combined.csv" ]; then
        tail -n +2 "$f" >> backtest_combined_all.csv
    fi
done

total_lines=$(wc -l < backtest_combined_all.csv)
total_trades=$((total_lines / 2))

echo "✅ Combined file has $total_lines lines (~$total_trades trades)"
echo ""

if [ "$total_trades" -lt 3000 ]; then
    echo "⚠️  WARNING: Only $total_trades trades found."
    echo "   For good model performance, aim for 5,000+ trades."
    echo "   Consider:"
    echo "   - Exporting more symbols"
    echo "   - Using longer date ranges"
    echo "   - Including multiple timeframes (5m, 15m, 1h)"
    echo ""
fi

echo "════════════════════════════════════════════════════════════════"
echo "📊 STEP 3: Parse AI Features & Engineer New Features"
echo "════════════════════════════════════════════════════════════════"
echo ""

cd - > /dev/null

python ml/collect_training_data.py --source tradingview --input ~/Downloads/backtest_combined_all.csv

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 STEP 4: Train LightGBM Model"
echo "════════════════════════════════════════════════════════════════"
echo ""

python ml/train_ai_guardian_v3_lightgbm.py --data ml/training_data.csv

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ TRAINING COMPLETE!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Check results:"
echo "   - Metrics: cat ml/model_metadata_v3.json"
echo "   - Charts: open ml/feature_importance_v3.png"
echo "   - Charts: open ml/model_metrics_v3.png"
echo ""
echo "🎯 Target metrics for production:"
echo "   - ROC-AUC: >0.65 (currently shows in output)"
echo "   - Recall: >70% (catch most winning trades)"
echo "   - Precision: >35% (reduce false positives)"
echo ""
echo "If ROC-AUC < 0.60, consider:"
echo "   1. Collect MORE trades (5,000-10,000 target)"
echo "   2. Add MORE features to Pine Script export"
echo "   3. Try different feature combinations"
echo ""
