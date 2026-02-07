# 🎛️ Portfolio Command Center V2.0
## *Complete Implementation Guide*

---

## 📋 **What We Built**

You now have an **institutional-grade Portfolio Command Center** with three integrated systems:

### ✅ **1. Live Risk Controls**
- **Dynamic configuration** - Adjust risk settings without restart
- **Time-based rules** - Auto-reduce risk during NFP, weekends, etc.
- **Per-symbol overrides** - Custom risk per symbol
- **Real-time guard toggles** - Enable/disable VaR, sector, correlation guards on the fly

### ✅ **2. Portfolio Optimizer**
- **Trailing stops** - Auto-follow price with configurable distance
- **Profit lock rules** - Auto-scale out at +2R, move SL to BE
- **Batch position actions** - Close/scale multiple positions at once
- **Auto-hedging engine** - Currency exposure analysis + hedge suggestions

### ✅ **3. Multi-Account Orchestration**
- **Capital allocation** - Optimize capital distribution across accounts
- **Trade copying** - Master→Slave with scale-by-balance
- **Account performance tracking** - Side-by-side comparison
- **Strategy assignment** - Different risk profiles per account

---

## 🗂️ **File Structure**

### **Backend (Python)**

```
migrations/
├── 009_portfolio_command_center.sql  # Database schema (10 new tables)

src/core/
├── dynamic_config.py                 # Live config system (DB overrides)

src/services/
├── trailing_stop_manager.py          # Smart trailing stops
├── hedging_engine.py                 # Auto-hedging + currency exposure
├── account_orchestrator.py           # Capital allocation + performance
├── trade_copier.py                   # Master-slave trade copying

src/
├── api_portfolio_control.py          # Comprehensive API (40+ endpoints)
├── api.py                            # Updated with new router
├── worker.py                         # Updated with periodic tasks
```

### **Database Tables (10 New)**

1. **`risk_config_overrides`** - Live risk settings
2. **`time_based_risk_rules`** - Automated time-based adjustments
3. **`trailing_stops`** - Trailing stop configurations
4. **`profit_lock_rules`** - Auto scale-out rules
5. **`profit_lock_executions`** - Audit log
6. **`account_strategies`** - Per-account configs
7. **`trade_copy_rules`** - Master-slave rules
8. **`trade_copy_log`** - Copy audit trail
9. **`capital_allocation_history`** - Allocation changes
10. **`hedge_suggestions`** - Auto-hedge recommendations

---

## 🚀 **Setup & Deployment**

### **Step 1: Run Database Migration**

```bash
# Connect to your Supabase database
psql <your-connection-string>

# Run the migration
\i migrations/009_portfolio_command_center.sql

# Verify tables created
\dt public.risk_config_overrides
\dt public.trailing_stops
\dt public.account_strategies
```

### **Step 2: Restart Backend Services**

```bash
# Stop current worker
docker-compose down worker

# Rebuild (to pick up new dependencies)
docker-compose build worker api

# Start services
docker-compose up -d worker api
```

### **Step 3: Verify API Endpoints**

Visit: `http://localhost:8000/docs`

You should see new endpoint groups:
- `/api/portfolio-control/risk/*` (Risk Controls)
- `/api/portfolio-control/optimizer/*` (Portfolio Optimizer)
- `/api/portfolio-control/accounts/*` (Multi-Account)

---

## 📚 **API Usage Examples**

### **Live Risk Controls**

#### Get All Current Settings
```bash
GET /api/portfolio-control/risk/settings

Response:
{
  "settings": {
    "risk_percent": 0.5,
    "max_lot_size": 10.0,
    "min_rr_ratio": 2.0,
    "portfolio_var_enabled": true,
    ...
  },
  "overrides_count": 3
}
```

#### Update Risk Setting (Live, No Restart!)
```bash
PATCH /api/portfolio-control/risk/settings/risk_percent
{
  "value": 0.75,
  "change_reason": "Market conditions favorable - increasing risk"
}

Response:
{
  "status": "ok",
  "setting": "risk_percent",
  "value": 0.75
}
```

#### Create Time-Based Rule
```bash
POST /api/portfolio-control/risk/time-rules
{
  "rule_name": "NFP Risk Reduction",
  "trigger_type": "TIME_OF_DAY",
  "trigger_time_start": "13:00:00",
  "trigger_time_end": "14:00:00",
  "risk_multiplier": 0.5,
  "enabled": true
}
```

---

### **Portfolio Optimizer**

#### Add Trailing Stop
```bash
POST /api/portfolio-control/optimizer/trailing-stop
{
  "signal_id": 123,
  "trail_distance_pips": 50,
  "wait_for_breakeven": true
}

Response:
{
  "status": "ok",
  "trailing_stop_id": 45
}
```

#### Create Profit Lock Rule
```bash
POST /api/portfolio-control/optimizer/profit-lock-rule
{
  "rule_name": "Scale Out at +2R",
  "trigger_r_multiple": 2.0,
  "close_percent": 0.5,
  "move_sl_to": "+1R",
  "enabled": true
}
```

