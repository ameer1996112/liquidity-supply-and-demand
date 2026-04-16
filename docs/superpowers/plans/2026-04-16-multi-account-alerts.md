# Multi-Account Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Telegram and Discord alerts so multi-account notifications stay in shared destinations but always show a clear account-first identity and richer, better-structured alert details.

**Architecture:** Keep the existing centralized `NotificationService` and enrich `NotificationPayload` with a first-class account badge plus ordered sections for signal, close, and alert notifications. Update the Discord and Telegram renderers to consume the new structure while preserving the current routing model and fallback behavior.

**Tech Stack:** Python, FastAPI, pytest, Discord webhook payloads, Telegram Bot API HTML messages

---

## File Structure

- Modify: `src/services/notification_service.py`
  - Add first-class header and section support to `NotificationPayload`
  - Refactor `format_signal`, `format_close`, and `format_alert`
  - Add shared helpers for account badge, status line, and grouped fields
- Modify: `src/adapters/discord.py`
  - Update Discord embed rendering for account-first header and grouped fields
  - Update Telegram HTML rendering to match the same information hierarchy
- Modify: `tests/test_notification_service.py`
  - Add service-level tests for account badge fallback, grouped data, and missing optional blocks
- Modify: `tests/test_discord_render.py`
  - Add render tests for account-first embed output and grouped details
- Modify: `tests/test_telegram_formatting.py`
  - Add formatting tests for account-first Telegram output and missing data fallbacks
- Modify: `tests/test_telegram_render.py`
  - Keep dispatch coverage aligned with the updated Telegram content shape

### Task 1: Extend NotificationPayload For Structured Alerts

**Files:**
- Modify: `src/services/notification_service.py`
- Test: `tests/test_notification_service.py`

- [ ] **Step 1: Write the failing payload structure tests**

```python
from src.services.notification_service import NotificationService


def test_format_signal_sets_account_badge_and_status_line():
    svc = NotificationService()
    signal = {
        "id": 11,
        "symbol": "XAUUSD",
        "side": "BUY",
        "entry": 3345.2,
        "sl": 3338.0,
        "tp": 3359.8,
        "size": 0.40,
        "risk_usd": 120.0,
        "bar_time": "2026-03-30T13:30:00Z",
        "zone_type": "demand",
        "firm_name": "FTMO",
    }

    payload = svc.format_signal(signal, mode="paper", account_name="Funded Alpha")

    assert payload.account_name == "Funded Alpha"
    assert payload.account_badge == "ACC: Funded Alpha"
    assert payload.status_line == "Paper | FTMO"
    assert payload.sections[0]["name"] == "Trade"
    assert payload.sections[1]["name"] == "Risk"


def test_format_signal_uses_unknown_account_fallback():
    svc = NotificationService()
    signal = {"id": 12, "symbol": "EURUSD", "side": "SELL", "entry": 1.08, "sl": 1.085, "tp": 1.07}

    payload = svc.format_signal(signal)

    assert payload.account_name == "Unknown Account"
    assert payload.account_badge == "ACC: Unknown Account"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py -k "account_badge or status_line" -v`
Expected: FAIL with `AttributeError` or assertion failures because `NotificationPayload` does not yet expose `account_badge`, `status_line`, or `sections`.

- [ ] **Step 3: Add minimal structured payload support**

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
    image_url: Optional[str] = None
    account_name: Optional[str] = None
    bar_time: Optional[str] = None
    account_badge: str = "ACC: Unknown Account"
    status_line: Optional[str] = None
    sections: list[dict[str, Any]] = field(default_factory=list)
```

```python
def _resolve_account_name(explicit_account: Optional[str], payload_source: dict[str, Any]) -> str:
    return str(
        explicit_account
        or payload_source.get("account_name")
        or payload_source.get("account")
        or "Unknown Account"
    )


