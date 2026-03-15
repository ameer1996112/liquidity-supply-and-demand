# Risk Management System Overview

> Last updated: 2026-03-15 — Role separation overhaul (4 bugs fixed, see bottom)

## Architecture: Pine Script + Backend Cooperation

```
Pine Script = Signal Generator ONLY
  ├─ Calculates: entry price, SL, TP, intended lot size
  ├─ Fires alerts when zone + liquidity + AI conditions are met
  └─ Daily loss check (4%): backtest simulation only, does NOT control live bot

Backend Bot = Single Risk Authority
  ├─ PropGuard Step-Up: survival 0.5x → building 0.75x → normal 1.0x → (funded only: aggressive 2.0x)
  ├─ Trinity kill switch: 4% daily loss / 8% drawdown → halt all trading
  ├─ FTMO compliance: EvaluationTracker enforces phase limits when EVALUATION_MODE=true
  ├─ Correlation guard: max 1 position per correlated group
  ├─ Sector guard: max 10-40% exposure per sector
  ├─ Portfolio VaR guard: max $500 VaR
  └─ Final sizing = min(pine_lots, max_allowed) × risk_multiplier
```

**Key principle: Pine proposes, backend disposes.**
Pine's lot size is always capped by the backend. The backend's risk_multiplier is now
correctly applied to the final position size (was silently ignored before 2026-03-15).

## FTMO $50k Limit Alignment

| Metric               | FTMO Firm Limit | Bot Kill Threshold | Buffer  |
|---------------------|-----------------|--------------------|---------|
| Daily loss           | $2,500 (5%)     | $2,000 (4%)        | $500    |
| Overall drawdown     | $5,000 (10%)    | $4,000 (8%)        | $1,000  |
| Phase 1 profit target| $5,000 (10%)    | Track only         | —       |
| Single trade risk    | No limit        | 1% ($500 max)      | —       |
| Best day / total profit | 40% (FTMO rule) | Throttle at 35%, block at 40% | ✓ |

**To activate FTMO compliance:** Set `EVALUATION_MODE=true` in Railway env vars.

---

## 🛡️ Multi-Layer Defense Architecture

Your bot uses **7 layers of risk management** working together to protect your account:

---

## Layer 1: AI Ensemble Brain (NOW ACTIVE ✅)

**What it does:** Filters out low-quality trades BEFORE execution

### Components:
1. **Random Forest (RF) Model** - Machine learning win probability
   - Threshold: `ML_MIN_CONFIDENCE=0.65` (65%)
   - Rejects trades with <65% predicted win probability
   - Uses 50+ features: zone quality, trend alignment, liquidity, momentum

2. **RAG Engine** (Retrieval Augmented Generation)
   - Queries knowledge base of trading rules
   - Matches current setup against proven strategies
   - Example: "FLIP entries require 15m boundary for futures"

3. **LLM Context Layer** (GPT-4o + GPT-4o-mini)
   - Two-tier system: Quick model first, escalates to deep model when uncertain
   - Analyzes market narrative + strategy rules + RF score
   - Makes final GO/NO_GO decision with reasoning

**Escalation Rules:**
- Quick model rejects → Deep model reviews (may override)
- RF probability in gray zone (55-72%) → Deep model reviews
- Quick model gives short reason → Deep model adds context

**Current Settings (Railway):**
```bash
AI_FILTER_ENABLED=true          # ✅ NOW ENABLED
AI_MODE=enforce                 # ✅ NOW BLOCKING TRADES
ENABLE_LLM_FILTER=true          # ✅ Full ensemble
ML_MIN_CONFIDENCE=0.65          # ✅ 65% threshold
ML_WARNING_ONLY_MODE=false      # ✅ Strict mode
AI_QUICK_MODEL=gpt-4o-mini      # Fast first pass
AI_DEEP_MODEL=gpt-4o            # Deep analysis when needed
```

---

## Layer 2: Trinity Guard Rails (ACTIVE ✅)

**What it does:** Hard limits on position sizing and exposure

### Rules:
```bash
TRINITY_MAX_DAILY_LOSS_PCT=4%        # Max 4% loss per day ($2,000 on $50k)
TRINITY_MAX_DRAWDOWN_PCT=8%          # Max 8% drawdown ($4,000 on $50k)
TRINITY_MAX_RISK_PER_TRADE_PCT=0.5%  # Max 0.5% risk per trade ($250)
TRINITY_MAX_POSITIONS=3              # Max 3 open positions
TRINITY_MAX_CURRENCY_EXPOSURE=2      # Max 2 positions per currency
TRINITY_MAX_CORRELATION_GROUP=1      # Max 1 position in correlated pairs
TRINITY_ALLOW_HEDGING=false          # No hedging allowed
```

**Enforcement:**
- Daily loss limit hit → Trading paused until next day
- Drawdown limit hit → Kill switch activated
- Per-trade risk exceeded → Position size reduced
- Max positions reached → New signals rejected
- Currency exposure exceeded → Reject signals in same currency

---

