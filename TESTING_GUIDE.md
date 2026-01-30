# 🧪 End-to-End Testing Guide

This guide explains how to verify your trading system is working correctly after running the smoke test.

---

## 📋 Pre-Test Checklist

Before running `scripts/test_live_flow.py`, ensure:

- [ ] **Backend** is running (`python main.py` or deployed)
- [ ] **Worker** is running (`python worker.py` or deployed)
- [ ] **Redis** is connected and accessible
- [ ] **Supabase** is configured with correct credentials
- [ ] **Frontend Dashboard** is open in your browser
- [ ] **AI Guardian** is enabled (if you want to test filtering)

---

## 🚀 Running the Test

```bash
# From the project root
python scripts/test_live_flow.py
```

You'll be prompted for:
1. **Backend URL** - e.g., `https://your-backend.railway.app` or `http://localhost:8000`
2. **Webhook Secret** - The secret configured in your backend's `WEBHOOK_SECRET` env var

---

## 📊 Expected Results

### Signal 1: BTCUSD (Perfect Buy Setup)
| Aspect | Expected | Meaning |
|--------|----------|---------|
| HTTP Response | `200 OK` | Backend received webhook |
| Status | `"success"` | Signal passed all filters |
| AI Decision | `APPROVE` | AI Guardian approved the trade |
| Dashboard | Green badge, High confidence | Visible as active signal |

### Signal 2: ETHUSD (Bad Setup)
| Aspect | Expected | Meaning |
|--------|----------|---------|
| HTTP Response | `200 OK` | Backend received webhook |
| Status | `"filtered"` | Signal was rejected |
| AI Decision | `REJECT` | AI Guardian vetoed the trade |
| Dashboard | Red "AI Veto" icon | Visible as filtered signal |

---

## 🔍 What to Check in Each Component

### 1. Backend Logs (main.py)

**Look for these lines confirming webhook receipt:**

```
INFO: POST /webhook - 200 OK
```

**Successful entry:**
```
📥 Webhook received: BTCUSD BUY @ 50000.0
✅ Pushed to Redis queue: trading_queue
```

**With AI filtering:**
```
📥 Webhook received: ETHUSD SELL @ 3000.0
🤖 AI Filter: REJECT - No inducement sweep detected
⚠️ Signal filtered: AI REJECT
```

---

### 2. Worker Logs (worker.py)

**Look for AI Guardian processing:**

For APPROVED signals (BTCUSD):
```
📦 Processing signal: BTCUSD BUY
🤖 AI Guardian analyzing...
✅ AI APPROVED (confidence: 85%)
   Reasoning: Strong setup with liquidity sweep and aggressive arrival
📈 Executing trade: BTCUSD BUY @ 50000.0
✅ Trade logged to Supabase
📢 Discord notification sent
```

For REJECTED signals (ETHUSD):
```
📦 Processing signal: ETHUSD SELL
🤖 AI Guardian analyzing...
❌ AI REJECT (confidence: 20%)
   Reasoning: CRITICAL: liq_swept=false violates THE INDUCEMENT RULE
⚠️ Signal filtered - not executing trade
📝 Filtered signal logged to Supabase
```

**Key log patterns to search for:**
- `🤖 AI APPROVED` - AI passed the signal
- `❌ AI REJECT` - AI vetoed the signal
- `confidence:` - AI's confidence percentage
- `Reasoning:` - Why the AI made its decision

---

### 3. Dashboard (Frontend)

**Open your Next.js dashboard and look for:**

#### Signal 1 (BTCUSD) - Should show:
- ✅ **Green Status Badge** - Indicates approved/active signal
- ✅ **High Confidence Bar** - Shows 80%+ confidence from AI
- ✅ **Entry Details** - BTCUSD, BUY, Entry: 50000, SL: 49500, TP: 51000
- ✅ **AI Reasoning** - "Strong setup with liquidity sweep..."

#### Signal 2 (ETHUSD) - Should show:
- ❌ **Red "AI Veto" Icon** - Indicates filtered signal
- ❌ **Low Confidence Bar** - Shows <40% confidence
- ❌ **Filtered Badge** - Marked as rejected
- ❌ **Rejection Reason** - "No inducement sweep detected"