def _build_status_line(mode: str, source: dict[str, Any]) -> Optional[str]:
    mode_label = "Paper" if mode == "paper" else "Live" if mode == "live" else "Manual"
    venue = source.get("firm_name") or source.get("broker_name") or source.get("broker")
    parts = [mode_label]
    if venue:
        parts.append(str(venue))
    return " | ".join(parts) if parts else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py -k "account_badge or status_line" -v`
Expected: PASS for the new payload structure tests.

- [ ] **Step 5: Commit**

```bash
git add src/services/notification_service.py tests/test_notification_service.py
git commit -m "feat: add structured notification payload metadata"
```

### Task 2: Refactor Signal Formatting Into Ordered Sections

**Files:**
- Modify: `src/services/notification_service.py`
- Test: `tests/test_notification_service.py`

- [ ] **Step 1: Write the failing signal section tests**

```python
def test_format_signal_orders_trade_risk_ai_and_context_sections():
    svc = NotificationService()
    signal = {
        "id": 13,
        "symbol": "XAUUSD",
        "side": "BUY",
        "entry": 3345.2,
        "sl": 3338.0,
        "tp": 3359.8,
        "size": 0.40,
        "risk_usd": 120.0,
        "bar_time": "2026-03-30T13:30:00Z",
        "zone_type": "demand",
    }
    ai = {"decision": "GO", "rf_prob": 0.84, "reason": "London momentum aligned with demand retest"}

    payload = svc.format_signal(signal, ai_result=ai, mode="paper", account_name="Funded Alpha")

    assert [section["name"] for section in payload.sections] == ["Trade", "Risk", "AI", "Context"]
    assert payload.sections[0]["fields"]["Entry"] == "3345.2"
    assert payload.sections[1]["fields"]["Risk"] == "$120.00"
    assert payload.sections[2]["fields"]["AI"] == "GO"
    assert payload.sections[3]["fields"]["Session"].startswith("🌐")


