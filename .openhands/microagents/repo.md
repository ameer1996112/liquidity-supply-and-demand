# Liquidity Supply and Demand Trading System

## Project Description

This is an institutional liquidity-based trading system that combines TradingView Pine Script strategies with a Python backend. The system receives webhook alerts from TradingView, processes them through an AI/ML quality filter, and executes trades via paper trading or live trading. It integrates with Supabase for data persistence and Discord for notifications.

## File Structure

- **backend/** - Python backend containing the main trading bot (`trading_bot.py`), paper trader, AI models, database integration (`supabase_db.py`), and utility scripts
- **scripts/** - Trading scripts including Pine Script strategies (`scripts/pinescript/`) and SQL schemas (`scripts/sql/`)
- **docs/** - Project documentation
- **tests/** - End-to-end test suite with Discord notification support

## Running Tests

```bash
# Install test dependencies
cd tests
pip install -r requirements-test.txt

# Run full E2E test suite
python e2e_test.py

# Run quick validation test
./quick_test.sh
```

Tests require environment variables: `WEBHOOK_URL`, `WEBHOOK_PASSPHRASE`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and optionally `DISCORD_WEBHOOK_URL`.

## Development Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python trading_bot.py
```

## Key Components

- **Supply & Demand Strategy**: Pine Script strategy for institutional liquidity-based trading
- **Webhook Backend**: Flask server that receives TradingView alerts
- **AI Filter**: ML model (`models/model_ultimate.pkl`) for trade quality assessment
- **Paper Trading**: Simulated trading for strategy testing before going live
