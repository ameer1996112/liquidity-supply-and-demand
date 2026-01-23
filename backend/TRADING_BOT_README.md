# Trading Alert Server v4.0

A full-featured trading alert system that receives TradingView webhooks and forwards them to Discord/Telegram with trade tracking and analytics.

## Features

- **Multi-Channel Notifications** - Discord + Telegram
- **Trade Tracking Database** - SQLite with full history
- **Web Dashboard** - View alerts, statistics, win rate
- **Position Size Calculator** - Auto-calculate lot size based on risk
- **Alert Filtering** - Filter by R:R ratio and trading sessions
- **Cloud Ready** - Deploy to Railway/Render in minutes

## Architecture

```
┌─────────────┐     Webhook      ┌──────────────┐     Notify     ┌─────────────┐
│ TradingView │ ──────────────►  │ Flask Server │ ─────────────► │  Discord    │
│   (Pine)    │    JSON POST     │  + SQLite    │                │  Telegram   │
└─────────────┘                  └──────┬───────┘                └─────────────┘
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │  Dashboard   │
                                 │  Statistics  │
                                 └──────────────┘
```

---

## Quick Start (Local)

### 1. Install

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/webhook_backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your settings (see Configuration section below).

### 3. Run

```bash
python trading_bot.py
```

Open http://localhost:3000 to see the dashboard.

### 4. Expose with ngrok (for TradingView)

```bash
ngrok http 3000
```

Use the ngrok URL in TradingView alerts: `https://xxx.ngrok.io/webhook`

---

## Cloud Deployment (Railway)

**No more ngrok!** Get a permanent URL.

### 1. Create Railway Account

Go to [railway.app](https://railway.app) and sign up (free).

### 2. Deploy

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
cd webhook_backend
railway init

# Deploy
railway up
```

### 3. Set Environment Variables

In Railway dashboard → Your Project → Variables:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx
TELEGRAM_BOT_TOKEN=xxx (optional)
TELEGRAM_CHAT_ID=xxx (optional)
ACCOUNT_BALANCE=10000
RISK_PERCENT=1.0
```

### 4. Get Your URL

Railway gives you a URL like: `https://your-app.up.railway.app`

Use in TradingView: `https://your-app.up.railway.app/webhook`

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_WEBHOOK_URL` | Discord webhook URL | Required |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | Optional |
| `TELEGRAM_CHAT_ID` | Telegram chat ID | Optional |
| `WEBHOOK_PORT` | Server port | 3000 |
| `ACCOUNT_BALANCE` | Your account balance | 10000 |
| `RISK_PERCENT` | Risk per trade (%) | 1.0 |
| `MIN_RR_RATIO` | Minimum R:R to forward | 1.0 |
| `TRADING_SESSIONS` | Trading hours (UTC) | Empty |

### Setting Up Telegram

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy the bot token
4. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID
5. Add both to `.env`

---

## API Endpoints

### Webhook (TradingView)

```bash
POST /webhook
Content-Type: application/json

{
    "symbol": "GBPJPY",
    "side": "buy",
    "entry": 159.200,
    "sl": 159.000,
    "tp": 159.500,
    "size": 0.1,
    "zone_id": "optional"
}
```

### Trade Tracking

```bash
# Mark as taken
GET /alert/1/taken

# Mark as skipped
GET /alert/1/skipped

# Mark as missed
GET /alert/1/missed

# Record outcome with P&L
POST /alert/1/outcome
{"outcome": "win", "pnl": 150.00, "notes": "Perfect entry"}
```

### Data & Stats

```bash
# Get dashboard
GET /

# Get all alerts (JSON)
GET /alerts

# Get statistics
GET /stats

# Get single alert
GET /alert/1

# Calculate position size
GET /position-size?sl_pips=20&symbol=EURUSD&balance=10000&risk=1
```

### Health Check

```bash
GET /health
```

---

## Dashboard

Access at `http://localhost:3000` (or your Railway URL).

Shows:
- Total alerts
- Today's alerts
- Win rate
- Total P&L
- Average R:R
- Trades taken
- Full alert history with actions

---

## Testing

```bash
# Send test alert
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"GBPJPY","side":"buy","entry":159.200,"sl":159.000,"tp":159.500,"size":0.1}'

# Check stats
curl http://localhost:3000/stats

# Mark trade as taken
curl http://localhost:3000/alert/1/taken

# Record outcome
curl -X POST http://localhost:3000/alert/1/outcome \
  -H "Content-Type: application/json" \
  -d '{"outcome":"win","pnl":150}'
```

---

## File Structure

```
webhook_backend/
├── .env                  # Your configuration
├── .env.example          # Config template
├── trading_bot.py        # Main server
├── trades.db             # SQLite database (auto-created)
├── trading_bot.log       # Logs
├── requirements.txt      # Dependencies
├── Procfile              # Railway/Heroku
├── railway.json          # Railway config
├── runtime.txt           # Python version
├── start_bot.sh          # Local startup script
└── TRADING_BOT_README.md # This file
```

---

## Troubleshooting

### "No notification channels configured"
Add `DISCORD_WEBHOOK_URL` or `TELEGRAM_BOT_TOKEN` to `.env`

### Alerts not showing in Discord
- Check webhook URL is correct
- Test with curl command above
- Check `trading_bot.log` for errors

### Railway deployment fails
- Ensure all files are committed to git
- Check Railway logs in dashboard
- Verify environment variables are set

### Database issues
Delete `trades.db` to reset (you'll lose history).

---

## Upgrading

The server auto-creates the database on first run. If you're upgrading from an older version:

1. Backup your `trades.db` file
2. Pull the new code
3. Restart the server

---

## Next Steps

Ideas for further improvements:

- [ ] Email notifications
- [ ] SMS via Twilio
- [ ] TradingView chart screenshots
- [ ] Auto-execution via broker API
- [ ] Multiple strategies support
- [ ] Advanced analytics & charts
