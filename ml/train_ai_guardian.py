#!/usr/bin/env python3
"""
AI Guardian Multi-Asset Super-Model Training Script - v4.0
============================================================
Trains a unified ML model across multiple trading assets using
TradingView and Notion backtest data.

Input: backtest_data/ folder (recursive scan)
Output: ml/model.pkl, ml/encoders.pkl, accuracy leaderboard by asset
"""

import pandas as pd
import numpy as np
import pickle
import logging
import re
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Script directory for saving outputs
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

# Known forex/crypto/index tickers for symbol extraction
KNOWN_TICKERS = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD',
    'GBPJPY', 'EURJPY', 'AUDJPY', 'CHFJPY', 'CADJPY', 'NZDJPY',
    'EURGBP', 'EURAUD', 'EURCHF', 'EURCAD', 'EURNZD',
    'GBPAUD', 'GBPCAD', 'GBPCHF', 'GBPNZD',
    'AUDCAD', 'AUDCHF', 'AUDNZD',
    'CADCHF', 'NZDCAD', 'NZDCHF',
    'XAUUSD', 'XAGUSD', 'GOLD', 'SILVER',
    'BTCUSD', 'ETHUSD', 'BTCUSDT', 'ETHUSDT',
    'NAS100', 'SPX500', 'US30', 'DAX40', 'USTEC', 'US500',
]


# ============================================================================
# SMART DATA INGESTION
# ============================================================================

def find_all_csv_files(data_path: Path) -> list:
    """
    Recursively find all CSV files in the backtest_data folder.
    Excludes processed/derived files.
    """
    csv_files = []

    for filepath in data_path.rglob('*.csv'):
        # Skip processed folders and metadata files
        if 'processed' in str(filepath).lower():
            continue
        if '_metadata' in filepath.name.lower():
            continue

        csv_files.append(filepath)

    logger.info(f"Found {len(csv_files)} CSV files in {data_path}")
    return csv_files


def extract_symbol_from_path(filepath: Path) -> str:
    """
    Smart symbol extraction with priority:
    1. Check filename for known ticker (e.g., trades_EURUSD_... -> EURUSD)
    2. Check parent folder name (e.g., USDJPY/backtest.csv -> USDJPY)
    3. Fallback to UNKNOWN
    """
    filename = filepath.stem.upper()
    parent_folder = filepath.parent.name.upper()

    # Priority 1: Check filename for known ticker
    for ticker in KNOWN_TICKERS:
        if ticker in filename:
            return ticker

    # Priority 2: Check parent folder name
    for ticker in KNOWN_TICKERS:
        if ticker == parent_folder or ticker in parent_folder:
            return ticker

    # Try to find any 6-letter uppercase pattern that looks like forex
    forex_pattern = re.search(r'([A-Z]{6})', filename)
    if forex_pattern:
        potential_ticker = forex_pattern.group(1)
        # Validate it looks like a forex pair
        if potential_ticker[:3] in ['EUR', 'GBP', 'USD', 'AUD', 'NZD', 'CAD', 'CHF', 'JPY']:
            return potential_ticker

    # Fallback
    logger.warning(f"Could not extract symbol from: {filepath}, using UNKNOWN")
    return 'UNKNOWN'


def detect_csv_format(df: pd.DataFrame) -> str:
    """
    Detect whether the CSV is from TradingView or Notion.
    Returns: 'tradingview', 'notion', or 'unknown'
    """
    columns_lower = [c.lower() for c in df.columns]

    # TradingView indicators
    if 'net p&l %' in columns_lower or 'favorable excursion' in ' '.join(columns_lower):
        return 'tradingview'

    # Notion indicators
    if '+ r (%)' in columns_lower or 'entry model' in columns_lower or 'zone type' in columns_lower:
        return 'notion'

    # Check for common Notion columns
    notion_cols = ['entry type', 'trade score', 'session', 'entry method']
    if sum(1 for c in notion_cols if c in columns_lower) >= 2:
        return 'notion'

    return 'unknown'