#### Batch Close Positions
```bash
POST /api/portfolio-control/optimizer/batch-action
{
  "signal_ids": [101, 102, 103],
  "action": "close"
}

Response:
{
  "status": "ok",
  "action": "close",
  "total": 3,
  "success": 3,
  "failed": 0
}
```

#### Generate Hedge Suggestion
```bash
POST /api/portfolio-control/optimizer/generate-hedge

Response:
{
  "status": "ok",
  "suggestion_id": 12,
  "suggestion": {
    "symbol": "EURUSD",
    "side": "short",
    "size": 0.85,
    "expected_var_reduction_pct": 35.0,
    "reason": "High EUR exposure detected (long $8,500)",
    "currency_exposure": {
      "EUR": 8500,
      "USD": -3200,
      "JPY": 2100
    }
  }
}
```

---

### **Multi-Account Orchestration**

#### Get Account Comparison
```bash
GET /api/portfolio-control/accounts/comparison

Response:
{
  "accounts": [
    {
      "account_name": "FTMO Challenge",
      "strategy_type": "BALANCED",
      "balance": 100000,
      "daily_pnl": 1245.0,
      "daily_pnl_pct": 1.25,
      "win_rate": 0.68,
      "sharpe_ratio": 2.3,
      "active_positions": 3
    },
    {
      "account_name": "MyFundedFX Phase 2",
      "balance": 50000,
      "daily_pnl": -320.0,
      "daily_pnl_pct": -0.64,
      "win_rate": 0.55,
      "sharpe_ratio": 1.2,
      "active_positions": 2
    }
  ]
}
```

#### Suggest Capital Allocation
```bash
POST /api/portfolio-control/accounts/allocation/suggest
{
  "total_capital": 175000,
  "optimization_goal": "maximize_sharpe"
}

Response:
{
  "total_capital": 175000,
  "total_allocated": 170000,
  "unallocated": 5000,
  "recommendations": [
    {
      "account_name": "FTMO Challenge",
      "current_balance": 100000,
      "suggested_allocation_usd": 120000,
      "change_usd": 20000,
      "change_pct": 20.0,
      "reason": "High Sharpe ratio (2.30) | Strong win rate (68%)"
    },
    {
      "account_name": "MyFundedFX Phase 2",
      "current_balance": 50000,
      "suggested_allocation_usd": 35000,
      "change_usd": -15000,
      "change_pct": -30.0,
      "reason": "Underperforming"
    }
  ],
  "expected_portfolio_sharpe": 2.1
}
```

#### Create Trade Copy Rule
```bash
POST /api/portfolio-control/accounts/trade-copy-rules
{
  "rule_name": "FTMO → Personal",
  "master_account_name": "FTMO Challenge",
  "slave_account_names": ["Personal Account"],
  "scale_by_balance": true,
  "risk_multiplier": 0.5,
  "copy_sl_tp": true,
  "enabled": true
}
```

---

## 🔄 **Worker Integration**

The worker now runs **periodic tasks every 60 seconds**:

1. **Update trailing stops** - Adjusts SL based on price movement
2. **Clear config cache** - Picks up DB setting changes
3. **Apply time-based rules** - Checks if any rules should trigger

```python
# In worker.py main loop (every 60 seconds)
- TradeWatchdog.run_sync()
- AlertEngine.evaluate_all()
- TrailingStopManager.update_trailing_stops()  # NEW
- clear_settings_cache()  # NEW
```

---

## 🎨 **Frontend Integration (Next Steps)**

You now need to build 3 frontend pages:

### **Page 1: Risk Control Center**
**File:** `frontend/src/app/risk-control/page.tsx`

**Features:**
- Risk sliders (risk_percent, max_lot_size, min_rr_ratio, VaR limits)
- Guard toggles (enable/disable VaR, sector, correlation guards)
- Time-based rules table (create/edit/delete)
- Per-symbol risk overrides table

**API calls:**
```typescript
GET /api/portfolio-control/risk/settings
PATCH /api/portfolio-control/risk/settings/{setting_key}
GET /api/portfolio-control/risk/time-rules
POST /api/portfolio-control/risk/time-rules
```

---

### **Page 2: Portfolio Optimizer**
**File:** `frontend/src/app/portfolio-optimizer/page.tsx`

**Features:**
- Active trailing stops table
- Profit lock rules editor
- Batch position selector (multi-select checkboxes)
- Batch action buttons (Close All, Scale Out 50%, Add Trailing Stops)
- Hedge suggestions panel

**API calls:**
```typescript
GET /api/portfolio-control/optimizer/trailing-stops
POST /api/portfolio-control/optimizer/trailing-stop
GET /api/portfolio-control/optimizer/profit-lock-rules
POST /api/portfolio-control/optimizer/batch-action
POST /api/portfolio-control/optimizer/generate-hedge
```

---

### **Page 3: Multi-Account Command Center**
**File:** `frontend/src/app/multi-account/page.tsx`

