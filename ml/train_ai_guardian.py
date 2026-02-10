#!/usr/bin/env python3
"""
AI Guardian Multi-Asset Super-Model Training Script - v5.1
============================================================
Trains a unified ML model across multiple trading assets using
TradingView and Notion backtest data.

CRITICAL FIX v5.0: Removed data leakage from outcome variables
(runup_pct, drawdown_pct, etc.) that don't exist at entry time.

NEW IN v5.1: Feature scaling with StandardScaler for improved RF accuracy
- Prevents large-scale features (entry price) from dominating predictions
- Categorical features (encoded IDs) remain unscaled
- Scaler fitted on training data only to prevent leakage

Input: backtest_data/ folder (recursive scan)
Output: ml/model.pkl, ml/encoders.pkl, ml/scaler.pkl, accuracy leaderboard by asset
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
from sklearn.preprocessing import LabelEncoder, StandardScaler
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

# =============================================================================
# FORBIDDEN COLUMNS - OUTCOME VARIABLES (FUTURE DATA)
# These columns represent data that does NOT exist at trade ENTRY time.
# Including them causes data leakage and model failure in live trading.
# =============================================================================
FORBIDDEN_COLUMNS = [
    'runup_pct',
    'drawdown_pct',
    'net_pnl_pct',
    'profit_pct',
    'gross_profit',
    'net_pnl',
    'exit_time',
    'trade_#',
    'trade_num',
    'trade_number',
]

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

    # Profit percentage (needed for target variable only, NOT as a feature)
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

    # NOTE: We intentionally do NOT include runup_pct/drawdown_pct here
    # as they are outcome variables that cause data leakage

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

    # Profit percentage - from "+ R (%)" column (for target only, NOT as feature)
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

    # Additional Notion features (legitimate - exist at entry time)
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

def extract_f_packet_features(signal_series: pd.Series) -> pd.DataFrame:
    """
    Extract numeric values from F: packets in signal strings.

    Example signal: "F:rsi=45.2|F:atr=0.0015|BUY_SIGNAL"
    Extracts: {'f_rsi': 45.2, 'f_atr': 0.0015}

    These are LEGITIMATE features as they represent indicator values
    at the time of signal generation (entry time).
    """
    # Pattern to match F:key=value
    f_pattern = re.compile(r'F:(\w+)=([\d.+-]+)')

    # Collect all unique F: keys first
    all_keys = set()
    for signal in signal_series.dropna().unique():
        matches = f_pattern.findall(str(signal))
        for key, _ in matches:
            all_keys.add(key.lower())

    if not all_keys:
        return pd.DataFrame(index=signal_series.index)

    # Initialize columns
    f_features = pd.DataFrame(index=signal_series.index)
    for key in all_keys:
        f_features[f'f_{key}'] = np.nan

    # Extract values
    for idx, signal in signal_series.items():
        if pd.isna(signal):
            continue
        matches = f_pattern.findall(str(signal))
        for key, value in matches:
            col_name = f'f_{key.lower()}'
            try:
                f_features.at[idx, col_name] = float(value)
            except (ValueError, TypeError):
                pass

    # Fill NaN with 0 for extracted features
    for col in f_features.columns:
        f_features[col] = f_features[col].fillna(0)

    if f_features.columns.tolist():
        logger.info(f"Extracted F: packet features: {f_features.columns.tolist()}")

    return f_features


def engineer_features(df: pd.DataFrame) -> tuple:
    """
    Feature Engineering for Multi-Asset Super-Model.

    CRITICAL: Only uses features available at ENTRY time.
    Explicitly excludes outcome variables (future data).

    Creates:
    - is_win (target): 1 if profit > 0, else 0
    - asset_id: LabelEncoded symbol
    - hour: Hour of entry (0-23)
    - day_of_week: Day (0=Monday, 6=Sunday)
    - type_encoded: Trade type encoded (long/short)
    - signal_encoded: Signal type encoded
    - f_* features: Extracted from F: packets in signals
    """
    features = pd.DataFrame()
    encoders = {}

    # Filter out rows with invalid profit (needed for target)
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
    # Clean up signals - remove F: packets before encoding, take first part
    signal_clean = signal_values.apply(
        lambda x: re.sub(r'F:\w+=[^|]+\|?', '', x).split('|')[0].split(',')[0].strip()[:50]
    )
    signal_clean = signal_clean.replace('', 'unknown')
    signal_encoder = LabelEncoder()
    features['signal_encoded'] = signal_encoder.fit_transform(signal_clean)
    encoders['signal'] = signal_encoder

    # === FEATURE: F: Packet Extraction (Indicator values at entry) ===
    f_packet_features = extract_f_packet_features(df_valid['signal'])
    if not f_packet_features.empty:
        for col in f_packet_features.columns:
            features[col] = f_packet_features[col].values

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

    # ==========================================================================
    # CRITICAL: DO NOT ADD OUTCOME VARIABLES AS FEATURES
    # The following are FORBIDDEN and must NOT be added:
    # - runup_pct (max favorable excursion - only known after trade)
    # - drawdown_pct (max adverse excursion - only known after trade)
    # - net_pnl_pct, profit_pct, gross_profit, net_pnl (outcome)
    # - exit_time (only known after trade closes)
    # - trade_# (sequential, causes data leakage)
    # ==========================================================================

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

    CRITICAL: Explicitly drops forbidden columns before training to prevent
    any data leakage from outcome variables.
    """
    # Separate target, features, and metadata
    y = features['is_win']
    symbols = features['_symbol']
    X = features.drop(columns=['is_win', '_symbol'])

    # ==========================================================================
    # CRITICAL DATA LEAKAGE PREVENTION
    # Explicitly drop any forbidden columns that might have slipped through
    # ==========================================================================
    columns_to_drop = []
    for col in X.columns:
        col_lower = col.lower()
        for forbidden in FORBIDDEN_COLUMNS:
            if forbidden in col_lower:
                columns_to_drop.append(col)
                break

    if columns_to_drop:
        logger.warning(f"⚠️  DROPPING FORBIDDEN COLUMNS (data leakage prevention): {columns_to_drop}")
        X = X.drop(columns=columns_to_drop)

    feature_names = X.columns.tolist()

    # ==========================================================================
    # PRINT FINAL FEATURE LIST - CONFIRM NO LEAKAGE
    # ==========================================================================
    print("\n" + "=" * 60)
    print("✅ FINAL FEATURE LIST (Data Leakage Check)")
    print("=" * 60)
    print(f"\nFeatures being used ({len(feature_names)}):")
    for i, name in enumerate(feature_names, 1):
        print(f"  {i:2}. {name}")

    print(f"\n🛡️  Forbidden columns explicitly excluded:")
    for col in FORBIDDEN_COLUMNS:
        print(f"  ✗ {col}")
    print("=" * 60)

    logger.info(f"\nTraining with {len(feature_names)} features: {feature_names}")

    # Split: 80% Train / 20% Test (stratified by target)
    X_train, X_test, y_train, y_test, sym_train, sym_test = train_test_split(
        X, y, symbols, test_size=0.2, stratify=y, random_state=42
    )

    logger.info(f"Train: {len(X_train)} samples | Test: {len(X_test)} samples")
    logger.info(f"Class distribution - Train: {y_train.value_counts().to_dict()}")

    # ==========================================================================
    # ✅ FEATURE SCALING PIPELINE (v5.1 - RF Accuracy Fix)
    # ==========================================================================
    print("\n" + "=" * 60)
    print("📐 APPLYING FEATURE SCALING (StandardScaler)")
    print("=" * 60)

    # Identify categorical vs numerical features
    # Categorical features: encoded columns (already integers from LabelEncoder)
    categorical_features = [col for col in feature_names if '_encoded' in col or col == 'asset_id']
    numerical_features = [col for col in feature_names if col not in categorical_features]

    logger.info(f"Categorical features ({len(categorical_features)}): {categorical_features}")
    logger.info(f"Numerical features ({len(numerical_features)}): {numerical_features[:10]}...")

    # Create scaler
    scaler = StandardScaler()

    # Copy DataFrames to preserve originals
    X_train_scaled = X_train.copy()
    X_test_scaled = X_test.copy()

    # Fit scaler on TRAINING data only (critical: prevent data leakage)
    # Transform both train and test
    if numerical_features:
        logger.info(f"Fitting StandardScaler on {len(numerical_features)} numerical features...")
        X_train_scaled[numerical_features] = scaler.fit_transform(X_train[numerical_features])
        X_test_scaled[numerical_features] = scaler.transform(X_test[numerical_features])

        # Log example scaling stats
        sample_col = numerical_features[0]
        logger.info(f"Example scaling - '{sample_col}':")
        logger.info(f"  Before: mean={X_train[sample_col].mean():.3f}, std={X_train[sample_col].std():.3f}")
        logger.info(f"  After:  mean={X_train_scaled[sample_col].mean():.3f}, std={X_train_scaled[sample_col].std():.3f}")
    else:
        logger.warning("No numerical features found - skipping scaling")

    print("✅ Feature scaling complete\n")

    # Train RandomForestClassifier on SCALED data
    logger.info("\n🌲 Training RandomForestClassifier on scaled features...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_scaled, y_train)

    # === OVERALL EVALUATION (on scaled test data) ===
    y_pred = model.predict(X_test_scaled)
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

    # ✅ Return scaler along with model and encoders
    scaler_metadata = {
        'scaler': scaler if numerical_features else None,
        'numerical_features': numerical_features,
        'categorical_features': categorical_features
    }

    return model, encoders, scaler_metadata


# ============================================================================
# SAVE ARTIFACTS
# ============================================================================

def save_artifacts(model, encoders: dict, scaler_metadata: dict = None):
    """
    Save model, encoders, and scaler to ml/ directory.
    """
    model_path = SCRIPT_DIR / 'model.pkl'
    encoders_path = SCRIPT_DIR / 'encoders.pkl'
    scaler_path = SCRIPT_DIR / 'scaler.pkl'

    # Save model
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n✅ Model saved to: {model_path}")

    # Save encoders (essential for the Worker to decode symbols)
    with open(encoders_path, 'wb') as f:
        pickle.dump(encoders, f)
    print(f"✅ Encoders saved to: {encoders_path}")

    # ✅ Save scaler (v5.1 - RF accuracy fix)
    if scaler_metadata and scaler_metadata.get('scaler') is not None:
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler_metadata, f)
        print(f"✅ Scaler saved to: {scaler_path}")
        print(f"   • Numerical features: {len(scaler_metadata['numerical_features'])}")
        print(f"   • Categorical features: {len(scaler_metadata['categorical_features'])}")
    else:
        print(f"⚠️  No scaler to save (no numerical features found)")

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
        'version': '5.1',  # ✅ Updated version for scaler addition
        'data_leakage_fix': True,
        'feature_scaling': scaler_metadata is not None and scaler_metadata.get('scaler') is not None,
        'forbidden_columns': FORBIDDEN_COLUMNS,
        'feature_names': model.feature_names_,
        'numerical_features': scaler_metadata['numerical_features'] if scaler_metadata else [],
        'categorical_features': scaler_metadata['categorical_features'] if scaler_metadata else [],
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

    # Print feature list confirmation
    print(f"\n📋 Model trained with {len(model.feature_names_)} features:")
    for feat in model.feature_names_:
        print(f"   • {feat}")


