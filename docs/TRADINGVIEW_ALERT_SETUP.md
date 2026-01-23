# TradingView Alert Setup Guide

## Problem: Not Receiving Real Trading Alerts

If you're running the bot but not getting real trade notifications, the issue is likely that **TradingView alerts aren't configured correctly**.

## ✅ Step-by-Step Setup

### 1. Verify Pine Script Settings

Open your Pine Script indicator/strategy in TradingView and check these settings:

**Required Settings:**
- ✅ **Enable Webhook Alerts**: Must be `TRUE`
- ✅ **Configuration Profile**: Choose one (Conservative/Balanced/Aggressive)

**Optional - Lower for Testing:**
- **AI Quality Threshold**: Try `30-40` (default is 60)
- **Min Entry Grade**: Try `C` (less strict)
- **Min Return Strength**: Set to `0` (disable compression filter)

### 2. Create TradingView Alert

#### Option A: Strategy Alert (Recommended)

1. **Open your chart** with the Pine Script strategy running
2. **Click the Alert button** (clock icon in top toolbar)
3. **Configure the alert:**

   ```
   Condition: "S&D Algo [Pro]" (or your strategy name)
   Option: "Order fills and alert() function calls"

   Alert name: Trading Bot - Live Alerts

   Webhook URL:
   https://grand-learning-production-bc96.up.railway.app/webhook

   Message:
   {{strategy.order.alert_message}}
   ```

4. **Alert Settings:**
   - Frequency: `Once Per Bar Close`
   - Expiration: `Open-ended`
   - Notify on App: ✅ (optional)

5. **Click "Create"**

#### Option B: Manual Alert (For Indicators)

If you're using an indicator (not strategy):

```json
{
  "passphrase": "test_passphrase_123",
  "symbol": "{{ticker}}",
  "side": "{{strategy.order.action}}",
  "entry": {{close}},
  "sl": {{plot_0}},
  "tp": {{plot_1}},
  "size": 0.10,
  "zone_id": {{time}},
  "zone_type": "demand"
}
```

### 3. Test the Alert

#### Quick Test (Manual Trigger)

1. **In TradingView:** Right-click your chart → "Add Alert"
2. **Test with a simple condition** like "Price crossing MA"
3. **Use same webhook URL** and message format
4. **Trigger the alert** by adjusting the chart timeframe

#### Real Test (Wait for Strategy Signal)

1. **Check Strategy Tester** in TradingView
   - Does it show any trades?
   - If NO trades → Your strategy filters are too strict

2. **Wait for a signal** on the chart
   - Look for BUY/SELL markers
   - Wait for the bar to close (alerts trigger on bar close)

3. **Check Discord** for notification

### 4. Verify Alert is Working

Run the diagnostic script:

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python3 scripts/check_trading_status.py
```

You should see:
- ✅ Real strategy alerts (not test alerts with zone_id 12345)
- ✅ Zone IDs are timestamps (unique values)
- ✅ Status is "active" (not filtered)

## 🔧 Troubleshooting

### Issue: No Trades in Strategy Tester

**Cause:** Strategy filters too strict, no valid setups found

**Fix:** Temporarily loosen filters:

```
Pine Script Settings:
- Min Entry Grade: C (instead of B+ or A)
- AI Quality Threshold: 30 (instead of 60)
- Min Return Strength: 0 (instead of 30-50)
- Enable Grade Filter: FALSE
```

### Issue: Alerts Show "Filtered" Status

**Cause:** Backend bot is rejecting alerts

**Fix:** Check backend/.env:

```bash
MIN_RR_RATIO=1.0          # Lower from 2.0
TRADING_SESSIONS=         # Leave empty to disable session filter
SWAP_HOURS_UTC=           # Leave empty to disable swap filter
```

### Issue: Test Alerts Only (zone_id 12345)

**Cause:** TradingView alert using wrong message format

**Fix:** Message MUST be `{{strategy.order.alert_message}}` exactly

### Issue: Webhook URL Error 404

**Cause:** Wrong webhook URL

**Fix:** Use exact URL:
```
https://grand-learning-production-bc96.up.railway.app/webhook
```

## 📊 Expected Results

Once configured correctly:

1. **TradingView generates signal** → Marker appears on chart
2. **Bar closes** → Alert triggers
3. **Webhook sent** → Backend receives data
4. **Discord notification** → You get notified
5. **Database record** → Trade logged in Supabase

## 🎯 Quick Checklist

Before asking "why no alerts?", verify:

- [ ] Pine Script: "Enable Webhook Alerts" = TRUE
- [ ] TradingView: Alert created with webhook URL
- [ ] TradingView: Message = `{{strategy.order.alert_message}}`
- [ ] Strategy Tester: Shows at least some trades
- [ ] Chart: Shows BUY/SELL signal markers
- [ ] Backend: Railway deployment is running (check health endpoint)
- [ ] Diagnostic: `python3 scripts/check_trading_status.py` shows real alerts

## 🆘 Still Not Working?

1. **Check Railway logs:**
   ```bash
   railway logs --tail
   ```

2. **Test webhook manually:**
   ```bash
   cd tests
   python3 e2e_test.py
   ```

3. **Check Supabase database:**
   - Go to Supabase dashboard
   - Check `trading_signals` table
   - Look for recent entries

4. **Discord webhook test:**
   ```bash
   curl -X POST "https://discord.com/api/webhooks/YOUR_WEBHOOK" \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'
   ```

## 📝 Notes

- Alerts trigger **on bar close** (not real-time)
- Strategy must have **at least one valid setup** to generate alerts
- Test alerts (zone_id 12345) don't represent real trading signals
- Use `Balanced` or `Aggressive` profile for more frequent signals
- `Conservative` profile is very selective (fewer trades)

---

**Need help?** Run: `python3 scripts/check_trading_status.py`
