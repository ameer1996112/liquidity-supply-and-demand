
import pandas as pd
import numpy as np
import pickle
import logging
import glob
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from imblearn.over_sampling import SMOTE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_model(csv_pattern='trade*.csv', model_path='model.pkl'):
    logging.info(f"Searching for data files matching: {csv_pattern}...")
    
    files = glob.glob(csv_pattern)
    if not files:
        logging.error(f"No files found matching '{csv_pattern}'. Please export 'List of Trades' from TradingView (e.g., 'trades_XAUUSD.csv').")
        return
    
    logging.info(f"Found {len(files)} files: {[os.path.basename(f) for f in files]}")
    
    dfs = []
    for f in files:
        try:
            curr_df = pd.read_csv(f)
            dfs.append(curr_df)
        except Exception as e:
            logging.error(f"Failed to read {f}: {e}")
            
    if not dfs:
        logging.error("No valid CSV files loaded.")
        return

    df = pd.concat(dfs, ignore_index=True)
    logging.info(f"Combined {len(df)} total rows.")

    # 1. Cleaning & Feature Extraction
    logging.info("Preprocessing data...")
    
    # Filter only rows with our AI Feature packet
    # Format: "Type | F:{Score},{LegCandles},{Freshness},{LiqSwept},{Trend},{RSI}"
    # Determine which column contains the AI feature packet
    if 'Signal' in df.columns:
        target_col = 'Signal'
    elif 'Comment' in df.columns:
        target_col = 'Comment'
    else:
        logging.error("CSV must contain either 'Signal' or 'Comment' column.")
        return
    # Determine profit column name
    if 'Net P&L USD' in df.columns:
        profit_col = 'Net P&L USD'
    elif 'Profit' in df.columns:
        profit_col = 'Profit'
    else:
        logging.error("CSV must contain a profit column (e.g., 'Net P&L USD' or 'Profit').")
        return
        logging.error("CSV missing 'Comment' column. Ensure you exported the 'List of Trades'.")
        return

    # Extract features using regex or split
    # V3 format: "F:Score,Freshness,Session,ZoneType,ATR_Ratio,isAccuracy,Trend,RSI,HTF_Trend,RVOL" (10 features)
    # V2 format: "... | F:Score,Freshness,Session,ZoneType,ATR_Ratio,isAccuracy,Trend,RSI" (8 features)
    # V1 format: "... | F:Score,LegCandles,Freshness,LiqSwept,Trend,RSI" (6 features)
    feature_data = []
    
    # V7.1 headers (17 features - LiquidityQuality split into Distance + Spread)
    headers_v7_1 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI', 'HTF_Trend', 'RVOL', 'ADX', 'TouchCount', 'BaseQuality', 'DepartureStrength', 'LiquidityDistance', 'LiquiditySpread', 'ReturnStrength']
    # V7 headers (16 features including Liquidity Quality and Return Strength)
    headers_v7 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI', 'HTF_Trend', 'RVOL', 'ADX', 'TouchCount', 'BaseQuality', 'DepartureStrength', 'LiquidityQuality', 'ReturnStrength']
    # V6 headers (14 features including Base Quality and Departure Strength)
    headers_v6 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI', 'HTF_Trend', 'RVOL', 'ADX', 'TouchCount', 'BaseQuality', 'DepartureStrength']
    # V5 headers (12 features including TouchCount)
    headers_v5 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI', 'HTF_Trend', 'RVOL', 'ADX', 'TouchCount']
    # V4 headers (11 features including ADX)
    headers_v4 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI', 'HTF_Trend', 'RVOL', 'ADX']
    # New V3 headers (10 features)
    headers_v3 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI', 'HTF_Trend', 'RVOL']
    # V2 headers (8 features)
    headers_v2 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI']
    # Old V1 headers (6 features)
    headers_v1 = ['Score', 'LegCandles', 'Freshness', 'LiqSwept', 'Trend', 'RSI']
    
    all_parsed_rows = []
    
    for index, row in df.iterrows():
        comment = str(row.get(target_col, ''))
        if 'F:' in comment:
            try:
                # Split by "F:" and take the part after it
                clean_part = comment.split('F:')[1].strip()
                # Split variables by comma
                vars = clean_part.split(',')
                
                feature_count = len(vars)
                
                if feature_count in [6, 8, 10, 11, 12, 14, 16, 17]:
                    features = [float(v) for v in vars]
                    
                    # Target: Profit > 0 = 1 (Win), else 0 (Loss)
                    profit = float(str(row.get(profit_col, '0')).replace(',' ,'').replace('$', '').replace(' ', ''))
                    target = 1 if profit > 0 else 0
                    
                    features.append(target)
                    all_parsed_rows.append((feature_count, features))
            except Exception as e:
                pass # Skip malformed rows

    if not all_parsed_rows:
        logging.error("No valid training samples found.")
        return

    # Determine best version (highest feature count)
    versions_found = {row[0] for row in all_parsed_rows}
    # Prioritize V7.1 if available
    best_version = max(versions_found)
    logging.info(f"Versions found in data: {versions_found}. Selected training version: {best_version} features.")

    # Filter data to match best version
    feature_data = [row[1] for row in all_parsed_rows if row[0] == best_version]
    valid_count = len(feature_data)

    # Set headers based on best version
    if best_version == 17:
        headers = headers_v7_1
        detected_version = 'v7.1'
    elif best_version == 16:
        headers = headers_v7
        detected_version = 'v7'
    elif best_version == 14:
        headers = headers_v6
        detected_version = 'v6'
    elif best_version == 12:
        headers = headers_v5
        detected_version = 'v5'
    elif best_version == 11:
        headers = headers_v4
        detected_version = 'v4'
    elif best_version == 10: 
        headers = headers_v3
        detected_version = 'v3'
    elif best_version == 8: 
        headers = headers_v2
        detected_version = 'v2'
    else: 
        headers = headers_v1
        detected_version = 'v1'
    
    logging.info(f"training with {valid_count} samples ({detected_version.upper()}).")

    if valid_count < 10:
        logging.error("Not enough data to train. Need at least 10 samples.")
        return

    # Create DataFrame
    cols = headers + ['Target']
    data = pd.DataFrame(feature_data, columns=cols)
    
    # 2. Train / Test Split
    X = data[headers]
    y = data['Target']
    
    # Split 80% Train, 20% Test
    # Stratified split to preserve class distribution
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    # Apply SMOTE to balance the training set
    smote = SMOTE(random_state=42)
    X_train, y_train = smote.fit_resample(X_train, y_train)
    
    # 3. Model Training
    logging.info("Training Random Forest Classifier...")
    # Use class weighting to handle imbalance
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        class_weight='balanced',
        random_state=42,
    )
    model.fit(X_train, y_train)
    
    # 4. Evaluation
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logging.info(f"Model Accuracy (Test Set): {acc:.2%}")
    logging.info("\n" + classification_report(y_test, y_pred))
    
    # Feature Importance
    importances = model.feature_importances_
    logging.info("Feature Importance:")
    for name, imp in zip(headers, importances):
        logging.info(f"  {name}: {imp:.4f}")

    # 5. Save Model
    logging.info(f"Saving model to {model_path}...")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
        
    logging.info("✅ Training Complete. The 'Brain' is ready.")

if __name__ == "__main__":
    train_model()
