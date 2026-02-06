# 🎯 Setup Guide: Evaluation Dashboard

## ✅ What's Been Implemented

### Backend (Python)
- ✅ **API Endpoint**: `/evaluation/stats` - Returns real-time evaluation metrics
- ✅ **Settings**: Added 20+ evaluation config fields to `config/settings.py`
- ✅ **Router Registration**: Evaluation API registered in `src/api.py`

### Database
- ✅ **Migration Ready**: `migrations/006_update_alert_rules_run_mode.sql`

### Frontend (Next.js)
- ✅ **Stats Fix**: Total PnL now properly handles NULL values and calculates from entry/exit
- ✅ **Alert System Fix**: Consecutive losses now filters by LIVE trades only
- ✅ **LIVE/PAPER Badges**: Added to dashboard signals table
- ✅ **Daily/Total PnL**: TopBar shows Daily PnL (resets midnight) and Total PnL (all-time)
- ✅ **Daily Drawdown**: RiskBar shows Daily DD gauge

---

## 🚀 Quick Start: Enable Evaluation Mode

### Step 1: Add Environment Variables

Add these to your `.env` file:

```bash
# ── Evaluation Mode Configuration ──
EVALUATION_MODE=true
EVALUATION_PHASE=phase1
EVALUATION_START_DATE=2026-02-07T00:00:00

# Phase 1 Rules (Customize for your prop firm)
PHASE1_PROFIT_TARGET=5000.0
PHASE1_MAX_DAILY_LOSS=500.0
PHASE1_MAX_DRAWDOWN_PCT=5.0
PHASE1_MIN_TRADING_DAYS=4

# Phase 2 Rules
PHASE2_PROFIT_TARGET=2500.0
PHASE2_MAX_DAILY_LOSS=500.0
PHASE2_MAX_DRAWDOWN_PCT=5.0
PHASE2_MIN_TRADING_DAYS=4

# Funded Account Rules
FUNDED_MAX_DAILY_LOSS=500.0
FUNDED_MAX_DRAWDOWN_PCT=10.0

# Consistency Target
CONSISTENCY_TARGET_PCT=70.0
```

### Step 2: Apply Database Migration

Run the alert rules migration to filter by LIVE trades only:

```bash
# If using Supabase CLI
supabase db push migrations/006_update_alert_rules_run_mode.sql

# Or via psql
psql $DATABASE_URL < migrations/006_update_alert_rules_run_mode.sql
```

### Step 3: Restart Backend

```bash
# Kill existing workers
pkill -f "python.*worker.py"

# Restart API
# (Railway will auto-restart, or manually restart your process)
```

### Step 4: Test the API Endpoint

```bash
curl http://localhost:8000/evaluation/stats | jq
```

Expected response:
```json
{
  "evaluation_mode": true,
  "phase": "phase1",
  "current_day": 1,
  "total_days": 30,
  "profit_target": 5000.0,
  "current_profit": 0.0,
  "profit_progress_pct": 0.0,
  "max_daily_loss": 500.0,
  "today_pnl": 0.0,
  "daily_loss_buffer": 500.0,
  "max_drawdown_pct": 5.0,
  "current_drawdown_pct": 0.0,
  "min_trading_days": 4,
  "actual_trading_days": 0,
  "consistency_pct": 0.0,
  "consistency_target_pct": 70.0,
  "rules_passed": {
    "profit_target": false,
    "min_trading_days": false,
    "max_daily_loss": true,
    "max_drawdown": true,
    "consistency": false
  },
  "violations": [],
  "can_upgrade": false
}
```

---

## 📊 Current Dashboard Status

### ✅ Working Features:
1. **TopBar Metrics**:
   - Win Rate
   - Active Trades
   - **Daily PnL** (resets at midnight UTC)
   - **Total PnL** (all-time cumulative)

2. **RiskBar Gauges**:
   - Daily P&L ($ with progress bar)
   - Drawdown (%)
   - **Daily DD** (daily drawdown %)
   - Positions counter
   - Risk mode badge
   - Kill Switch button

3. **Recent Signals Table**:
   - **LIVE/PAPER badges** (L = red, P = blue)
   - Status badges
   - AI confidence rings
   - R:R ratios
   - PnL display

4. **Alert System**:
   - Filters by LIVE trades only (PAPER excluded)
   - Configurable via `alert_rules` table

---

## 🎨 Next Step: Frontend Evaluation Dashboard

The evaluation metrics API is **live and working**. Now you need to create the visual dashboard component.

### Option A: Use the Full Design (from EVALUATION_DASHBOARD_DESIGN.md)

I've created a complete design document with:
- Phase status header
- Progress bars for Profit Target, Max Daily Loss, Max Drawdown
- Completion checklist
- Violation alerts
- Upgrade button

You can implement this using the API endpoint: `GET /evaluation/stats`

