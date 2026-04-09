# Notification Upgrade Design — 2026-03-30

## Goal

Upgrade the signal notification template on Discord and Telegram with a cleaner layout,
new contextual fields (account name, session, bar time), TradingView chart image support,
and removal of the unused two-way command system (whitelist + Telegram polling).

---

## Scope

### Part 1 — Remove command system
- Remove `src/adapters/telegram_polling.py`
- Remove `src/services/command_router.py`
- Remove `src/api_discord_commands.py`
- Remove TelegramPoller startup block from `src/worker.py` (~lines 1736–1741)
- Remove whitelist/command endpoints from `src/api_notifications.py`
  - Keep only `GET/PATCH /api/notifications/routing`
- Remove `WhitelistPanel` and `CommandLogPanel` from frontend
  - Keep only `RoutingPanel` on `/notifications` page

### Part 2 — Upgrade NotificationPayload
Extend `NotificationPayload` in `src/services/notification_service.py`:
- Add `image_url: Optional[str]` — TradingView chart screenshot URL
- Add `account_name: Optional[str]` — broker account label
- Add `bar_time: Optional[str]` — ISO string from signal payload
- Add `session: Optional[str]` — derived from bar_time UTC hour

Session derivation logic (UTC):
- 🌏 Asian:       00:00–07:59
- 🇬🇧 London:     08:00–12:59
- 🌐 Overlap:     13:00–15:59 (London + New York)
- 🇺🇸 New York:   16:00–20:59
- 🌙 Off-hours:   21:00–23:59

### Part 3 — Upgrade format_signal()
Update `NotificationService.format_signal()` to:
1. Accept `image_url`, `bar_time`, `account_name` as params (or read from signal dict)
2. Derive `session` from `bar_time`
3. Build two-section field layout:
   - **Trade Details**: Symbol, Side, R:R, Entry, SL, TP
   - **Execution**: Lot Size, Risk, Account
   - **Context**: Session, Bar Time, Zone Type (if present)
   - **🧠 AI Analysis**: if present (unchanged)
4. Store `image_url` on the payload

### Part 4 — Upgrade Discord render
Update `_payload_to_discord_embed()` in `discord.py`:
- Use section separators in field layout (inline grouping)
- Attach `image: { url: image_url }` when present

### Part 5 — Upgrade Telegram render
Update `_payload_to_telegram_html()` and `dispatch_payload()` in `discord.py`:
- When `image_url` is present → use `sendPhoto` with `caption` (HTML) instead of `sendMessage`
- When `image_url` is absent → use `sendMessage` as normal, append `📊 <a href="...">View Chart</a>` link

Chart link fallback: `https://www.tradingview.com/chart/?symbol={symbol}`

### Part 6 — Wire up in worker
Update wherever `format_signal()` is called in `worker.py`:
- Pass `image_url=signal.get("image_url")`, `bar_time=signal.get("bar_time")`, `account_name` from account profile

---

## New Discord Embed Layout

```
📈 NEW BUY SIGNAL — XAUUSD #42
──────────────────────────────
Symbol    Side    R:R
XAUUSD    BUY     1:2.50

Entry       Stop Loss              Take Profit
2650.50     2640.00 (105 pips)     2676.25 (257 pips)

Lot Size    Risk      Account
0.05 lots   $100.00   Ameer Live MT5

Session         Bar Time       Zone
🇬🇧 London      14:35 UTC      🟢 DEMAND

🧠 AI Analysis
Decision: GO | Confidence: 87.5%
Reason: Strong demand zone with ...

[Chart image embedded below embed]
```

## New Telegram Layout

```
📈 NEW BUY SIGNAL #42

Symbol: XAUUSD | BUY | R:R 1:2.50
Entry:  2650.50
SL:     2640.00 (105 pips)
TP:     2676.25 (257 pips)

Lots: 0.05 | Risk: $100.00
Account: Ameer Live MT5
Session: 🇬🇧 London | Bar: 14:35 UTC

🧠 AI: GO (87.5%) — Strong demand zone...

[Photo attached if image_url present]
[📊 View Chart link if no image]
```

---

## Files Changed

| File | Change |
|---|---|
| `src/services/notification_service.py` | Add fields, upgrade format_signal(), add session logic |
| `src/adapters/discord.py` | Upgrade embed render, add sendPhoto for Telegram |
| `src/worker.py` | Pass new fields to format_signal(), remove TelegramPoller block |
| `src/api_notifications.py` | Remove whitelist/command endpoints |
| `src/adapters/telegram_polling.py` | DELETE |
| `src/services/command_router.py` | DELETE |
| `src/api_discord_commands.py` | DELETE |
| `frontend/src/components/notifications/WhitelistPanel.tsx` | DELETE |
| `frontend/src/components/notifications/CommandLogPanel.tsx` | DELETE |
| `frontend/src/app/notifications/page.tsx` | Remove deleted panel imports |

## Files NOT changed
- `migrations/065_notification_system.sql` — DB tables kept (no harm leaving them)
- `notification_routing` logic — unchanged (routing still works)

---

## Verification Plan
1. Backend tests: `PYTHONPATH=/workspace pytest tests/ -v` — must stay green
2. Manual: fire a test webhook via `POST /webhook/test` and confirm log shows new format fields
3. Manual: fire a real webhook to Discord/Telegram and visually confirm new template
4. Frontend: load `/notifications` page — only RoutingPanel visible, no whitelist/command panels
