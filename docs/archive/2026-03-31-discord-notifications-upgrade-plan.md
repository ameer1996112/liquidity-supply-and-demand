# Discord Notifications Upgrade — Implementation Plan

**Spec:** docs/superpowers/specs/2026-03-31-discord-notifications-upgrade-design.md
**Date:** 2026-03-31

---

## Task 1: Add `_get_symbol_thumbnail_url()` helper to `discord.py`

**File:** `src/adapters/discord.py`

Add after the existing `get_pip_divisor()` function:

```python
_CURRENCY_FLAG_MAP: dict[str, str] = {
    "EUR": "eu", "GBP": "gb", "USD": "us", "JPY": "jp",
    "CAD": "ca", "AUD": "au", "NZD": "nz", "CHF": "ch",
    "NAS": "us", "SPX": "us", "DJI": "us", "US3": "us",
}

def _get_symbol_thumbnail_url(symbol: str, image_url: Optional[str] = None) -> Optional[str]:
    """Return thumbnail URL: chart screenshot → currency flag → None."""
    if image_url:
        return image_url
    symbol = symbol.upper()
    for prefix, code in _CURRENCY_FLAG_MAP.items():
        if symbol.startswith(prefix):
            return f"https://flagcdn.com/w80/{code}.png"
    return None
```

**Verify:** No import changes needed (`Optional` already imported).

---

## Task 2: Upgrade `_payload_to_discord_embed()` in `discord.py`

**File:** `src/adapters/discord.py`

Replace the existing `_payload_to_discord_embed()` function body with the upgraded version:

```python
def _payload_to_discord_embed(payload: NotificationPayload) -> dict:
    """Render a NotificationPayload as a premium Discord embed dict."""
    color = COLOR_MAP.get(payload.color, 0x3B82F6)

    # Build fields — inline for everything except known wide fields
    wide_fields = {"🧠 AI Analysis", "Details", "Reason"}
    fields = [
        {"name": k, "value": str(v), "inline": k not in wide_fields}
        for k, v in payload.fields.items()
    ]

    embed: dict = {
        "title": payload.title,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": fields,
    }

    # Author block
    author_name = "Trading Bot"
    if payload.account_name:
        author_name += f" · {payload.account_name}"
    embed["author"] = {"name": author_name}

    # Thumbnail: chart screenshot → currency flag → omit
    symbol = payload.metadata.get("symbol", "") if payload.metadata else ""
    thumb_url = _get_symbol_thumbnail_url(symbol, payload.image_url)
    if thumb_url:
        embed["thumbnail"] = {"url": thumb_url}

    if payload.description:
        embed["description"] = payload.description
    if payload.footer:
        embed["footer"] = {"text": payload.footer}

    # image (full-width chart) is separate from thumbnail
    if payload.image_url:
        embed["image"] = {"url": payload.image_url}

    return embed
```

**Verify:** Run `pytest tests/test_discord_render.py -x` — existing tests must still pass (image_url test).

---

## Task 3: Split AI Analysis into compact fields in `notification_service.py`

**File:** `src/services/notification_service.py`

In `format_signal()`, replace the block that adds `"🧠 AI Analysis"`:

```python
        # AI analysis section — compact inline fields
        ai_section = _format_ai_analysis(ai_result or signal.get("ai_reasoning"))
        if ai_section:
            fields["🧠 AI Analysis"] = ai_section
```

With:

```python
        # AI compact inline fields (Decision + Confidence only in embed)
        _ai_raw = ai_result or signal.get("ai_reasoning")
        if _ai_raw:
            decision = str(_ai_raw.get("decision", "")).upper()
            if decision:
                try:
                    rf_prob = float(_ai_raw.get("rf_prob") or _ai_raw.get("confidence") or 0) * 100
                except Exception:
                    rf_prob = 0.0
                decision_emoji = "✅" if decision == "GO" else "⛔"
                fields["🧠 AI Decision"] = f"{decision_emoji} {decision}"
                fields["🎯 Confidence"] = f"{rf_prob:.1f}%"
```

Also store the full ai_result in payload metadata for thread posting:

In the `return NotificationPayload(...)` call, update `metadata`:
```python
            metadata={"symbol": symbol, "side": side, "mode": mode, "ai_result": _ai_raw or {}},
```

**Verify:** Run `pytest tests/ -x -k "notification"` — must pass.

---

## Task 4: Add R Multiple to `format_close()` in `notification_service.py`

**File:** `src/services/notification_service.py`

