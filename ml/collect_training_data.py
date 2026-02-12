"""
Training Data Collection Helper
================================

🎯 PURPOSE:
Extract trade data from TradingView Strategy Tester for AI model training.

📊 REQUIRED DATA FORMAT:
CSV file with these columns:
- outcome: 1 (win) or 0 (loss)
- score: Zone quality score (0-100)
- freshness: First touch (0 or 1)
- session: Trading session (0=Asian, 1=London, 2=NY, 3=Off-hours)
- atr_ratio: Zone size / ATR
- is_accuracy: Accuracy zone flag (0 or 1)
- trend: Current trend (0 or 1)
- rsi: RSI indicator (0-100)
- htf_trend: Higher timeframe trend (0 or 1)
- rvol: Relative volume
- adx: ADX strength (0-100)
- touch_count: Number of touches
- base_quality: Base candle quality (0-100)
- departure_strength: Impulse strength (0-100)
- liquidity_distance: Distance to liquidity (pips)
- liquidity_spread: Liquidity range (pips)
- return_strength: Return momentum (0-100)
- zone_type: Demand (1) or Supply (-1)
- entry_model: Entry type (1=Flip, 2=DirClose, 3=BoC)

📁 COLLECTION METHODS:

METHOD 1: Extract from TradingView Strategy Tester (RECOMMENDED)
-----------------------------------------------------------------
1. Run your Pine Script strategy in TradingView
2. Open "Strategy Tester" tab
3. Click "List of Trades"
4. Copy all trades (Ctrl+A, Ctrl+C)
5. Paste into Excel/Google Sheets
6. Save as CSV: backtest_results.csv
7. Run: python ml/collect_training_data.py --source tradingview --input backtest_results.csv

METHOD 2: Extract from trading_signals database
------------------------------------------------
1. Export data from database
2. Run: python ml/collect_training_data.py --source database --days 30

METHOD 3: Simulate data (FOR TESTING ONLY)
-------------------------------------------
1. Generate synthetic data for testing
2. Run: python ml/collect_training_data.py --source synthetic --count 500

🚀 USAGE:
# From TradingView export:
python ml/collect_training_data.py --source tradingview --input backtest_results.csv

# From database (last 30 days):
python ml/collect_training_data.py --source database --days 30

# Generate synthetic data:
python ml/collect_training_data.py --source synthetic --count 500

📁 OUTPUT:
Saves to: ml/training_data.csv (ready for train_ai_guardian_v2_pro.py)
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


ML_DIR = Path(__file__).parent
OUTPUT_PATH = ML_DIR / "training_data.csv"


# ══════════════════════════════════════════════════════════
# METHOD 1: TradingView Strategy Tester Export
# ══════════════════════════════════════════════════════════

def extract_from_tradingview(input_csv: Path) -> pd.DataFrame:
    """
    Parse TradingView Strategy Tester export.

    Expected TradingView columns:
    - Trade #: Trade number
    - Signal: Entry/Exit signal name
    - Date/Time: Entry time
    - Type: Long/Short
    - Price: Entry price
    - Contracts: Position size
    - Profit: P/L in currency
    - Profit %: P/L percentage
    - Cum. Profit: Cumulative profit
    - Run-up: Best profit during trade
    - Drawdown: Worst loss during trade

    We extract:
    - outcome: 1 if Profit > 0, else 0
    - All features from Pine Script (if available in comment)
    """
    print(f"📁 Loading TradingView export from {input_csv}...")
    df = pd.read_csv(input_csv, encoding='utf-8-sig', on_bad_lines='skip')

    # Parse trades (only process Entry rows, skip Exit rows)
    trades = []
    for _, row in df.iterrows():
        # Skip exit rows - we only need entry rows with AI features
        trade_type = str(row.get('Type', ''))
        if 'Exit' in trade_type or 'exit' in trade_type:
            continue
        # Determine outcome (1=win, 0=loss)
        # Try different column names that TradingView uses
        profit_pct = row.get('Net P&L %', row.get('Profit %', row.get('Profit%', 0)))
        if isinstance(profit_pct, str):
            profit_pct = float(profit_pct.replace('%', ''))

        # Also try P&L in USD if percentage not available
        if profit_pct == 0:
            profit_usd = row.get('Net P&L USD', row.get('Profit', 0))
            if isinstance(profit_usd, str):
                profit_usd = float(profit_usd.replace(',', ''))
            outcome = 1 if profit_usd > 0 else 0
        else:
            outcome = 1 if profit_pct > 0 else 0

        # Extract features from comment or signal column (if Pine Script includes AI features)
        # TradingView exports may put AI features in either 'Comment' or 'Signal' column
        comment = str(row.get('Comment', ''))
        if not comment or 'F:' not in comment:
            # Try Signal column (TradingView sometimes puts entry comment here)
            comment = str(row.get('Signal', ''))

        # Parse features from comment like "F:score=75 | F:freshness=1 | ..."
        features = parse_features_from_comment(comment)

        # Add basic features if not in comment
        if not features:
            # Use defaults
            features = {
                'score': 50,  # Neutral
                'freshness': 1,  # Assume fresh
                'session': 1,  # London
                'atr_ratio': 1.0,
                'is_accuracy': 0,
                'trend': 1,
                'rsi': 50,
                'htf_trend': 1,
                'rvol': 1.0,
                'adx': 30,
                'touch_count': 1,
                'base_quality': 50,
                'departure_strength': 50,
                'liquidity_distance': 10,
                'liquidity_spread': 20,
                'return_strength': 50,
                'zone_type': 1 if 'Long' in str(row.get('Type', '')) else -1,
                'entry_model': 2,  # DirClose
            }

        features['outcome'] = outcome
        trades.append(features)

    df_out = pd.DataFrame(trades)
    print(f"✅ Extracted {len(df_out)} trades ({df_out['outcome'].sum()} wins, {len(df_out) - df_out['outcome'].sum()} losses)")
    return df_out


def parse_features_from_comment(comment: str) -> dict:
    """
    Parse AI features from Pine Script comment.

    Example comment:
    "F:score=75 | F:freshness=1 | F:session=1 | F:atr_ratio=1.2 | ..."

    Returns:
        dict of features, or empty dict if not found
    """
    features = {}
    if 'F:' not in comment:
        return features

    # Split by | and parse each F:key=value
    parts = comment.split('|')
    for part in parts:
        part = part.strip()
        if not part.startswith('F:'):
            continue

        # Remove F: prefix and split key=value
        kv = part[2:].strip()
        if '=' not in kv:
            continue

        key, value = kv.split('=', 1)
        key = key.strip()
        value = value.strip()

        # Try to convert to number
        try:
            if '.' in value:
                features[key] = float(value)
            else:
                features[key] = int(value)
        except:
            pass  # Skip if conversion fails

    return features


# ══════════════════════════════════════════════════════════
# METHOD 2: Database Export
# ══════════════════════════════════════════════════════════

def extract_from_database(days: int = 30) -> pd.DataFrame:
    """
    Extract trades from trading_signals database.

    Requires:
    - Database connection configured
    - trading_signals table with AI features

    Returns:
        DataFrame with features and outcome
    """
    print(f"🗄️  Extracting trades from database (last {days} days)...")

    try:
        from sqlalchemy import create_engine, text
        from config import get_settings

        settings = get_settings()
        engine = create_engine(settings.database_url.get_secret_value())

        # Query for trades with outcome
        query = text("""
            SELECT
                -- Outcome (1=win, 0=loss)
                CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END as outcome,

                -- AI Features
                score,
                CASE WHEN touch_count = 1 THEN 1 ELSE 0 END as freshness,
                session,
                (zone_top - zone_bottom) / NULLIF(atr, 0) as atr_ratio,
                CASE WHEN is_accuracy THEN 1 ELSE 0 END as is_accuracy,
                trend,
                rsi,
                htf_trend,
                rvol,
                adx,
                touch_count,
                base_quality,
                departure_strength,
                liquidity_distance,
                liquidity_spread,
                return_strength,
                CASE WHEN zone_type = 'demand' THEN 1 ELSE -1 END as zone_type,
                CASE
                    WHEN entry_model = 'FLIP' THEN 1
                    WHEN entry_model = 'DIR_CLOSE' THEN 2
                    WHEN entry_model = 'BREAK_CANDLE' THEN 3
                    ELSE 2
                END as entry_model

            FROM trading_signals
            WHERE
                close_time IS NOT NULL
                AND close_time >= NOW() - INTERVAL :days DAY
                AND net_pnl IS NOT NULL
            ORDER BY close_time DESC
        """)

        df = pd.read_sql(query, engine, params={'days': days})
        print(f"✅ Extracted {len(df)} trades from database")
        return df

    except Exception as e:
        print(f"❌ Database extraction failed: {e}")
        print("   Make sure database connection is configured in .env")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════
# METHOD 3: Synthetic Data (FOR TESTING)
# ══════════════════════════════════════════════════════════

def generate_synthetic_data(count: int = 500, win_rate: float = 0.55) -> pd.DataFrame:
    """
    Generate synthetic training data for testing.

    ⚠️  WARNING: This is for TESTING ONLY! Do NOT use for production.

    Generates random features with some correlations:
    - Higher score → Higher win probability
    - Fresh zones → Higher win probability
    - Trend alignment → Higher win probability

    Args:
        count: Number of trades to generate
        win_rate: Target win rate (0-1)

    Returns:
        DataFrame with synthetic features
    """
    print(f"🧪 Generating {count} synthetic trades (win_rate={win_rate:.1%})...")

    trades = []
    for _ in range(count):
        # Generate features
        score = random.randint(40, 100)
        freshness = random.choice([0, 1])
        session = random.randint(0, 3)
        atr_ratio = random.uniform(0.5, 3.0)
        is_accuracy = random.choice([0, 1])
        trend = random.choice([0, 1])
        rsi = random.uniform(30, 70)
        htf_trend = random.choice([0, 1])
        rvol = random.uniform(0.5, 2.0)
        adx = random.uniform(15, 50)
        touch_count = random.randint(1, 3)
        base_quality = random.randint(30, 90)
        departure_strength = random.randint(30, 90)
        liquidity_distance = random.uniform(5, 50)
        liquidity_spread = random.uniform(10, 100)
        return_strength = random.randint(30, 90)
        zone_type = random.choice([1, -1])
        entry_model = random.choice([1, 2, 3])

        # Determine outcome based on features (with some randomness)
        # Higher quality setups → Higher win probability
        base_win_prob = win_rate

        # Adjust based on features
        if score >= 80:
            base_win_prob += 0.15
        elif score >= 60:
            base_win_prob += 0.05

        if freshness == 1:
            base_win_prob += 0.10

        if trend == htf_trend:
            base_win_prob += 0.05

        if is_accuracy == 1:
            base_win_prob += 0.10

        # Cap at 0.95
        win_prob = min(base_win_prob, 0.95)

        # Random outcome
        outcome = 1 if random.random() < win_prob else 0

        trades.append({
            'outcome': outcome,
            'score': score,
            'freshness': freshness,
            'session': session,
            'atr_ratio': atr_ratio,
            'is_accuracy': is_accuracy,
            'trend': trend,
            'rsi': rsi,
            'htf_trend': htf_trend,
            'rvol': rvol,
            'adx': adx,
            'touch_count': touch_count,
            'base_quality': base_quality,
            'departure_strength': departure_strength,
            'liquidity_distance': liquidity_distance,
            'liquidity_spread': liquidity_spread,
            'return_strength': return_strength,
            'zone_type': zone_type,
            'entry_model': entry_model,
        })

    df = pd.DataFrame(trades)
    actual_wr = df['outcome'].mean()
    print(f"✅ Generated {len(df)} synthetic trades (actual win_rate={actual_wr:.1%})")
    print("⚠️  WARNING: This is SYNTHETIC data! Use real backtest data for production.")
    return df


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Collect AI training data')
    parser.add_argument(
        '--source',
        type=str,
        required=True,
        choices=['tradingview', 'database', 'synthetic'],
        help='Data source: tradingview, database, or synthetic'
    )
    parser.add_argument(
        '--input',
        type=str,
        help='Input CSV file (for tradingview source)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to extract (for database source)'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=500,
        help='Number of synthetic trades to generate'
    )
    parser.add_argument(
        '--win-rate',
        type=float,
        default=0.55,
        help='Target win rate for synthetic data (0-1)'
    )

    args = parser.parse_args()

    # Extract data based on source
    if args.source == 'tradingview':
        if not args.input:
            print("❌ Error: --input required for tradingview source")
            return
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ Error: File not found: {input_path}")
            return
        df = extract_from_tradingview(input_path)

    elif args.source == 'database':
        df = extract_from_database(days=args.days)

    elif args.source == 'synthetic':
        df = generate_synthetic_data(count=args.count, win_rate=args.win_rate)

    else:
        print(f"❌ Unknown source: {args.source}")
        return

    # Validate data
    if df.empty:
        print("❌ No data extracted!")
        return

    # Save to output file
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n✅ Training data saved to: {OUTPUT_PATH}")
    print(f"   Total samples: {len(df)}")
    print(f"   Wins: {df['outcome'].sum()} ({df['outcome'].mean():.1%})")
    print(f"   Losses: {len(df) - df['outcome'].sum()} ({(1 - df['outcome'].mean()):.1%})")

    print(f"\n📊 Next steps:")
    print(f"   1. Review data: head {OUTPUT_PATH}")
    print(f"   2. Train model: python ml/train_ai_guardian_v2_pro.py --data {OUTPUT_PATH}")
    print(f"   3. Deploy model: Update brain.py to use model_v2.pkl")


if __name__ == '__main__':
    main()