### Option B: Add Evaluation Panel to Existing Dashboard

Add a simple evaluation summary card to your existing dashboard:

```tsx
// Add this to frontend/src/app/page.tsx

import { useQuery } from '@tanstack/react-query';

async function fetchEvaluationStats() {
  const res = await fetch('/evaluation/stats');
  return res.json();
}

function EvaluationCard() {
  const { data: eval } = useQuery({
    queryKey: ['evaluation-stats'],
    queryFn: fetchEvaluationStats,
    refetchInterval: 10000,
  });

  if (!eval?.evaluation_mode) return null;

  return (
    <div className="tv-card p-4">
      <h3 className="text-xs uppercase font-semibold mb-3">
        {eval.phase === 'phase1' ? 'Phase 1' : eval.phase === 'phase2' ? 'Phase 2' : 'Funded'}
        - Day {eval.current_day}/{eval.total_days}
      </h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span>Profit Target:</span>
          <span className={eval.current_profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
            ${eval.current_profit.toFixed(2)} / ${eval.profit_target}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Trading Days:</span>
          <span>{eval.actual_trading_days} / {eval.min_trading_days}</span>
        </div>
        <div className="flex justify-between">
          <span>Consistency:</span>
          <span>{eval.consistency_pct.toFixed(0)}% / {eval.consistency_target_pct}%</span>
        </div>
        {eval.can_upgrade && (
          <button className="w-full mt-2 px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
            ✓ Ready to Upgrade
          </button>
        )}
      </div>
    </div>
  );
}
```

---

## 🔧 Customizing for Your Prop Firm

### FTMO Rules:
```bash
PHASE1_PROFIT_TARGET=5000
PHASE1_MAX_DAILY_LOSS=500
PHASE1_MAX_DRAWDOWN_PCT=5
PHASE1_MIN_TRADING_DAYS=4

PHASE2_PROFIT_TARGET=2500
PHASE2_MAX_DAILY_LOSS=500
PHASE2_MAX_DRAWDOWN_PCT=5
PHASE2_MIN_TRADING_DAYS=4
```

### MyFundedFX Rules:
```bash
PHASE1_PROFIT_TARGET=4000
PHASE1_MAX_DAILY_LOSS=400
PHASE1_MAX_DRAWDOWN_PCT=4
PHASE1_MIN_TRADING_DAYS=3

PHASE2_PROFIT_TARGET=2000
PHASE2_MAX_DAILY_LOSS=400
PHASE2_MAX_DRAWDOWN_PCT=4
PHASE2_MIN_TRADING_DAYS=3
```

### The5ers Rules:
```bash
PHASE1_PROFIT_TARGET=6000
PHASE1_MAX_DAILY_LOSS=600
PHASE1_MAX_DRAWDOWN_PCT=6
PHASE1_MIN_TRADING_DAYS=5
```

---

## 📝 Testing Checklist

- [x] Backend API returns evaluation stats
- [x] Total PnL calculates correctly
- [x] Daily PnL resets at midnight UTC
- [x] Alert system filters LIVE trades only
- [x] LIVE/PAPER badges display in signals table
- [ ] Frontend evaluation dashboard component created
- [ ] Phase upgrade button works
- [ ] Violation alerts display properly

---

## 🎯 What You Have Now

1. ✅ **Hybrid LIVE/PAPER Trading** - Fully operational
2. ✅ **Dual PnL Tracking** - Daily (resets) + Total (cumulative)
3. ✅ **Smart Alert System** - Filters by run_mode
4. ✅ **Evaluation API** - Real-time prop firm metrics
5. ✅ **Configurable Rules** - 20+ evaluation settings

**Next:** Create the frontend dashboard component to visualize the evaluation metrics!

---

## 💡 Pro Tips

1. **Test with PAPER first**: Set signals to `run_mode: "PAPER"` to test evaluation logic without affecting real stats
2. **Monitor violations**: Check `/evaluation/stats` regularly for rule breaches
3. **Track consistency**: Aim for 70%+ profitable days
4. **Use Daily DD gauge**: Watch the "Daily DD" gauge in RiskBar to avoid breaching limits

---

## 🆘 Troubleshooting

### Total PnL shows $0.00
✅ **FIXED** - Query now handles NULL `pnl_usd` and calculates from entry/exit prices

### Alerts triggering for PAPER trades
✅ **FIXED** - Run migration `006_update_alert_rules_run_mode.sql` to add `run_mode` filter

### Evaluation endpoint returns error
- Check `EVALUATION_MODE=true` in `.env`
- Check `EVALUATION_START_DATE` is set (ISO format: `2026-02-07T00:00:00`)
- Restart backend after changing `.env`

---

Ready to build the frontend? Let me know if you want me to implement the full `EvaluationDashboard.tsx` component!