**If you don't see Signal 2 at all:**
- Check if your dashboard has a "Show Filtered" toggle
- Filtered signals may be in a separate tab/view
- Check Supabase directly in the `signals` table with `status='filtered'`

---

## 🐛 Troubleshooting

### Problem: "Connection Failed"
```
✗ CONNECTION FAILED - Is the backend running?
```
**Solutions:**
- Verify backend is running: `curl http://localhost:8000/health`
- Check the URL is correct (http vs https, port number)
- For Railway/cloud: ensure the app is deployed and not sleeping

---

### Problem: HTTP 401 Unauthorized
```
✗ HTTP 401: {"detail": "Invalid webhook secret"}
```
**Solutions:**
- Verify `WEBHOOK_SECRET` in backend matches what you entered
- Try with no secret if testing locally
- Check for extra spaces or quotes in the secret

---

### Problem: HTTP 422 Validation Error
```
✗ HTTP 422: {"detail": [{"loc": ["symbol"], "msg": "field required"}]}
```
**Solutions:**
- This shouldn't happen with the test script
- If you modified the script, check required fields: `symbol`, `side`, `entry`, `sl`, `tp`, `size`

---

### Problem: Both Signals Accepted (AI not filtering)
```
⚠ Signal 2 (ETHUSD): Accepted (AI filter may be disabled)
```
**Solutions:**
- Check `AI_FILTER_ENABLED=true` in backend environment
- Verify `AI_API_KEY` is set and valid
- Check worker logs for AI errors/timeouts
- The system fails-open, so AI errors = trade proceeds

---

### Problem: Both Signals Rejected
**Solutions:**
- Check `AI_MIN_CONFIDENCE` setting (default: 75)
- Lower it temporarily for testing: `AI_MIN_CONFIDENCE=50`
- Check AI provider connectivity and API key

---

### Problem: Signals not appearing on Dashboard
**Solutions:**
1. Check Supabase directly:
   ```sql
   SELECT * FROM signals ORDER BY created_at DESC LIMIT 10;
   ```
2. Verify frontend is connected to correct Supabase project
3. Check browser console for JavaScript errors
4. Verify real-time subscriptions are working

---

## 🔧 Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBHOOK_SECRET` | No | Webhook authentication (empty = no auth) |
| `REDIS_URL` | Yes | Redis connection for queue |
| `SUPABASE_URL` | Yes | Database connection |
| `SUPABASE_ANON_KEY` | Yes | Supabase API key |
| `AI_FILTER_ENABLED` | No | Enable AI Guardian (default: true) |
| `AI_API_KEY` | If AI enabled | OpenAI/Anthropic/Groq API key |
| `AI_MIN_CONFIDENCE` | No | Threshold for approval (default: 75) |
| `AI_PROVIDER` | No | "openai", "anthropic", or "groq" |

---

## ✅ Success Criteria

Your system passes the smoke test if:

1. **Backend**: Both webhooks return HTTP 200
2. **AI Guardian**: Signal 1 approved, Signal 2 rejected
3. **Database**: Both signals appear in Supabase
4. **Dashboard**: Shows correct status for each signal
5. **Notifications**: Discord/Telegram received (if configured)

---

## 📝 Manual Verification Queries

### Check signals in Supabase:
```sql
-- Recent signals
SELECT
  symbol,
  side,
  status,
  ai_decision,
  ai_confidence,
  created_at
FROM signals
ORDER BY created_at DESC
LIMIT 10;

-- Count by status
SELECT status, COUNT(*)
FROM signals
GROUP BY status;
```

### Check Redis queue (if accessible):
```bash
redis-cli LLEN trading_queue  # Should be 0 if worker processed
```

---

## 🎉 All Tests Passed?

Congratulations! Your trading system is fully operational:

- ✅ Webhooks are received and validated
- ✅ Redis queue is processing signals
- ✅ AI Guardian is filtering low-quality setups
- ✅ Database is storing all signals
- ✅ Dashboard is displaying real-time data

You're ready to connect TradingView alerts! 🚀