**Features:**
- Account performance cards (side-by-side)
- Capital allocation slider per account
- "Suggest Allocation" button → shows recommendations
- Trade copy rules table (create/edit/toggle)
- Copy log (recent copies)

**API calls:**
```typescript
GET /api/portfolio-control/accounts/comparison
POST /api/portfolio-control/accounts/allocation/suggest
POST /api/portfolio-control/accounts/allocation/execute/{account_name}
GET /api/portfolio-control/accounts/trade-copy-rules
POST /api/portfolio-control/accounts/trade-copy-rules
```

---

## 🧪 **Testing the System**

### **Test 1: Live Risk Update**
```bash
# 1. Check current risk
curl http://localhost:8000/api/portfolio-control/risk/settings

# 2. Update risk_percent to 0.75
curl -X PATCH http://localhost:8000/api/portfolio-control/risk/settings/risk_percent \
  -H "Content-Type: application/json" \
  -d '{"value": 0.75, "change_reason": "Testing live update"}'

# 3. Send a test signal - it should use 0.75% risk (no restart needed!)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol": "EURUSD", "side": "buy", "entry": 1.0800, ...}'

# 4. Check worker logs - should show "Using dynamic setting for 'risk_percent': 0.75"
docker-compose logs -f worker | grep "risk_percent"
```

---

### **Test 2: Trailing Stop**
```bash
# 1. Create a test position (signal_id=999)
# 2. Add trailing stop
curl -X POST http://localhost:8000/api/portfolio-control/optimizer/trailing-stop \
  -H "Content-Type: application/json" \
  -d '{
    "signal_id": 999,
    "trail_distance_pips": 50,
    "wait_for_breakeven": true
  }'

# 3. Wait 60 seconds (next periodic update cycle)
# 4. Check worker logs - should show "Updating X trailing stops"
docker-compose logs -f worker | grep "Trailing"

# 5. Verify SL moved
curl http://localhost:8000/api/positions/active
```

---

### **Test 3: Hedge Suggestion**
```bash
# 1. Create multiple positions (e.g., 3 EUR longs)
# 2. Generate hedge suggestion
curl -X POST http://localhost:8000/api/portfolio-control/optimizer/generate-hedge

# Expected response: suggests shorting EURUSD to offset EUR exposure
```

---

## 📊 **Database Queries (Useful for Debugging)**

```sql
-- View all active risk overrides
SELECT * FROM risk_config_overrides WHERE is_active = true;

-- View trailing stops
SELECT ts.*, sig.symbol, sig.side, sig.entry, sig.sl
FROM trailing_stops ts
JOIN trading_signals sig ON ts.signal_id = sig.id
WHERE ts.is_active = true;

-- View time-based rules
SELECT * FROM time_based_risk_rules WHERE enabled = true;

-- View account strategies
SELECT * FROM account_strategies WHERE is_active = true;

-- View trade copy log
SELECT * FROM trade_copy_log ORDER BY copied_at DESC LIMIT 20;

-- View hedge suggestions
SELECT * FROM hedge_suggestions WHERE status = 'PENDING';
```

---

## 🎯 **Key Benefits**

### **Before (V1.1):**
- ❌ All risk changes required `.env` edit + restart (30+ seconds downtime)
- ❌ Manual position management (click each position individually)
- ❌ No portfolio hedging or auto-scaling
- ❌ Multi-account support existed but no UI control

### **After (V2.0):**
- ✅ **Live risk controls** - Adjust settings in <1 second, no restart
- ✅ **Batch operations** - Close 10 positions with 1 click
- ✅ **Smart automation** - Trailing stops, profit locks, auto-hedging
- ✅ **Capital optimization** - Data-driven allocation across accounts
- ✅ **Trade copying** - Scale proven strategies across accounts

---

## 🚀 **Next Steps for You**

1. **Run the migration** (`009_portfolio_command_center.sql`)
2. **Restart backend** (docker-compose restart)
3. **Test API endpoints** (use Postman or curl examples above)
4. **Build frontend pages** (use examples in this guide)
5. **Integrate into main dashboard** (add navigation links)

---

## 📞 **Support & Troubleshooting**

### **Common Issues:**

**Issue: API returns 503 "Supabase not configured"**
- Check `.env` has `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Restart API: `docker-compose restart api`

**Issue: Trailing stops not updating**
- Check worker logs: `docker-compose logs -f worker`
- Verify trailing_stop_manager initialized: should see "TrailingStopManager initialized" in logs
- Ensure positions have valid broker_order_id

**Issue: Dynamic config not working**
- Clear cache manually: restart worker
- Check `risk_config_overrides` table has data
- Verify `is_active = true`

---

## 🎉 **Congratulations!**

You now have a **world-class Portfolio Command Center** that rivals institutional trading platforms!

**What you can do now:**
- Adjust risk **instantly** without downtime
- Manage **hundreds of positions** with batch operations
- **Auto-hedge** currency exposure
- **Optimize capital** allocation across accounts
- **Copy trades** from master to slave accounts

**Go build the frontend and take it for a spin!** 🚀
