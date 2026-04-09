# Notification Upgrade Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Upgrade the signal notification template with chart images, cleaner layout, and new contextual fields (account, session, bar time) — while removing the unused two-way command system (Telegram polling, whitelist, command router).

**Architecture:** The `NotificationPayload` dataclass in `notification_service.py` is the single source of truth for all notification data. `dispatch_payload()` in `discord.py` renders and sends to Discord/Telegram. Worker passes signal data through `format_signal()` to build the payload. Command system files are deleted; frontend panels removed.

**Tech Stack:** Python (FastAPI backend), `requests` (HTTP to Discord/Telegram APIs), React/Next.js (frontend), Supabase (DB — tables left intact), pytest (tests)

---

### Task 1: Delete the command system files

**Files:**
- Delete: `src/services/command_router.py`
- Delete: `src/adapters/telegram_polling.py`
- Delete: `src/api_discord_commands.py`

**Step 1: Delete the files**

```bash
rm src/services/command_router.py
rm src/adapters/telegram_polling.py
rm src/api_discord_commands.py
```

**Step 2: Verify nothing critical imports them**

```bash
grep -r "command_router\|telegram_polling\|api_discord_commands" src/ --include="*.py" -l
```

Expected: only `src/worker.py` references `telegram_polling` — we fix that in Task 2.

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: delete command router and telegram polling files"
```

---

### Task 2: Remove TelegramPoller from worker.py

**Files:**
- Modify: `src/worker.py` ~lines 1730–1745

**Step 1: Find and remove the TelegramPoller block**

In `src/worker.py`, locate and delete this block:

```python
try:
    from src.adapters.telegram_polling import TelegramPoller
    _telegram_poller = TelegramPoller(supabase=supabase, meta_api=_meta_api_for_commands)
    ...
except Exception as _tp_exc:
    logger.warning("TelegramPoller init failed (non-fatal): %s", _tp_exc)
```

Remove the entire try/except block (roughly 6–8 lines).

**Step 2: Verify worker imports cleanly**

```bash
PYTHONPATH=/workspace python3 -c "import src.worker; print('OK')"
```

Expected: `OK` (no ImportError)

**Step 3: Run backend tests**

```bash
PYTHONPATH=/workspace pytest tests/ -v
```

Expected: all previously passing tests still pass.

**Step 4: Commit**

```bash
git add src/worker.py
git commit -m "chore: remove TelegramPoller startup from worker"
```

---

### Task 3: Strip whitelist/command endpoints from api_notifications.py

**Files:**
- Modify: `src/api_notifications.py`

**Step 1: Remove the whitelist section**

Delete everything from line `# ─── Whitelist ───` to the end of `remove_whitelist()` function — that is, remove these endpoints:
- `GET /api/notifications/whitelist`
- `POST /api/notifications/whitelist`
- `DELETE /api/notifications/whitelist/{id}`

**Step 2: Remove the command audit log section**

Delete from `# ─── Command audit log ───` to the end of the file:
- `GET /api/notifications/commands`

**Step 3: Remove now-unused Pydantic model**

Remove the `WhitelistEntry` model class.

**Step 4: Final file should only have:**

```python
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/routing")
def get_routing(): ...

@router.patch("/routing/{alert_type}")
def update_routing(alert_type: str, body: RoutingUpdate): ...
```

**Step 5: Verify API starts**

```bash
PYTHONPATH=/workspace python3 -c "from src.api_notifications import router; print('OK')"
```

Expected: `OK`

**Step 6: Run tests**

```bash
PYTHONPATH=/workspace pytest tests/ -v
```

**Step 7: Commit**

```bash
git add src/api_notifications.py
git commit -m "feat: remove whitelist and command-log API endpoints"
```

---

### Task 4: Remove frontend command/whitelist panels

**Files:**
- Delete: `frontend/src/components/notifications/WhitelistPanel.tsx`
- Delete: `frontend/src/components/notifications/CommandLogPanel.tsx`
- Modify: `frontend/src/app/notifications/page.tsx`

