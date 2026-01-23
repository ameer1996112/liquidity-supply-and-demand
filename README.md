# Trading System

Institutional liquidity-based trading system with TradingView Pine Script strategies and Python backend.

## Project Structure

```
trading/
├── backend/              # Python backend for webhooks and trading automation
│   ├── trading_bot.py   # Main trading bot logic
│   ├── paper_trader.py  # Paper trading implementation
│   ├── supabase_db.py   # Database integration
│   ├── models/          # AI/ML models
│   ├── scripts/         # Utility scripts
│   └── venv/            # Python virtual environment
│
├── scripts/             # Trading scripts and strategies
│   ├── pinescript/      # TradingView Pine Script strategies
│   │   ├── supply_and_demand.pine          # Main institutional liquidity strategy (6,367 lines)
│   │   ├── supply_and_demand_optimized.pine # Optimized version (coming soon)
│   │   └── rd_concepts_strategy.pine       # RD concepts strategy
│   └── sql/             # Database schemas
│       └── supabase_schema.sql
│
├── docs/                # Documentation
│   ├── README.md                      # Original project info
│   ├── EXECUTION_PLAN.md              # Development roadmap
│   ├── PINE_SCRIPT_FIX.md             # Pine Script fixes
│   ├── QUICK_FIX.txt                  # Quick fixes
│   └── SUPABASE_MIGRATION_GUIDE.md    # Database migration guide
│
└── tests/               # Test suite
    └── e2e_test.py      # End-to-end tests
```

## Quick Start

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python trading_bot.py
```

### Pine Script
1. Open TradingView
2. Pine Editor > New
3. Copy content from [scripts/pinescript/supply_and_demand.pine](scripts/pinescript/supply_and_demand.pine)
4. Save and add to chart

## Key Components

- **Supply & Demand Strategy**: Institutional liquidity-based trading with smart money concepts
- **Webhook Backend**: Flask server for TradingView alerts
- **Paper Trading**: Simulated trading for strategy testing
- **AI Filter**: Machine learning quality filter for setups

## Documentation

See the [docs/](docs/) directory for detailed documentation on:
- Execution plans
- Pine Script fixes and optimizations
- Database migration guides
- Quick fixes and troubleshooting