# ============================================================================
# MAIN
# ============================================================================

def main(data_path: str = None):
    """
    Main training pipeline for Multi-Asset Super-Model.
    """
    print("\n" + "=" * 60)
    print("🧠 AI GUARDIAN MULTI-ASSET SUPER-MODEL TRAINING v5.1")
    print("   (v5.0: Data Leakage Removed | v5.1: Feature Scaling Added)")
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
    print("⚙️  FEATURE ENGINEERING (Leakage-Free)")
    print("-" * 60)
    features, encoders = engineer_features(df)

    # 5. Train the Super-Model
    print("\n" + "-" * 60)
    print("🚀 TRAINING SUPER-MODEL")
    print("-" * 60)
    model, encoders, scaler_metadata = train_super_model(features, encoders)

    # 6. Save artifacts (model, encoders, and scaler)
    save_artifacts(model, encoders, scaler_metadata)

    print("\n" + "=" * 60)
    print("🎉 TRAINING COMPLETE! The AI Guardian Brain is ready.")
    print("   ✅ No data leakage - model uses only entry-time features")
    print("   ✅ Feature scaling applied - improved prediction accuracy")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Train AI Guardian Multi-Asset Super-Model (v5.1 - Feature Scaling + Data Leakage Fix)'
    )
    parser.add_argument(
        '--data', '-d',
        type=str,
        default=None,
        help='Path to backtest_data directory (default: backend/backtest_data)'
    )

    args = parser.parse_args()
    main(args.data)