**Step 1: Delete the panel files**

```bash
rm frontend/src/components/notifications/WhitelistPanel.tsx
rm frontend/src/components/notifications/CommandLogPanel.tsx
```

**Step 2: Update notifications page**

Replace `frontend/src/app/notifications/page.tsx` with:

```tsx
'use client';

import { Bell } from 'lucide-react';
import { RoutingPanel } from '@/components/notifications/RoutingPanel';

export default function NotificationsPage() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Bell className="h-4 w-4 text-[var(--to-text-dim)]" />
        <h1 className="text-sm font-semibold text-[var(--to-text-primary)]">Notification Settings</h1>
      </div>
      <RoutingPanel />
    </div>
  );
}
```

**Step 3: Verify frontend builds**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no import errors.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: remove whitelist and command-log panels from notifications page"
```

---

### Task 5: Extend NotificationPayload with new fields

**Files:**
- Modify: `src/services/notification_service.py`

**Step 1: Write the failing test**

In `tests/test_notification_service.py` (create if missing), add:

```python
from src.services.notification_service import NotificationService

def test_format_signal_includes_session_and_bar_time():
    svc = NotificationService()
    signal = {
        "id": 1, "symbol": "XAUUSD", "side": "BUY",
        "entry": 2650.50, "sl": 2640.0, "tp": 2676.25, "size": 0.05,
        "bar_time": "2026-03-30T09:30:00Z",  # London session
        "image_url": "https://www.tradingview.com/x/abc123/",
    }
    payload = svc.format_signal(signal, account_name="Ameer Live MT5")

    assert payload.image_url == "https://www.tradingview.com/x/abc123/"
    assert payload.account_name == "Ameer Live MT5"
    assert "Session" in payload.fields
    assert "🇬🇧" in payload.fields["Session"]   # London session emoji
    assert "Bar Time" in payload.fields
    assert "09:30" in payload.fields["Bar Time"]

def test_format_signal_session_new_york():
    svc = NotificationService()
    signal = {
        "id": 2, "symbol": "EURUSD", "side": "SELL",
        "entry": 1.08, "sl": 1.085, "tp": 1.07, "size": 0.1,
        "bar_time": "2026-03-30T17:00:00Z",  # New York session
    }
    payload = svc.format_signal(signal)
    assert "🇺🇸" in payload.fields.get("Session", "")

def test_format_signal_image_url_none_when_missing():
    svc = NotificationService()
    signal = {"id": 3, "symbol": "XAUUSD", "side": "BUY", "entry": 2650.5, "sl": 2640.0, "tp": 2676.25}
    payload = svc.format_signal(signal)
    assert payload.image_url is None
```

**Step 2: Run to verify tests fail**

```bash
PYTHONPATH=/workspace pytest tests/test_notification_service.py -v
```

Expected: `AttributeError: 'NotificationPayload' object has no attribute 'image_url'`

**Step 3: Add new fields to NotificationPayload**

In `src/services/notification_service.py`, update the dataclass:

```python
@dataclass
class NotificationPayload:
    type: Literal["signal", "close", "alert", "guard", "bug"]
    title: str
    fields: dict[str, str]
    color: NotificationColor
    description: str = ""
    footer: str = ""
    metadata: dict = field(default_factory=dict)
    signal_id: Optional[int] = None
    alert_id: Optional[int] = None
    # New fields
    image_url: Optional[str] = None
    account_name: Optional[str] = None
    bar_time: Optional[str] = None
```

**Step 4: Add session derivation helper**

Add this function near the bottom of `notification_service.py` (with the other helpers):

```python
def _derive_session(bar_time_iso: Optional[str]) -> Optional[str]:
    """Derive trading session from bar_time UTC hour."""
    if not bar_time_iso:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(str(bar_time_iso).replace("Z", "+00:00"))
        hour = dt.astimezone(timezone.utc).hour
        if 0 <= hour < 8:
            return "🌏 Asian"
        if 8 <= hour < 13:
            return "🇬🇧 London"
        if 13 <= hour < 16:
            return "🌐 London/NY Overlap"
        if 16 <= hour < 21:
            return "🇺🇸 New York"
        return "🌙 Off-hours"
    except Exception:
        return None