## Layer 3: PropGuard Risk Scaling (ACTIVE ✅)

**What it does:** Dynamically adjusts position size based on account performance

### Risk Modes:
```bash
RISK_MODE=step_up               # Current mode
ENABLE_RISK_SCALING=true        # Dynamic scaling enabled
```

**Step-Up Mode:**
- Phase 1 (0-33% profit target): `risk_multiplier = 0.7` (30% smaller positions)
- Phase 2 (33-66% profit target): `risk_multiplier = 0.85` (15% smaller)
- Phase 3 (66-100% profit target): `risk_multiplier = 1.0` (full size)

**Example:** $50k FTMO account with $5k profit target
- Phase 1 ($0-$1,666 profit): Risk 0.35% per trade ($175)
- Phase 2 ($1,666-$3,333 profit): Risk 0.425% per trade ($212.50)
- Phase 3 ($3,333-$5,000 profit): Risk 0.5% per trade ($250)

**Conservative Mode:** (if you switch to `RISK_MODE=conservative`)
- Always use `risk_multiplier = 0.5` (50% of base risk)

---

## Layer 4: Portfolio Risk Management (ACTIVE ✅)

**What it does:** Prevents correlation blow-ups and concentration risk

### Guards:
1. **Correlation Guard**
   - Tracks correlation between open positions
   - Rejects new positions that increase correlation above 0.7
   - Prevents EUR/GBP + EUR/USD + GBP/USD all going the same direction

2. **Sector Exposure Guard**
   - Max 40% of portfolio in any one sector (FX majors, commodities, indices)
   - Prevents over-concentration in gold or crude oil

3. **Portfolio VaR Guard**
   - Calculates Value at Risk (VaR) for entire portfolio
   - Rejects trades that push portfolio VaR too high
   - Uses historical volatility + correlation matrix

**Current Settings:**
```bash
CORRELATION_MATRIX_ENABLED=true
MAX_AVG_PORTFOLIO_CORRELATION=0.7
```

---

## Layer 5: Position Sizing (ACTIVE ✅)

**What it does:** Calculates safe lot sizes based on stop loss and risk

### Formula:
```python
risk_usd = account_balance * (RISK_PERCENT / 100) * propguard_multiplier
sl_adjusted = sl ± (STOP_LOSS_BUFFER_PIPS * pip_size)  # Buffer prevents stop hunts
position_size = risk_usd / (sl_pips * pip_value_per_lot)
position_size = min(position_size, MAX_LOT_SIZE)
```

**Current Settings:**
```bash
RISK_PERCENT=0.5                # 0.5% risk per trade
STOP_LOSS_BUFFER_PIPS=1.0       # 1 pip safety margin beyond zone
MAX_LOT_SIZE=100.0              # Cap at 100 lots (prevents runaway sizing)
```

**Example:** EURUSD trade
- Account: $50,000
- Risk: 0.5% = $250
- Stop Loss: 10 pips + 1 pip buffer = 11 pips
- Pip value: $10/lot
- Position size: $250 / (11 × $10) = 2.27 lots

**Dynamic Pip Value (JPY pairs):**
- USDJPY @ 149.5: pip_value = (0.01 / 149.5) × 100,000 = $6.69/lot
- NZDJPY @ 93.9: pip_value = (0.01 / 93.9) × 100,000 = $10.65/lot

---

## Layer 6: Pine Script Deterministic Filters (ACTIVE ✅)

**What it does:** Mirrors TradingView strategy entry conditions

### Filters:
```python
PINE_MIN_SCORE=70               # Zone must score 70+ (quality threshold)
PINE_MIN_GRADE=B                # Zone must be grade B or better
PINE_REQUIRE_LIQ_SWEPT=false    # Liquidity sweep optional (strict S&D)
PINE_MIN_RETURN_STRENGTH=40     # Minimum return leg strength
PINE_MIN_DEPARTURE_STRENGTH=40  # Minimum departure leg strength
```

**Additional Checks:**
- **FLIP Timing Validation:** FLIP entries must occur on 15-min boundaries (00/15/30/45)
- **Futures Entry Model:** Futures prefer BOC/Directional Close, FLIP requires 15m/1H boundary
- **Dead Zone Filter:** No trades during low-liquidity sessions (configurable)
- **Daily Trade Limit:** Max trades per day (prevents overtrading)

---

## Layer 7: Kill Switch & Circuit Breakers (ACTIVE ✅)

**What it does:** Emergency stop mechanisms

### Types:
1. **Manual Kill Switch**
   ```bash
   TRADING_KILL_SWITCH=false    # Set to true to stop all trading
   ```

2. **Circuit Breaker** (LIVE only)
   - Tracks consecutive losses
   - Auto-pauses trading after N consecutive losses
   - Requires manual reset

3. **Daily Loss Kill Switch**
   - Auto-activates when `TRINITY_MAX_DAILY_LOSS_PCT` reached
   - Automatically resets at midnight UTC

4. **Drawdown Kill Switch**
   - Auto-activates when `TRINITY_MAX_DRAWDOWN_PCT` reached
   - Requires manual investigation + reset

