
import pandas as pd
import numpy as np
import pickle
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from imblearn.over_sampling import SMOTE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_model(csv_path='trades_XAUUSD_1_1_2024_19_1_2026.csv', model_path='model.pkl'):
    logging.info(f"Loading data from {csv_path}...")
    
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        logging.error(f"File {csv_path} not found. Please export 'List of Trades' from TradingView and save it as '{csv_path}'.")
        return

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
    # V2 format: "... | F:Score,Freshness,Session,ZoneType,ATR_Ratio,isAccuracy,Trend,RSI"
    # V1 format: "... | F:Score,LegCandles,Freshness,LiqSwept,Trend,RSI" (6 features)
    feature_data = []
    
    # New V2 headers (8 features)
    headers_v2 = ['Score', 'Freshness', 'Session', 'ZoneType', 'ATR_Ratio', 'isAccuracy', 'Trend', 'RSI']
    # Old V1 headers (6 features)
    headers_v1 = ['Score', 'LegCandles', 'Freshness', 'LiqSwept', 'Trend', 'RSI']
    
    valid_count = 0
    detected_version = None
    
    for index, row in df.iterrows():
        comment = str(row.get(target_col, ''))
        if 'F:' in comment:
            try:
                # Split by "F:" and take the part after it
                clean_part = comment.split('F:')[1].strip()
                # Split variables by comma
                vars = clean_part.split(',')
                
                # Detect version based on feature count
                if len(vars) == 8:
                    # V2 format
                    if detected_version is None:
                        detected_version = 'v2'
                        logging.info("Detected V2 feature format (8 features)")
                    features = [float(v) for v in vars]
                    
                    # Target: Profit > 0 = 1 (Win), else 0 (Loss)
                    profit = float(str(row.get(profit_col, '0')).replace(',' ,'').replace('$', '').replace(' ', ''))
                    target = 1 if profit > 0 else 0
                    
                    features.append(target)
                    feature_data.append(features)
                    valid_count += 1
                elif len(vars) == 6:
                    # V1 format (legacy)
                    if detected_version is None:
                        detected_version = 'v1'
                        logging.info("Detected V1 feature format (6 features)")
                    features = [float(v) for v in vars]
                    
                    # Target: Profit > 0 = 1 (Win), else 0 (Loss)
                    profit = float(str(row.get(profit_col, '0')).replace(',' ,'').replace('$', '').replace(' ', ''))
                    target = 1 if profit > 0 else 0
                    
                    features.append(target)
                    feature_data.append(features)
                    valid_count += 1
            except Exception as e:
                pass # Skip malformed rows
    
    # Use appropriate headers based on detected version
    headers = headers_v2 if detected_version == 'v2' else headers_v1

    logging.info(f"Found {valid_count} valid training samples out of {len(df)} total rows.")
    
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