```

**Step 5: Update format_signal() signature and body**

Update `format_signal()` to accept and use the new fields:

```python
def format_signal(
    self,
    signal: dict[str, Any],
    ai_result: Optional[dict[str, Any]] = None,
    mode: str = "manual",
    account_name: Optional[str] = None,
    image_url: Optional[str] = None,
) -> NotificationPayload:
    ...
    # Resolve image_url — prefer explicit param, fallback to signal dict
    resolved_image_url = image_url or signal.get("image_url")

    # Resolve account name
    resolved_account = account_name or signal.get("account_name")

    # Resolve bar_time
    bar_time_raw = signal.get("bar_time") or signal.get("signal_time")
    session = _derive_session(bar_time_raw)
    bar_time_display = None
    if bar_time_raw:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(str(bar_time_raw).replace("Z", "+00:00"))
            bar_time_display = dt.strftime("%H:%M UTC")
        except Exception:
            bar_time_display = str(bar_time_raw)

    # ... (existing entry/sl/tp/rr logic unchanged) ...

    # Build fields in order:
    fields: dict[str, str] = {
        "Symbol":      f"**{symbol}**",
        "Side":        side,
        "R:R":         f"1:{rr_ratio:.2f}" if rr_ratio else "N/A",
        "Entry":       f"{entry:.5g}" if entry else "N/A",
        "Stop Loss":   sl_display if sl else "N/A",
        "Take Profit": tp_display if tp else "N/A",
    }
    if size:
        fields["Lot Size"] = f"{size:.2f} lots"
    if risk_usd:
        fields["Risk"] = f"${risk_usd:.2f}"
    if resolved_account:
        fields["Account"] = resolved_account
    if session:
        fields["Session"] = session
    if bar_time_display:
        fields["Bar Time"] = bar_time_display
    if signal.get("zone_id") is not None:
        fields["Zone ID"] = str(signal["zone_id"])
    if signal.get("zone_type"):
        zone_emoji = "🟢" if signal["zone_type"] == "demand" else "🔴"
        fields["Zone Type"] = f"{zone_emoji} {signal['zone_type'].upper()}"

    ai_section = _format_ai_analysis(ai_result or signal.get("ai_reasoning"))
    if ai_section:
        fields["🧠 AI Analysis"] = ai_section

    return NotificationPayload(
        type="signal",
        title=f"{mode_prefix}{emoji} New {side} Signal — #{signal_id}",
        description=f"**{'Auto-executed (paper)' if mode == 'paper' else 'Execute manually'}**",
        fields=fields,
        color=color,
        footer=f"Signal #{signal_id}",
        metadata={"symbol": symbol, "side": side, "mode": mode},
        signal_id=signal_id,
        image_url=resolved_image_url,
        account_name=resolved_account,
        bar_time=bar_time_raw,
    )
```

**Step 6: Run tests — expect pass**

```bash
PYTHONPATH=/workspace pytest tests/test_notification_service.py -v
```

Expected: 3 tests PASS.

**Step 7: Run full test suite**

```bash
PYTHONPATH=/workspace pytest tests/ -v
```

**Step 8: Commit**

```bash
git add src/services/notification_service.py tests/test_notification_service.py
git commit -m "feat: add image_url, account_name, session, bar_time to NotificationPayload"
```

---

### Task 6: Upgrade Discord embed render

**Files:**
- Modify: `src/adapters/discord.py` — `_payload_to_discord_embed()` function

**Step 1: Write failing test**

In `tests/test_discord_render.py` (create if missing):

```python
from src.adapters.discord import _payload_to_discord_embed
from src.services.notification_service import NotificationPayload

