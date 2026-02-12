#!/bin/bash
# Quick script to verify CSV has AI features

CSV_FILE="${1:-$HOME/Downloads/backtest.csv}"

if [ ! -f "$CSV_FILE" ]; then
    echo "❌ File not found: $CSV_FILE"
    echo ""
    echo "Usage: bash ml/check_csv_has_features.sh ~/Downloads/backtest.csv"
    exit 1
fi

echo "📊 Checking CSV file: $CSV_FILE"
echo ""

# Check if Comment column exists
if ! head -1 "$CSV_FILE" | grep -q "Comment"; then
    echo "❌ No 'Comment' column found!"
    echo "   Available columns:"
    head -1 "$CSV_FILE" | tr ',' '\n' | nl
    exit 1
fi

echo "✅ Comment column exists"
echo ""

# Extract comment column (assuming it's the last column)
COMMENT_COL=$(head -1 "$CSV_FILE" | tr ',' '\n' | grep -n "Comment" | cut -d: -f1)

# Check if it has AI features
SAMPLE_COMMENT=$(sed -n '2p' "$CSV_FILE" | cut -d',' -f"$COMMENT_COL")

if echo "$SAMPLE_COMMENT" | grep -q "F:score"; then
    echo "✅ AI features found in Comment column!"
    echo ""
    echo "Sample comment (first trade):"
    echo "$SAMPLE_COMMENT" | cut -c1-200
    echo ""
    echo "🎉 CSV is ready for training!"
    echo ""
    echo "Next step:"
    echo "  python ml/collect_training_data.py --source tradingview --input $CSV_FILE"
else
    echo "❌ AI features NOT found in Comment column!"
    echo ""
    echo "Sample comment (first trade):"
    echo "$SAMPLE_COMMENT"
    echo ""
    echo "⚠️  You need to enable 'Show AI Debug Text On Order Labels' in TradingView!"
    echo ""
    echo "Steps:"
    echo "  1. Open TradingView strategy settings (⚙️ icon)"
    echo "  2. Go to '⚙️ Advanced / Manual Tweaks'"
    echo "  3. Enable ☑️ 'Show AI Debug Text On Order Labels'"
    echo "  4. Re-export the backtest data"
    exit 1
fi
