# 📊 How to Export Backtest Data from TradingView

## Step-by-Step Instructions

### 1️⃣ Open TradingView and Load Your Strategy

1. Go to **TradingView.com**
2. Open a **chart** (any symbol, we'll change it)
3. Click **"Pine Editor"** (bottom panel)
4. Open your **SND_Strategy.pine** script
5. Click **"Add to Chart"** button (top right of Pine Editor)

### 2️⃣ Configure the Backtest

1. **Select Symbol**: Choose XAUUSD, GBPJPY, or any symbol you trade
2. **Set Timeframe**: Click timeframe dropdown → Select **5 minutes (5m)**
3. **Set Date Range**:
   - Click the **calendar icon** (top toolbar)
   - Set **"From"** date to 6-12 months ago (e.g., Aug 2024)
   - Set **"To"** date to today
4. Wait for the strategy to run (may take 10-30 seconds)

### 3️⃣ Open Strategy Tester

1. Look at the **bottom panel** of the screen
2. Click the **"Strategy Tester"** tab (next to Pine Editor)
3. You should see:
   - **Overview** tab showing performance metrics
   - **List of Trades** tab
   - **Performance Summary** tab

### 4️⃣ Export the Trades List

1. Click the **"List of Trades"** tab
2. You'll see a table with columns:
   - Trade #
   - Date/Time
   - Signal (Long/Short)
   - Price
   - Contracts
   - P/L
   - %
   - Cumulative P/L
   - **Comment** ← THIS IS CRITICAL! Must contain AI features

3. **Select all trades**:
   - **Windows**: Click first row → Ctrl+A
   - **Mac**: Click first row → Cmd+A
   - All rows should be highlighted in blue

4. **Copy the data**:
   - **Windows**: Ctrl+C
   - **Mac**: Cmd+C

### 5️⃣ Save to CSV

1. Open **Excel** (or Google Sheets)
2. **Paste the data**:
   - **Windows**: Ctrl+V
   - **Mac**: Cmd+V
3. You should see all columns with headers
4. **Check the "Comment" column**:
   - Should contain text like: `score:85 freshness:1 rsi:60 trend:1 ...`
   - If Comment is empty, **STOP** - see troubleshooting below

5. **Save as CSV**:
   - File → Save As
   - File name: `backtest.csv`
   - File type: **CSV (Comma delimited) (*.csv)**
   - Location: `~/Downloads/backtest.csv`

### 6️⃣ Verify the Export

Open the CSV in a text editor to verify:

```bash
head ~/Downloads/backtest.csv
```

**Expected format:**
```
Trade #,Signal,Date/Time,Price,Contracts,P/L,%,Cumulative P/L,Run-up,Drawdown,Comment
1,Long,2024-08-12 09:35:00,2020.50,0.5,+125.50,+0.62%,+125.50,+180.25,-45.00,"score:85 freshness:1 session:2 atr_ratio:1.2 is_accuracy:1 trend:1 rsi:60 htf_trend:1 rvol:1.5 adx:25 touch_count:0 base_quality:2 departure_strength:2 return_strength:2 liquidity_distance:8.5 liquidity_spread:50"
```

---

## ⚠️ CRITICAL: Verify AI Features in Comment

**The Comment column MUST contain AI features!**

If your Comment column is empty or doesn't have features like `score:85 freshness:1 rsi:60`, then your Pine Script might not be configured to output them.

### How to Enable AI Features in Comments:

1. Open your **SND_Strategy.pine** in Pine Editor
2. Find the webhook/alert configuration section (usually near the end)
3. Make sure the strategy uses `alert()` or webhook that includes all features
4. Look for code like:
   ```pine
   alert_msg = "score:" + str.tostring(zone_score) +
               " freshness:" + str.tostring(freshness) +
               " rsi:" + str.tostring(rsi) + ...
   ```

5. If missing, the Pine script needs to be updated to include features

---

## 📊 Expected Data Volume

For good AI training, aim for:

- ✅ **Minimum**: 200+ trades (3-6 months)
- ✅ **Good**: 500+ trades (6-12 months)
- ✅ **Excellent**: 1000+ trades (12+ months)

**Tip**: Use 5m timeframe on XAUUSD or GBPJPY for more trades

---

## 🔧 Troubleshooting

### Problem: "List of Trades" is empty

**Solution:**
- Wait for strategy to finish calculating (10-30 seconds)
- Check if date range is correct
- Verify strategy is enabled (not paused)
- Try refreshing the page

### Problem: Comment column is empty

**Solution:**
- Your Pine Script might not be outputting features to comments
- Check Pine Script for `alert()` or `strategy.entry()` comment parameter
- You may need to update the script to include AI features in comments

### Problem: Only shows last 100 trades

**Solution:**
- TradingView may limit display - but copy/paste should get all trades
- Try exporting smaller date ranges (e.g., 3 months at a time)
- Combine multiple exports

### Problem: Excel splits the data incorrectly

**Solution:**
- Save as `.txt` first, then open in Excel
- Use "Text to Columns" feature in Excel
- Or use Google Sheets which handles paste better

---

## ✅ Checklist Before Converting

Before running the converter, verify:

- [ ] CSV file has at least 200 rows (excluding header)
- [ ] Comment column exists and is populated
- [ ] Comment contains features like `score:XX freshness:X rsi:XX`
- [ ] Trades have P/L values (wins and losses)
- [ ] File is saved as .csv format

---

## 📈 Next Steps After Export

Once you have `~/Downloads/backtest.csv`:

```bash
# 1. Convert to training format
python ml/collect_training_data.py --source tradingview --input ~/Downloads/backtest.csv

# 2. Train the model
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv

# 3. Check results
open ml/model_metrics_v2.png
cat ml/model_metadata_v2.json

# 4. Deploy to Railway
git add ml/model_v2.pkl ml/scaler_v2.pkl ml/encoders_v2.pkl
git commit -m "Upgrade AI brain to v2.0"
git push
```

---

**Questions? Check:**
- Is the Comment column populated? (Most critical!)
- Do you have 200+ trades in the export?
- Is the CSV format correct?