def test_embed_includes_image_when_image_url_set():
    payload = NotificationPayload(
        type="signal", title="📈 BUY XAUUSD", fields={"Symbol": "XAUUSD"},
        color="buy", image_url="https://www.tradingview.com/x/abc123/"
    )
    embed = _payload_to_discord_embed(payload)
    assert "image" in embed
    assert embed["image"]["url"] == "https://www.tradingview.com/x/abc123/"

def test_embed_no_image_key_when_image_url_none():
    payload = NotificationPayload(
        type="signal", title="📈 BUY XAUUSD", fields={"Symbol": "XAUUSD"},
        color="buy", image_url=None
    )
    embed = _payload_to_discord_embed(payload)
    assert "image" not in embed
```

**Step 2: Run to verify tests fail**

```bash
PYTHONPATH=/workspace pytest tests/test_discord_render.py -v
```

Expected: FAIL — `"image" not in embed`

**Step 3: Update _payload_to_discord_embed()**

```python
def _payload_to_discord_embed(payload: NotificationPayload) -> dict:
    color = COLOR_MAP.get(payload.color, 0x3B82F6)
    # Non-inline fields: AI analysis, Details, multi-line blocks
    NON_INLINE = {"🧠 AI Analysis", "Details", "Reason"}
    fields = [
        {"name": k, "value": str(v), "inline": k not in NON_INLINE}
        for k, v in payload.fields.items()
    ]
    embed: dict = {
        "title": payload.title,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": fields,
    }
    if payload.description:
        embed["description"] = payload.description
    if payload.footer:
        embed["footer"] = {"text": payload.footer}
    if payload.image_url:
        embed["image"] = {"url": payload.image_url}
    return embed
```

**Step 4: Run tests — expect pass**

```bash
PYTHONPATH=/workspace pytest tests/test_discord_render.py -v
```

**Step 5: Commit**

```bash
git add src/adapters/discord.py tests/test_discord_render.py
git commit -m "feat: attach chart image to Discord embed when image_url present"
```

---

### Task 7: Upgrade Telegram render — sendPhoto fallback

**Files:**
- Modify: `src/adapters/discord.py` — `dispatch_payload()` Telegram section

**Step 1: Write failing test**

In `tests/test_discord_render.py`, add:

```python
from unittest.mock import patch, MagicMock
from src.adapters.discord import _payload_to_telegram_html
from src.services.notification_service import NotificationPayload

def test_telegram_html_includes_chart_link_when_no_image():
    payload = NotificationPayload(
        type="signal", title="📈 BUY", fields={"Symbol": "XAUUSD"},
        color="buy", image_url=None,
        metadata={"symbol": "XAUUSD"}
    )
    html = _payload_to_telegram_html(payload)
    assert "tradingview.com" in html
    assert "XAUUSD" in html

def test_telegram_html_no_chart_link_when_image_present():
    payload = NotificationPayload(
        type="signal", title="📈 BUY", fields={"Symbol": "XAUUSD"},
        color="buy", image_url="https://www.tradingview.com/x/abc/",
        metadata={"symbol": "XAUUSD"}
    )
    html = _payload_to_telegram_html(payload)
    # When image is present, we use sendPhoto — html is the caption, no extra link needed
    assert "View Chart" not in html
```

**Step 2: Run to verify tests fail**

```bash
PYTHONPATH=/workspace pytest tests/test_discord_render.py::test_telegram_html_includes_chart_link_when_no_image -v
```

**Step 3: Update _payload_to_telegram_html()**

```python
def _payload_to_telegram_html(payload: NotificationPayload) -> str:
    lines = [f"<b>{payload.title}</b>"]
    if payload.description:
        lines.append(payload.description)
    lines.append("")
    for k, v in payload.fields.items():
        if k == "🧠 AI Analysis":
            lines.append(f"<b>{k}</b>\n<i>{v}</i>")
        else:
            lines.append(f"<b>{k}:</b> {v}")
    if payload.footer:
        lines.append(f"\n<i>{payload.footer}</i>")
    # Chart link fallback — only when no image_url (image will be sent as photo)
    if not payload.image_url:
        symbol = payload.metadata.get("symbol", "")
        if symbol:
            chart_url = f"https://www.tradingview.com/chart/?symbol={symbol}"
            lines.append(f'\n📊 <a href="{chart_url}">View Chart</a>')
    return "\n".join(lines)
