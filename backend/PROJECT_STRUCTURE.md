# Project Structure - Clean & Organized

```
webhook_backend/
├── backtest_data/           # All backtest data consolidated here
│   ├── notion_exports/      # Manual quality-assessed trades (572)
│   │   ├── XAUUSD/
│   │   ├── GBPJPY/
│   │   ├── USDJPY/
│   │   ├── GBPCAD/
│   │   ├── CHFJPY/
│   │   └── NAS100/
│   ├── tradingview_exports/ # TradingView backtest exports (2,974)
│   │   ├── trades_XAUUSD_1_1_2023_19_1_2026.csv
│   │   ├── trades_GBPJPY_1_1_2023_19_1_2026.csv
│   │   ├── trades_USDJPY_1_1_2023_19_1_2026.csv
│   │   ├── trades_GBPCAD_1_1_2023_19_1_2026.csv
│   │   └── trades_EURUSD_1_1_2023_19_1_2026.csv
│   └── processed/           # Processed training datasets
│       ├── training_enhanced.csv    # 572 Notion trades with 21 features
│       ├── training_ultimate.csv    # 3,546 combined trades
│       ├── features_metadata.json
│       └── ultimate_metadata.json
│
├── scripts/                 # Analysis and training tools
│   ├── analyze_all_pairs.py         # Multi-pair performance analyzer
│   ├── prepare_enhanced_training.py # Notion data processor
│   ├── combine_all_data.py          # Combines all sources
│   └── train_enhanced_model.py      # AI model trainer
│
├── models/                  # Trained AI models
│   ├── model_ultimate.pkl           # 🎯 CURRENT: 3,546 trades, 76.6% accuracy
│   ├── model_enhanced.pkl           # 572 trades, 82.6% accuracy
│   ├── model_universal.pkl          # Old universal model
│   └── model_performance.json       # Performance metrics
│
├── reports/                 # Analysis reports
│   └── pair_performance.json        # Detailed metrics per pair
│
├── trading_bot.py           # Main webhook server
├── train_model.py           # Legacy trainer (use scripts version)
└── ... (other production files)
```

## Key Files

### Production

- `trading_bot.py` - Main bot (needs update to load `model_ultimate.pkl`)
- `models/model_ultimate.pkl` - **Deploy this!**

### Analysis

- `scripts/analyze_all_pairs.py` - Run anytime to check performance
- `reports/pair_performance.json` - Latest metrics

### Training

- `backtest_data/processed/training_ultimate.csv` - **3,546 trades ready for training**
- `scripts/train_enhanced_model.py` - Retrain model anytime

## Next Steps

1. **Deploy Ultimate Model:**

   ```bash
   # On Railway, ensure models/model_ultimate.pkl exists
   # Update trading_bot.py to load it
   ```

2. **Add New Data (Future):**
   - Drop new Notion CSVs into `backtest_data/notion_exports/[PAIR]/`
   - Drop new TradingView exports into `backtest_data/tradingview_exports/`
   - Run `python scripts/combine_all_data.py`
   - Run `python scripts/train_enhanced_model.py`

3. **Monitor Performance:**
   ```bash
   python scripts/analyze_all_pairs.py
   # Check reports/pair_performance.json
   ```

---

**Everything is now clean, organized, and ready for deployment!** 🚀