In `format_close()`, after building `fields`, add R Multiple when `risk_usd` is available:

```python
        risk_usd = float(signal.get("risk_usd") or signal.get("risk_amount") or 0)
        if risk_usd > 0:
            r_multiple = pnl / risk_usd
            sign = "+" if r_multiple >= 0 else ""
            fields["📊 R Multiple"] = f"{sign}{r_multiple:.2f}R"
```

Insert this block after the `if swap:` block (around line 222).

**Verify:** Run `pytest tests/ -x -k "close"` — must pass.

---

## Task 5: Post full AI reasoning to Discord thread in `dispatch_payload()`

**File:** `src/adapters/discord.py`

In `dispatch_payload()`, after the Discord signal embed is posted and a thread exists, post full AI reasoning as a thread reply. Find the section where Discord is dispatched and add:

```python
    # After posting signal embed — post full AI reasoning to thread if available
    # (thread_id is set on the signal via the existing create_discord_thread flow)
    thread_id = payload.metadata.get("discord_thread_id") if payload.metadata else None
    ai_result = payload.metadata.get("ai_result") if payload.metadata else None
    if thread_id and ai_result and payload.type == "signal":
        full_ai = _format_ai_analysis(ai_result)
        if full_ai:
            ai_embed = {
                "title": "🧠 Full AI Analysis",
                "description": full_ai,
                "color": 0x5865F2,
                "timestamp": datetime.utcnow().isoformat(),
            }
            post_to_discord_thread(thread_id, ai_embed)
```

**Verify:** No test needed for this path (thread_id is optional — gracefully skipped when absent).

---

## Task 6: Update tests in `test_discord_render.py`

**File:** `tests/test_discord_render.py`

Add tests for:
1. Author block present in embed
2. Thumbnail URL set when symbol is EURUSD (no image_url)
3. Thumbnail URL set to chart URL when image_url present
4. AI compact fields (Decision + Confidence) present instead of big AI Analysis block
5. R Multiple present in close embed

```python
from src.adapters.discord import _payload_to_discord_embed, _get_symbol_thumbnail_url
from src.services.notification_service import NotificationService, NotificationPayload

def test_embed_has_author_block():
    payload = NotificationPayload(
        type="signal", title="📈 BUY EURUSD", fields={},
        color="buy", account_name="FTMO-50K",
        metadata={"symbol": "EURUSD", "side": "BUY", "mode": "manual"}
    )
    embed = _payload_to_discord_embed(payload)
    assert "author" in embed
    assert "FTMO-50K" in embed["author"]["name"]

def test_embed_thumbnail_uses_flag_for_eurusd():
    assert _get_symbol_thumbnail_url("EURUSD", None) == "https://flagcdn.com/w80/eu.png"

def test_embed_thumbnail_uses_image_url_when_present():
    url = "https://www.tradingview.com/x/abc123/"
    assert _get_symbol_thumbnail_url("EURUSD", url) == url

def test_embed_thumbnail_none_for_xauusd():
    assert _get_symbol_thumbnail_url("XAUUSD", None) is None

def test_signal_has_compact_ai_fields():
    svc = NotificationService()
    signal = {"id": 1, "symbol": "EURUSD", "side": "BUY", "entry": 1.08, "sl": 1.07, "tp": 1.10}
    ai = {"decision": "GO", "rf_prob": 0.784, "reason": "Strong trend", "rules": []}
    payload = svc.format_signal(signal, ai_result=ai)
    assert "🧠 AI Decision" in payload.fields
    assert "🎯 Confidence" in payload.fields
    assert "🧠 AI Analysis" not in payload.fields

def test_close_has_r_multiple():
    svc = NotificationService()
    signal = {"id": 1, "symbol": "EURUSD", "side": "BUY",
              "pnl_usd": 248.50, "risk_usd": 125.0}
    payload = svc.format_close(signal)
    assert "📊 R Multiple" in payload.fields
    assert "1.99R" in payload.fields["📊 R Multiple"]
```

**Verify:** `pytest tests/test_discord_render.py -v` — all 6 new tests + 2 existing must pass.

---

## Task 7: Commit

```bash
node scripts/jira-agent.js smart-create "Upgrade Discord notification embeds to Discord-native premium layout" Task
# Use returned ticket key in commit message
git add src/adapters/discord.py src/services/notification_service.py tests/test_discord_render.py
git commit -m "feat: [DEV-XX] upgrade Discord embeds — author block, flag thumbnails, compact AI, R multiple"
```