def standardize_tradingview(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Standardize TradingView export columns to unified format.
    Target columns: ['symbol', 'type', 'signal', 'close_time', 'profit_pct']
    """
    standardized = pd.DataFrame(index=df.index)
    standardized['symbol'] = symbol  # Broadcasts to all rows

    # Type column (Entry long/short, Exit long/short)
    if 'Type' in df.columns:
        standardized['type'] = df['Type'].astype(str).str.lower()
    else:
        standardized['type'] = 'unknown'

    # Signal column
    if 'Signal' in df.columns:
        standardized['signal'] = df['Signal'].astype(str)
    else:
        standardized['signal'] = ''

    # Close time (Date and time column)
    datetime_col = None
    for col in ['Date and time', 'Date/Time', 'DateTime']:
        if col in df.columns:
            datetime_col = col
            break

    if datetime_col:
        standardized['close_time'] = pd.to_datetime(df[datetime_col], errors='coerce')
    else:
        standardized['close_time'] = pd.NaT

    # Profit percentage
    profit_col = None
    for col in ['Net P&L %', 'Profit %', 'P&L %']:
        if col in df.columns:
            profit_col = col
            break

    if profit_col:
        profit_str = df[profit_col].astype(str).str.replace(r'[%$,\s]', '', regex=True)
        standardized['profit_pct'] = pd.to_numeric(profit_str, errors='coerce')
    else:
        standardized['profit_pct'] = np.nan

    # Keep additional useful columns
    if 'Favorable excursion %' in df.columns:
        runup_str = df['Favorable excursion %'].astype(str).str.replace(r'[%$,\s]', '', regex=True)
        standardized['runup_pct'] = pd.to_numeric(runup_str, errors='coerce')

    if 'Adverse excursion %' in df.columns:
        drawdown_str = df['Adverse excursion %'].astype(str).str.replace(r'[%$,\s]', '', regex=True)
        standardized['drawdown_pct'] = pd.to_numeric(drawdown_str, errors='coerce').abs()

    # Source tracking
    standardized['_source'] = 'tradingview'

    return standardized


def standardize_notion(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Standardize Notion export columns to unified format.
    Target columns: ['symbol', 'type', 'signal', 'close_time', 'profit_pct']
    """
    standardized = pd.DataFrame(index=df.index)
    standardized['symbol'] = symbol  # Broadcasts to all rows

    # Type - from Entry Type or Zone Type
    if 'Entry Type' in df.columns:
        standardized['type'] = df['Entry Type'].astype(str).str.lower()
    elif 'Zone Type' in df.columns:
        standardized['type'] = df['Zone Type'].astype(str).str.lower()
    else:
        standardized['type'] = 'unknown'

    # Signal - combine Entry model + Entry method
    signal_parts = []
    if 'Entry model' in df.columns:
        signal_parts.append(df['Entry model'].astype(str))
    if 'Entry method' in df.columns:
        signal_parts.append(df['Entry method'].astype(str))

    if signal_parts:
        standardized['signal'] = signal_parts[0] if len(signal_parts) == 1 else \
                                 signal_parts[0] + ' | ' + signal_parts[1]
    else:
        standardized['signal'] = ''

    # Close time
    close_col = None
    for col in ['Close', 'close', 'Exit Time', 'Exit']:
        if col in df.columns:
            close_col = col
            break

    if close_col:
        standardized['close_time'] = pd.to_datetime(df[close_col], errors='coerce')
    else:
        standardized['close_time'] = pd.NaT

    # Profit percentage - from "+ R (%)" column
    profit_col = None
    for col in ['+ R (%)', '+R (%)', 'R%', 'Profit %', 'Net Profit']:
        if col in df.columns:
            profit_col = col
            break

    if profit_col:
        profit_str = df[profit_col].astype(str).str.replace(r'[%$,\s]', '', regex=True)
        standardized['profit_pct'] = pd.to_numeric(profit_str, errors='coerce')
    else:
        # Try to determine from Win/Loss columns
        standardized['profit_pct'] = np.nan
        if 'Win' in df.columns and 'Loss' in df.columns:
            win_mask = df['Win'].notna() & (df['Win'].astype(str).str.strip() != '')
            loss_mask = df['Loss'].notna() & (df['Loss'].astype(str).str.strip() != '')
            standardized.loc[win_mask, 'profit_pct'] = 1.0  # Default win value
            standardized.loc[loss_mask, 'profit_pct'] = -1.0  # Default loss value

    # Additional Notion features
    if 'Session' in df.columns:
        standardized['session'] = df['Session'].astype(str)

    if 'Trade Score' in df.columns:
        standardized['trade_score'] = df['Trade Score'].astype(str)

    if 'Day' in df.columns:
        standardized['day'] = df['Day'].astype(str)

    if 'Liquidity Distance' in df.columns:
        standardized['liq_distance'] = pd.to_numeric(df['Liquidity Distance'], errors='coerce')

    # Source tracking
    standardized['_source'] = 'notion'

    return standardized


def load_and_standardize_all(csv_files: list) -> pd.DataFrame:
    """
    Load all CSV files, detect format, and standardize columns.
    """
    all_data = []

    for filepath in csv_files:
        try:
            # Read with BOM handling
            df = pd.read_csv(filepath, encoding='utf-8-sig')

            if df.empty or len(df) < 1:
                logger.warning(f"Skipping empty file: {filepath.name}")
                continue

            # Extract symbol
            symbol = extract_symbol_from_path(filepath)

            # Detect format and standardize
            csv_format = detect_csv_format(df)

            if csv_format == 'tradingview':
                standardized = standardize_tradingview(df, symbol)
            elif csv_format == 'notion':
                standardized = standardize_notion(df, symbol)
            else:
                logger.warning(f"Unknown format for {filepath.name}, attempting TradingView parsing")
                standardized = standardize_tradingview(df, symbol)

            standardized['_file'] = filepath.name
            all_data.append(standardized)

            logger.info(f"  ✓ {filepath.name}: {len(standardized)} rows, symbol={symbol}, format={csv_format}")

        except Exception as e:
            logger.error(f"  ✗ Failed to load {filepath.name}: {e}")

    if not all_data:
        raise ValueError("No valid CSV files could be loaded")

    combined = pd.concat(all_data, ignore_index=True)
    logger.info(f"\nTotal rows loaded: {len(combined)}")
    logger.info(f"Symbols found: {combined['symbol'].unique().tolist()}")

    return combined


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def engineer_features(df: pd.DataFrame) -> tuple:
    """
    Feature Engineering for Multi-Asset Super-Model.

    Creates:
    - is_win (target): 1 if profit > 0, else 0
    - asset_id: LabelEncoded symbol
    - hour: Hour of close (0-23)
    - day_of_week: Day (0=Monday, 6=Sunday)
    - type_encoded: Trade type encoded
    - signal_encoded: Signal type encoded
    """
    features = pd.DataFrame()
    encoders = {}

    # Filter out rows with invalid profit
    valid_mask = df['profit_pct'].notna()
    df_valid = df[valid_mask].copy()

    logger.info(f"Valid rows with profit data: {len(df_valid)}")

    if len(df_valid) < 50:
        raise ValueError(f"Not enough valid samples ({len(df_valid)}). Need at least 50.")

    # === TARGET: is_win ===
    features['is_win'] = (df_valid['profit_pct'] > 0).astype(int)

    # === FEATURE: Asset ID (LabelEncoded symbol) ===
    symbol_encoder = LabelEncoder()
    features['asset_id'] = symbol_encoder.fit_transform(df_valid['symbol'])
    encoders['symbol'] = symbol_encoder
    logger.info(f"Assets encoded: {dict(zip(symbol_encoder.classes_, range(len(symbol_encoder.classes_))))}")

    # === FEATURE: Hour and DayOfWeek ===
    close_time = df_valid['close_time']
    features['hour'] = close_time.dt.hour.fillna(12).astype(int)
    features['day_of_week'] = close_time.dt.dayofweek.fillna(2).astype(int)

    # === FEATURE: Type (Long/Short/Flip/Default) ===
    type_values = df_valid['type'].fillna('unknown').astype(str)
    type_encoder = LabelEncoder()
    features['type_encoded'] = type_encoder.fit_transform(type_values)
    encoders['type'] = type_encoder

    # === FEATURE: Signal (Label Encoded) ===
    signal_values = df_valid['signal'].fillna('unknown').astype(str)
    # Clean up signals - take first part before pipe or comma
    signal_clean = signal_values.apply(lambda x: x.split('|')[0].split(',')[0].strip()[:50])
    signal_encoder = LabelEncoder()
    features['signal_encoded'] = signal_encoder.fit_transform(signal_clean)
    encoders['signal'] = signal_encoder

    # === OPTIONAL FEATURES: Session, Trade Score ===
    if 'session' in df_valid.columns:
        session_values = df_valid['session'].fillna('unknown').astype(str)
        session_encoder = LabelEncoder()
        features['session_encoded'] = session_encoder.fit_transform(session_values)
        encoders['session'] = session_encoder

    if 'liq_distance' in df_valid.columns:
        features['liq_distance'] = df_valid['liq_distance'].fillna(50).astype(float)

    # === FEATURE: Source (TradingView vs Notion) ===
    source_values = df_valid['_source'].fillna('unknown')
    source_encoder = LabelEncoder()
    features['source_encoded'] = source_encoder.fit_transform(source_values)
    encoders['source'] = source_encoder

    # === FEATURE: Runup and Drawdown (if available) ===
    if 'runup_pct' in df_valid.columns:
        features['runup_pct'] = df_valid['runup_pct'].fillna(0)

    if 'drawdown_pct' in df_valid.columns:
        features['drawdown_pct'] = df_valid['drawdown_pct'].fillna(0)

    # Keep symbol for per-asset accuracy calculation
    features['_symbol'] = df_valid['symbol'].values

    logger.info(f"Features created: {[c for c in features.columns if not c.startswith('_')]}")

    return features, encoders


# ============================================================================
# TRAINING
# ============================================================================

def train_super_model(features: pd.DataFrame, encoders: dict) -> tuple:
    """
    Train a single RandomForestClassifier on the combined multi-asset dataset.
    """
    # Separate target, features, and metadata
    y = features['is_win']
    symbols = features['_symbol']
    X = features.drop(columns=['is_win', '_symbol'])

    feature_names = X.columns.tolist()
    logger.info(f"\nTraining with {len(feature_names)} features: {feature_names}")

    # Split: 80% Train / 20% Test (stratified by target)
    X_train, X_test, y_train, y_test, sym_train, sym_test = train_test_split(
        X, y, symbols, test_size=0.2, stratify=y, random_state=42
    )

    logger.info(f"Train: {len(X_train)} samples | Test: {len(X_test)} samples")
    logger.info(f"Class distribution - Train: {y_train.value_counts().to_dict()}")

    # Train RandomForestClassifier
    logger.info("\n🌲 Training RandomForestClassifier...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # === OVERALL EVALUATION ===
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print("\n" + "=" * 60)
    print(f"📊 OVERALL MODEL ACCURACY: {accuracy:.1%}")
    print("=" * 60)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Loss (0)', 'Win (1)']))

    # === ACCURACY BY ASSET LEADERBOARD ===
    print("\n" + "=" * 60)
    print("🏆 ACCURACY LEADERBOARD BY ASSET")
    print("=" * 60)

    asset_results = []
    for symbol in sorted(sym_test.unique()):
        mask = sym_test == symbol
        if mask.sum() < 5:  # Skip assets with too few test samples
            continue

        sym_y_test = y_test[mask]
        sym_y_pred = y_pred[mask]
        sym_accuracy = accuracy_score(sym_y_test, sym_y_pred)
        win_rate = sym_y_test.mean()

        asset_results.append({
            'symbol': symbol,
            'accuracy': sym_accuracy,
            'samples': mask.sum(),
            'win_rate': win_rate
        })

    # Sort by accuracy descending
    asset_results = sorted(asset_results, key=lambda x: x['accuracy'], reverse=True)

    # Print leaderboard
    print(f"\n{'Rank':<6}{'Asset':<12}{'Accuracy':<12}{'Samples':<10}{'Win Rate':<10}")
    print("-" * 50)
    for i, result in enumerate(asset_results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{medal} {i:<4}{result['symbol']:<12}{result['accuracy']:.1%}       "
              f"{result['samples']:<10}{result['win_rate']:.1%}")

    # === FEATURE IMPORTANCE ===
    print("\n" + "=" * 60)
    print("📈 FEATURE IMPORTANCE")
    print("=" * 60)
    importances = sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    )
    for name, imp in importances:
        bar = "█" * int(imp * 50)
        print(f"  {name:<20} {imp:.3f} {bar}")

    # === CONFUSION MATRIX ===
    cm = confusion_matrix(y_test, y_pred)
    print("\n" + "=" * 60)
    print("📉 CONFUSION MATRIX")
    print("=" * 60)
    print(f"\n              Predicted")
    print(f"              Loss    Win")
    print(f"Actual Loss   {cm[0][0]:<8}{cm[0][1]}")
    print(f"Actual Win    {cm[1][0]:<8}{cm[1][1]}")

    # Store feature names and asset results with model
    model.feature_names_ = feature_names
    model.asset_leaderboard_ = asset_results

    return model, encoders


# ============================================================================
# SAVE ARTIFACTS
# ============================================================================

def save_artifacts(model, encoders: dict):
    """
    Save model and encoders to ml/ directory.
    """
    model_path = SCRIPT_DIR / 'model.pkl'
    encoders_path = SCRIPT_DIR / 'encoders.pkl'

    # Save model
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n✅ Model saved to: {model_path}")

    # Save encoders (essential for the Worker to decode symbols)
    with open(encoders_path, 'wb') as f:
        pickle.dump(encoders, f)
    print(f"✅ Encoders saved to: {encoders_path}")

    # Save metadata (convert numpy types to native Python types)
    asset_leaderboard_clean = [
        {
            'symbol': r['symbol'],
            'accuracy': float(r['accuracy']),
            'samples': int(r['samples']),
            'win_rate': float(r['win_rate'])
        }
        for r in model.asset_leaderboard_
    ]

    metadata = {
        'trained_at': datetime.now().isoformat(),
        'version': '4.0',
        'feature_names': model.feature_names_,
        'n_estimators': model.n_estimators,
        'max_depth': model.max_depth,
        'asset_leaderboard': asset_leaderboard_clean,
        'encoder_classes': {
            k: v.classes_.tolist()
            for k, v in encoders.items()
            if hasattr(v, 'classes_')
        }
    }

    metadata_path = SCRIPT_DIR / 'model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Metadata saved to: {metadata_path}")


# ============================================================================
# MAIN
# ============================================================================

def main(data_path: str = None):
    """
    Main training pipeline for Multi-Asset Super-Model.
    """
    print("\n" + "=" * 60)
    print("🧠 AI GUARDIAN MULTI-ASSET SUPER-MODEL TRAINING v4.0")
    print("=" * 60)

    # 1. Determine data path
    if data_path:
        backtest_dir = Path(data_path)
    else:
        # Default: backend/backtest_data
        backtest_dir = PROJECT_ROOT / 'backend' / 'backtest_data'

    if not backtest_dir.exists():
        logger.error(f"Data directory not found: {backtest_dir}")
        sys.exit(1)

    logger.info(f"\n📂 Scanning: {backtest_dir}")

    # 2. Find all CSV files
    csv_files = find_all_csv_files(backtest_dir)

    if not csv_files:
        logger.error("No CSV files found!")
        sys.exit(1)

    # 3. Load and standardize all data
    print("\n" + "-" * 60)
    print("📥 LOADING AND STANDARDIZING DATA")
    print("-" * 60)
    df = load_and_standardize_all(csv_files)

    # 4. Feature engineering
    print("\n" + "-" * 60)
    print("⚙️  FEATURE ENGINEERING")
    print("-" * 60)
    features, encoders = engineer_features(df)

    # 5. Train the Super-Model
    print("\n" + "-" * 60)
    print("🚀 TRAINING SUPER-MODEL")
    print("-" * 60)
    model, encoders = train_super_model(features, encoders)

    # 6. Save artifacts
    save_artifacts(model, encoders)

    print("\n" + "=" * 60)
    print("🎉 TRAINING COMPLETE! The AI Guardian Brain is ready.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Train AI Guardian Multi-Asset Super-Model'
    )
    parser.add_argument(
        '--data', '-d',
        type=str,
        default=None,
        help='Path to backtest_data directory (default: backend/backtest_data)'
    )

    args = parser.parse_args()
    main(args.data)