```

**Step 4: Update dispatch_payload() Telegram section**

In `dispatch_payload()`, replace the Telegram block:

```python
# Telegram
if routing.get("telegram_enabled", True) and s.telegram_bot_token and s.telegram_chat_id:
    try:
        text = _payload_to_telegram_html(payload)
        if payload.image_url:
            # Send as photo with caption
            r = requests.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendPhoto",
                json={
                    "chat_id": s.telegram_chat_id,
                    "photo": payload.image_url,
                    "caption": text,
                    "parse_mode": "HTML",
                },
                timeout=15,
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
        if r.status_code == 200:
            msg_id = r.json().get("result", {}).get("message_id")
            if msg_id and supabase_client and payload.signal_id:
                try:
                    supabase_client.table("trading_signals").update(
                        {"telegram_message_id": msg_id}
                    ).eq("id", payload.signal_id).execute()
                except Exception:
                    pass
            logger.info("dispatch_payload: Telegram sent (%s)", payload.title)
        else:
            logger.warning("dispatch_payload: Telegram failed HTTP %s", r.status_code)
    except Exception:
        logger.error("dispatch_payload: Telegram error", exc_info=True)
```

**Step 5: Run all tests**

```bash
PYTHONPATH=/workspace pytest tests/ -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add src/adapters/discord.py tests/test_discord_render.py
git commit -m "feat: sendPhoto for Telegram when image_url present, chart link fallback"
```

---

### Task 8: Wire new fields into worker signal dispatch

**Files:**
- Modify: `src/worker.py` — wherever `format_signal()` is called and `dispatch_payload_async()` is called

**Step 1: Search for all format_signal calls**

```bash
grep -n "format_signal" src/worker.py
```

**Step 2: For each call site, pass new params**

Update calls to include:

```python
payload = notification_service.format_signal(
    signal,
    ai_result=ai_result,
    mode=run_mode,
    account_name=signal.get("account_name") or account_label,  # from broker_profiles
    image_url=signal.get("image_url"),
)
```

The `account_label` is whatever account label is already resolved in the worker at that point (look for `account_name`, `account_label`, or `broker_profile.get("label")` near the call site).

**Step 3: Run full tests**

```bash
PYTHONPATH=/workspace pytest tests/ -v
```

**Step 4: Commit**

```bash
git add src/worker.py
git commit -m "feat: pass image_url, account_name, bar_time to format_signal in worker"
```

---

### Task 9: End-to-end smoke test

**Step 1: Start the backend**

```bash
source .venv/bin/activate && PYTHONPATH=/workspace python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

**Step 2: Fire a test webhook**

```bash
curl -s -X POST http://localhost:8000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "XAUUSD",
    "side": "BUY",
    "entry": 2650.5,
    "sl": 2640.0,
    "tp": 2676.25,
    "size": 0.05,
    "bar_time": "2026-03-30T09:30:00Z",
    "image_url": "https://www.tradingview.com/x/test/"
  }' | python3 -m json.tool
```

Expected: `"schema_valid": true`, `"would_execute": true`

**Step 3: Load frontend `/notifications` page**

Verify:
- Only **Routing Panel** visible
- No whitelist or command log sections

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: notification upgrade complete — DEV-XX done"
```

---

## Summary of changes

| Task | Files | Est. time |
|---|---|---|
| 1 | Delete 3 command system files | 2 min |
| 2 | Remove TelegramPoller from worker | 3 min |
| 3 | Strip whitelist/command API routes | 3 min |
| 4 | Remove frontend panels | 3 min |
| 5 | Extend NotificationPayload + format_signal | 15 min |
| 6 | Upgrade Discord embed render | 8 min |
| 7 | Upgrade Telegram render + sendPhoto | 10 min |
| 8 | Wire new fields in worker | 8 min |
| 9 | Smoke test | 5 min |