def test_format_signal_omits_ai_section_when_missing():
    svc = NotificationService()
    signal = {"id": 14, "symbol": "EURUSD", "side": "BUY", "entry": 1.08, "sl": 1.07, "tp": 1.10}

    payload = svc.format_signal(signal, account_name="Funded Alpha")

    assert [section["name"] for section in payload.sections] == ["Trade"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py -k "orders_trade_risk_ai_and_context_sections or omits_ai_section_when_missing" -v`
Expected: FAIL because `format_signal` still emits a flat `fields` dict instead of sectioned output.

- [ ] **Step 3: Implement grouped signal formatting**

```python
trade_fields = {
    "Entry": f"{entry:.5g}" if entry else "N/A",
    "Stop Loss": sl_display if sl else "N/A",
    "Take Profit": tp_display if tp else "N/A",
    "R:R": f"1:{rr_ratio:.2f}" if rr_ratio else "N/A",
}

risk_fields: dict[str, str] = {}
if size:
    risk_fields["Lot Size"] = f"{size:.2f} lots"
if risk_usd:
    risk_fields["Risk"] = f"${risk_usd:.2f}"
if signal.get("zone_type"):
    risk_fields["Zone"] = str(signal["zone_type"]).title()

ai_fields: dict[str, str] = {}
if _ai_raw and decision:
    ai_fields["AI"] = decision
    ai_fields["Confidence"] = f"{rf_prob:.1f}%"
    if reason:
        ai_fields["Reason"] = reason

context_fields: dict[str, str] = {}
if session:
    context_fields["Session"] = session
if bar_time_display:
    context_fields["Bar Time"] = bar_time_display
if signal_id:
    context_fields["Signal"] = f"#{signal_id}"

sections = [{"name": "Trade", "fields": trade_fields}]
if risk_fields:
    sections.append({"name": "Risk", "fields": risk_fields})
if ai_fields:
    sections.append({"name": "AI", "fields": ai_fields})
if context_fields:
    sections.append({"name": "Context", "fields": context_fields})
```

```python
return NotificationPayload(
    type="signal",
    title=f"{side} Signal - {symbol}",
    description="Auto-executed (paper)" if mode == "paper" else "Execute manually",
    fields=_flatten_sections(sections),
    color=color,
    footer=f"Signal #{signal_id} | /close {signal_id} to close",
    metadata={"symbol": symbol, "side": side, "mode": mode, "ai_result": _ai_raw or {}},
    signal_id=signal_id,
    image_url=resolved_image_url,
    account_name=resolved_account,
    bar_time=bar_time_raw,
    account_badge=f"ACC: {resolved_account}",
    status_line=_build_status_line(mode, signal),
    sections=sections,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py -k "orders_trade_risk_ai_and_context_sections or omits_ai_section_when_missing" -v`
Expected: PASS and signal payloads now expose ordered sections.

- [ ] **Step 5: Commit**

```bash
git add src/services/notification_service.py tests/test_notification_service.py
git commit -m "feat: restructure signal notifications by section"
```

### Task 3: Refactor Close And Alert Formatting For Account-First Output

**Files:**
- Modify: `src/services/notification_service.py`
- Test: `tests/test_notification_service.py`

- [ ] **Step 1: Write the failing close and alert tests**

```python
def test_format_close_keeps_account_badge_and_summary_sections():
    svc = NotificationService()
    signal = {
        "id": 15,
        "symbol": "EURUSD",
        "side": "BUY",
        "account_name": "Funded Alpha",
        "entry": 1.08,
        "exit_price": 1.09,
        "pnl_usd": 248.50,
        "risk_usd": 125.0,
    }

    payload = svc.format_close(signal)

    assert payload.account_badge == "ACC: Funded Alpha"
    assert [section["name"] for section in payload.sections] == ["Summary", "Context"]
    assert payload.sections[0]["fields"]["PnL"] == "+$248.50"


def test_format_alert_keeps_account_badge_and_omits_empty_details():
    svc = NotificationService()
    alert = {
        "id": 51,
        "title": "Daily Loss Limit Hit",
        "message": "Trading paused for the session.",
        "severity": "warning",
        "alert_type": "risk_limit",
        "account_name": "Funded Alpha",
    }

    payload = svc.format_alert(alert)

    assert payload.account_badge == "ACC: Funded Alpha"
    assert [section["name"] for section in payload.sections] == ["Summary"]
    assert "Details" not in payload.fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py -k "close_keeps_account_badge or alert_keeps_account_badge" -v`
Expected: FAIL because `format_close` and `format_alert` do not yet populate `account_badge` or `sections`.

- [ ] **Step 3: Implement grouped close and alert formatting**

```python
summary_fields = {
    "Outcome": outcome,
    "PnL": f"{pnl_sign}${pnl:.2f}",
    "Entry": f"{entry:.5g}" if entry else "N/A",
    "Exit": f"{exit_price:.5g}" if exit_price else "N/A",
}
if commission:
    summary_fields["Commission"] = f"${commission:.2f}"
if swap:
    summary_fields["Swap"] = f"${swap:.2f}"
if risk_usd > 0:
    summary_fields["R Multiple"] = f"{sign}{r_multiple:.2f}R"

context_fields = {"Signal": f"#{signal_id}"} if signal_id else {}
sections = [{"name": "Summary", "fields": summary_fields}]
if context_fields:
    sections.append({"name": "Context", "fields": context_fields})
```

```python
severity_fields = {
    "Severity": severity.upper(),
    "Type": str(alert.get("alert_type", "")),
}
if alert.get("signal_id"):
    severity_fields["Signal"] = f"#{alert['signal_id']}"
if meta_lines:
    severity_fields["Details"] = meta_lines

return NotificationPayload(
    type="alert",
    title=alert.get("title", "Alert"),
    description=alert.get("message", ""),
    fields=_flatten_sections([{"name": "Summary", "fields": severity_fields}]),
    color=color,
    footer=f"Alert #{alert.get('id')} | /ack {alert.get('id')} to acknowledge",
    metadata=metadata,
    alert_id=alert.get("id"),
    account_name=_resolve_account_name(None, alert),
    account_badge=f"ACC: {_resolve_account_name(None, alert)}",
    sections=[{"name": "Summary", "fields": severity_fields}],
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py -k "close_keeps_account_badge or alert_keeps_account_badge" -v`
Expected: PASS and both formats follow the account-first structure.

- [ ] **Step 5: Commit**

```bash
git add src/services/notification_service.py tests/test_notification_service.py
git commit -m "feat: add account-first close and alert formatting"
```

### Task 4: Update Discord Embed Rendering

**Files:**
- Modify: `src/adapters/discord.py`
- Test: `tests/test_discord_render.py`

- [ ] **Step 1: Write the failing Discord render tests**

```python
from src.adapters.discord import _payload_to_discord_embed
from src.services.notification_service import NotificationPayload


def test_embed_uses_account_badge_and_status_line():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - XAUUSD",
        fields={"Entry": "3345.2"},
        color="buy",
        account_name="Funded Alpha",
        account_badge="ACC: Funded Alpha",
        status_line="Paper | FTMO",
        sections=[
            {"name": "Trade", "fields": {"Entry": "3345.2", "R:R": "1:2.10"}},
            {"name": "Risk", "fields": {"Risk": "$120.00"}},
        ],
        metadata={"symbol": "XAUUSD"},
    )

    embed = _payload_to_discord_embed(payload)

    assert embed["author"]["name"] == "ACC: Funded Alpha"
    assert embed["description"].startswith("Paper | FTMO")
    assert embed["fields"][0]["name"] == "Trade"
    assert "Entry" in embed["fields"][0]["value"]


def test_embed_falls_back_to_unknown_account_badge():
    payload = NotificationPayload(
        type="alert",
        title="Daily Loss Limit Hit",
        fields={"Severity": "WARNING"},
        color="warning",
        sections=[{"name": "Summary", "fields": {"Severity": "WARNING"}}],
    )

    embed = _payload_to_discord_embed(payload)

    assert embed["author"]["name"] == "ACC: Unknown Account"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_discord_render.py -k "account_badge and status_line" -v`
Expected: FAIL because the embed renderer still uses `Trading Bot` author and flat field names.

- [ ] **Step 3: Render sections as grouped Discord fields**

```python
def _section_to_embed_field(section: dict[str, Any]) -> dict[str, Any]:
    body = "\n".join(f"**{key}:** {value}" for key, value in section["fields"].items())
    return {"name": section["name"], "value": body, "inline": section["name"] in {"Trade", "Risk", "Context"}}
```

```python
embed: dict = {
    "title": payload.title,
    "color": color,
    "timestamp": datetime.utcnow().isoformat(),
    "fields": [_section_to_embed_field(section) for section in (payload.sections or [])],
}

embed["author"] = {"name": payload.account_badge or "ACC: Unknown Account"}

description_parts = []
if payload.status_line:
    description_parts.append(payload.status_line)
if payload.description:
    description_parts.append(payload.description)
if description_parts:
    embed["description"] = "\n".join(description_parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_discord_render.py -k "account_badge and status_line" -v`
Expected: PASS and the embed header now leads with the account badge.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/discord.py tests/test_discord_render.py
git commit -m "feat: render account-first discord notifications"
```

### Task 5: Update Telegram HTML Rendering

**Files:**
- Modify: `src/adapters/discord.py`
- Test: `tests/test_telegram_formatting.py`
- Test: `tests/test_telegram_render.py`

- [ ] **Step 1: Write the failing Telegram formatting tests**

```python
from src.adapters.discord import _payload_to_telegram_html
from src.services.notification_service import NotificationPayload


def test_telegram_html_starts_with_account_badge():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - XAUUSD",
        fields={"Entry": "3345.2"},
        color="buy",
        account_badge="ACC: Funded Alpha",
        status_line="Paper | FTMO",
        sections=[
            {"name": "Trade", "fields": {"Entry": "3345.2", "R:R": "1:2.10"}},
            {"name": "Risk", "fields": {"Risk": "$120.00", "Zone": "Demand"}},
        ],
        footer="Signal #13 | /close 13 to close",
    )

    html = _payload_to_telegram_html(payload)

    assert "ACC: Funded Alpha" in html
    assert "Paper | FTMO" in html
    assert "<b>Trade</b>" in html
    assert "<b>Risk</b>" in html


def test_telegram_html_uses_unknown_account_badge_by_default():
    payload = NotificationPayload(
        type="alert",
        title="Daily Loss Limit Hit",
        fields={"Severity": "WARNING"},
        color="warning",
        sections=[{"name": "Summary", "fields": {"Severity": "WARNING"}}],
    )

    html = _payload_to_telegram_html(payload)

    assert "ACC: Unknown Account" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_telegram_formatting.py -k "account_badge" -v`
Expected: FAIL because Telegram HTML does not currently render `account_badge`, `status_line`, or section headers.

- [ ] **Step 3: Implement section-aware Telegram rendering**

```python
lines = [f"<b>{clean(payload.account_badge or 'ACC: Unknown Account')}</b>", f"{header_emoji} <b>{title.upper()}</b>"]
if payload.status_line:
    lines.append(f"<i>{clean(payload.status_line)}</i>")
if payload.description:
    lines.append(clean(payload.description))
lines.append("")

for section in payload.sections or []:
    lines.append(f"<b>{clean(section['name'])}</b>")
    section_lines = [
        f"<b>{clean(key)}:</b> <code>{clean(value)}</code>"
        for key, value in section["fields"].items()
    ]
    lines.append("<blockquote>" + "\n".join(section_lines) + "</blockquote>")
    lines.append("")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_telegram_formatting.py tests/test_telegram_render.py -v`
Expected: PASS and Telegram output now starts with the account badge and grouped sections.

- [ ] **Step 5: Commit**

```bash
git add src/adapters/discord.py tests/test_telegram_formatting.py tests/test_telegram_render.py
git commit -m "feat: render account-first telegram notifications"
```

### Task 6: Preserve Compatibility And Backfill Regression Coverage

**Files:**
- Modify: `tests/test_notification_service.py`
- Modify: `tests/test_discord_render.py`
- Modify: `tests/test_telegram_formatting.py`

- [ ] **Step 1: Write the failing regression tests**

```python
def test_format_signal_keeps_image_url_and_metadata():
    svc = NotificationService()
    signal = {
        "id": 16,
        "symbol": "EURUSD",
        "side": "BUY",
        "entry": 1.08,
        "sl": 1.07,
        "tp": 1.10,
        "image_url": "https://www.tradingview.com/x/abc123/",
    }

    payload = svc.format_signal(signal, ai_result={"decision": "GO", "rf_prob": 0.9}, account_name="Funded Alpha")

    assert payload.image_url == "https://www.tradingview.com/x/abc123/"
    assert payload.metadata["symbol"] == "EURUSD"
    assert payload.metadata["ai_result"]["decision"] == "GO"


def test_embed_still_uses_chart_image_when_present():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - EURUSD",
        fields={"Entry": "1.08"},
        color="buy",
        account_badge="ACC: Funded Alpha",
        sections=[{"name": "Trade", "fields": {"Entry": "1.08"}}],
        image_url="https://www.tradingview.com/x/abc123/",
        metadata={"symbol": "EURUSD"},
    )

    embed = _payload_to_discord_embed(payload)

    assert embed["image"]["url"] == "https://www.tradingview.com/x/abc123/"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py -k "image_url and metadata" -v`
Expected: FAIL if any renderer or formatter refactor dropped existing image or metadata behavior.

- [ ] **Step 3: Adjust compatibility helpers**

```python
def _flatten_sections(sections: list[dict[str, Any]]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for section in sections:
        for key, value in section["fields"].items():
            flattened[key] = value
    return flattened
```

```python
symbol = (payload.metadata or {}).get("symbol", "")
if payload.image_url:
    embed["image"] = {"url": payload.image_url}
else:
    flag_url = _get_symbol_thumbnail_url(symbol)
    if flag_url:
        embed["thumbnail"] = {"url": flag_url}
```

- [ ] **Step 4: Run the full notification suite**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py tests/test_telegram_render.py -v`
Expected: PASS for the notification formatting and channel rendering test suite.

- [ ] **Step 5: Commit**

```bash
git add src/services/notification_service.py src/adapters/discord.py tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py tests/test_telegram_render.py
git commit -m "test: cover multi-account notification rendering regressions"
```

### Task 7: Final Verification

**Files:**
- Modify: none
- Test: `tests/test_notification_service.py`
- Test: `tests/test_discord_render.py`
- Test: `tests/test_telegram_formatting.py`
- Test: `tests/test_telegram_render.py`

- [ ] **Step 1: Run targeted notification tests**

Run: `PYTHONPATH=. pytest tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py tests/test_telegram_render.py -v`
Expected: PASS

- [ ] **Step 2: Run the standard backend test suite**

Run: `PYTHONPATH=. pytest tests/ -v`
Expected: PASS except for any already-documented unrelated pre-existing failures outside this feature scope.

- [ ] **Step 3: Sanity-check code quality**

Run: `ruff check src/services/notification_service.py src/adapters/discord.py tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py tests/test_telegram_render.py`
Expected: PASS or only pre-existing unrelated warnings not introduced by this work.

- [ ] **Step 4: Review changed files**

Run: `git diff -- src/services/notification_service.py src/adapters/discord.py tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py tests/test_telegram_render.py`
Expected: Diff shows account-first formatting, grouped sections, and regression coverage only.

- [ ] **Step 5: Final commit**

```bash
git add src/services/notification_service.py src/adapters/discord.py tests/test_notification_service.py tests/test_discord_render.py tests/test_telegram_formatting.py tests/test_telegram_render.py
git commit -m "feat: upgrade multi-account telegram and discord alerts"
```
