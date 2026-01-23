
import pandas as pd
import numpy as np
import pickle
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def backtest_ai_filter(csv_path='trade_XAUUSD_4_1_2023_19_1_2026.csv', model_path='model.pkl', threshold=0.5):
    """
    Simulates trading performance with and without the AI filter.
    """
    
    if not Path(csv_path).exists():
        logging.error(f"CSV file not found: {csv_path}")
        return
        
    if not Path(model_path).exists():
        logging.error(f"Model file not found: {model_path}")
        return

    logging.info(f"Load Data: {csv_path}") 
    logging.info(f"Load Model: {model_path}")
    logging.info(f"Threshold: {threshold}")

    # Load Model
    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    # Load Data
    df = pd.read_csv(csv_path)
    
    # 1. Parse Features
    feature_data = []
    indices = []
    
    # Check for target column (Signal or Comment)
    target_col = 'Signal' if 'Signal' in df.columns else 'Comment'
    profit_col = 'Net P&L USD' if 'Net P&L USD' in df.columns else 'Profit'

    for index, row in df.iterrows():
        comment = str(row.get(target_col, ''))
        if 'F:' in comment:
            try:
                clean_part = comment.split('F:')[1].strip()
                vars = clean_part.split(',')
                features = [float(v) for v in vars]
                
                # Ensure we have 8 features (V2 format)
                # If model expects 8 but we have 6, padding or error handling might be needed
                # But since we just trained on this data, it should match
                feature_data.append(features)
                indices.append(index)
            except:
                pass

    if not feature_data:
        logging.error("No valid feature rows found!")
        return

    # 2. Get Predictions
    X = np.array(feature_data)
    probs = model.predict_proba(X)[:, 1] # Probability of Class 1 (Win)
    
    # 3. Simulate Performance
    # Filter original dataframe to only rows we extracted features for
    sim_df = df.loc[indices].copy()
    sim_df['Win_Prob'] = probs
    
    # Parse financial columns
    sim_df['Net_Profit'] = sim_df[profit_col].astype(str).str.replace(',', '').str.replace('$', '').str.replace(' ', '').astype(float)
    
    # -- SCENARIO A: NO FILTER (BASELINE) --
    baseline_trades = len(sim_df)
    baseline_pnl = sim_df['Net_Profit'].sum()
    baseline_wins = len(sim_df[sim_df['Net_Profit'] > 0])
    baseline_wr = (baseline_wins / baseline_trades * 100) if baseline_trades > 0 else 0
    
    # -- SCENARIO B: AI FILTER --
    # Keep only trades where Win_Prob >= threshold
    filtered_df = sim_df[sim_df['Win_Prob'] >= threshold]
    
    ai_trades = len(filtered_df)
    ai_pnl = filtered_df['Net_Profit'].sum()
    ai_wins = len(filtered_df[filtered_df['Net_Profit'] > 0])
    ai_wr = (ai_wins / ai_trades * 100) if ai_trades > 0 else 0
    
    # -- REPORT RESULTS --
    print("\n" + "="*50)
    print(f"📊 BACKTEST RESULTS (Threshold > {threshold:.0%})")
    print("="*50)
    
    print(f"\n🚫 BASELINE (No AI):")
    print(f"   Trades: {baseline_trades}")
    print(f"   Win Rate: {baseline_wr:.2f}%")
    print(f"   Total P&L: ${baseline_pnl:,.2f}")
    
    print(f"\n🤖 WITH AI FILTER:")
    print(f"   Trades: {ai_trades} (Filtered out {baseline_trades - ai_trades})")
    print(f"   Win Rate: {ai_wr:.2f}%")
    print(f"   Total P&L: ${ai_pnl:,.2f}")
    
    print("\n" + "-"*50)
    
    pnl_diff = ai_pnl - baseline_pnl
    wr_diff = ai_wr - baseline_wr
    
    print(f"📈 IMPACT:")
    print(f"   P&L Change: {('+$' if pnl_diff >=0 else '-$')}{abs(pnl_diff):,.2f}")
    print(f"   Win Rate: {('+' if wr_diff >=0 else '')}{wr_diff:.2f}%")
    print("="*50 + "\n")

if __name__ == "__main__":
    backtest_ai_filter()