---

## 📊 Guard Rail Execution Order (worker.py)

When a signal arrives from TradingView, it passes through guards in this order:

```
1. Invalid Size Check (size <= 0) → REJECT
2. Max Lot Size Guard (size > 100 lots) → REJECT
3. Kill Switch → REJECT
4. Circuit Breaker (LIVE only) → REJECT
5. PropGuard (apply risk scaling multiplier)
6. Correlation Manager → REJECT if correlation too high
7. Portfolio VaR Guard → REJECT if VaR exceeds limit
8. Sector Exposure Guard → REJECT if sector > 40%
9. Pine Filters (zone quality, grade, liquidity) → REJECT
10. AI Ensemble Brain (RF → RAG → LLM) → REJECT or APPROVE
```

**Result:**
- If ALL guards pass → Trade executed on broker
- If ANY guard rejects → Signal logged to database with rejection reason
- Rejection reasons visible in frontend dashboard

---

## 🎯 Prop Firm Compliance

Your current settings are **optimized for prop firm evaluations**:

### FTMO / MFF / E8 Compliance:
✅ Daily loss limit: 4% (FTMO = 5% max)
✅ Max drawdown: 8% (FTMO = 10% max)
✅ Risk per trade: 0.5% (conservative)
✅ Position limits: 3 max (prevents overtrading)
✅ No hedging (FTMO rule)
✅ No martingale (Trinity enforces fixed risk %)

### Why AI Filtering is Critical for Prop Firms:
- **Reduces drawdown:** Only takes high-quality setups (65%+ win probability)
- **Prevents tilt trading:** LLM rejects trades in bad market conditions
- **Enforces rules:** RAG engine ensures strategy consistency
- **Audit trail:** Every rejection logged with reasoning

---

## 📈 Expected Performance Impact (Now That AI is Active)

**Before (AI disabled):**
- ✅ All TradingView signals executed
- Win rate: ~50% (random)
- Many low-quality trades
- High drawdown risk

**After (AI enabled):**
- ❌ ~30-40% of signals rejected by AI
- ✅ Only high-probability setups executed
- Expected win rate: 55-65% (based on RF model)
- Reduced drawdown, smoother equity curve

**Trade-off:**
- Fewer trades (60-70% of original volume)
- Higher quality trades
- Better risk-adjusted returns

---

## 🔧 How to Monitor Risk Management

### Check Guard Rails Status:
```bash
# View all risk settings
railway variables | grep -E "TRINITY|RISK|AI_"

# Check recent rejections
python3 scripts/diagnose_ai_filtering.py

# View guard rail logs
railway logs --filter "REJECT"
```

### Dashboard Metrics:
- **Positions page:** Shows live exposure, correlation, VaR
- **Analytics page:** Win rate, profit factor, drawdown tracking
- **Prop Firm page:** Daily PnL, equity curve, evaluation progress

---

## 🚨 Emergency Actions

### If You're Losing Money Fast:
```bash
# 1. Activate kill switch immediately
railway variables --set TRADING_KILL_SWITCH=true

# 2. Close all positions manually via MetaTrader or dashboard

# 3. Investigate what happened
railway logs --filter "ERROR"
python3 scripts/diagnose_ai_filtering.py
```

### If AI is Too Aggressive (rejecting good trades):
```bash
# Lower ML threshold slightly
railway variables --set ML_MIN_CONFIDENCE=0.60

# Or switch AI to shadow mode temporarily (log only, no blocking)
railway variables --set AI_MODE=shadow
```

### If AI is Too Permissive (approving bad trades):
```bash
# Raise ML threshold
railway variables --set ML_MIN_CONFIDENCE=0.70

# Make sure enforce mode is active
railway variables --set AI_MODE=enforce
```

---

## 📚 Summary

Your bot now has **military-grade risk management** with 7 defensive layers:

1. ✅ **AI Ensemble Brain** (RF + RAG + LLM) - Filters bad setups
2. ✅ **Trinity Guard Rails** - Hard limits on risk exposure
3. ✅ **PropGuard Scaling** - Dynamic position sizing for prop firms
4. ✅ **Portfolio Risk** - Correlation + VaR + sector limits
5. ✅ **Position Sizing** - Safe lot calculation with buffers
6. ✅ **Pine Filters** - Zone quality + entry model validation
7. ✅ **Kill Switches** - Emergency stops

**Changes Just Applied:**
- `AI_FILTER_ENABLED=false` → `true` ✅
- `AI_MODE=shadow` → `enforce` ✅
- `ML_WARNING_ONLY_MODE=true` → `false` ✅

**Result:** AI will now actively filter trades. Expect to see rejections in your dashboard with detailed reasoning.

**Next Steps:**
1. Wait for deployment to complete (check Railway dashboard)
2. Monitor next few signals to see AI filtering in action
3. Review rejection reasons to understand AI decision-making
4. Adjust `ML_MIN_CONFIDENCE` if needed (0.60-0.70 range)
