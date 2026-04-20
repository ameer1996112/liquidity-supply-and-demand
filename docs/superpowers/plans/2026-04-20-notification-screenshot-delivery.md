# Notification Screenshot Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Discord and Telegram trade notifications attach screenshots only when an existing image URL is already present in trade data, and stop reusing open/setup screenshots for close notifications.

**Architecture:** Keep the change narrowly inside the notification formatting and delivery flow. The formatter decides whether an open or close notification has an attachable image URL, and the existing Discord/Telegram send path continues to branch only on `payload.image_url`. Remove the extra generated-chart delivery branch from trade-open logic so no screenshot is ever sent unless persisted trade data already contains one.

**Tech Stack:** Python, pytest, FastAPI service layer, Discord webhook/Bot API adapter, Telegram Bot API adapter

---

## File Map

- Modify: `src/services/notification_service.py`
  Purpose: add a dedicated close-image resolver, stop close notifications from falling back to setup/open screenshots, and tighten close message formatting.

- Modify: `src/logic.py`
  Purpose: remove the generated chart notification branch from trade-open flow so notification screenshots are data-driven only.

- Modify: `tests/services/test_notification_service.py`
  Purpose: verify open image resolution still works, close notifications only use dedicated close-image fields, and close formatting stays readable without screenshots.

- Modify: `tests/test_telegram_render.py`
  Purpose: verify Telegram only uses `sendPhoto` when `payload.image_url` exists and keeps text-only behavior otherwise.

- Optional verify-only read: `tests/test_discord_render.py`
  Purpose: confirm existing embed image behavior still matches the new contract without needing implementation changes.

---

### Task 1: Lock Down Screenshot Resolution Rules in Tests

**Files:**
- Modify: `tests/services/test_notification_service.py`
- Test: `tests/services/test_notification_service.py`

- [ ] **Step 1: Write the failing tests for close-image resolution**

Add these tests near the existing notification service image tests:

```python
def test_format_close_uses_dedicated_close_image_url() -> None:
    payload = NotificationService().format_close(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "exit_price": 0.7172,
            "pnl_usd": 42.5,
            "close_image_url": "https://provider.example/close.png",
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url == "https://provider.example/close.png"


def test_format_close_does_not_reuse_opening_setup_evidence_image() -> None:
    payload = NotificationService().format_close(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "exit_price": 0.7172,
            "pnl_usd": 42.5,
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url is None
```

- [ ] **Step 2: Write the failing test for close formatting**

Add a formatting test that checks the close message stays compact and intentional:

```python
def test_format_close_keeps_clean_summary_and_context_sections() -> None:
    payload = NotificationService().format_close(
        {
            "id": 46,
            "symbol": "XAUUSD",
            "side": "SELL",
            "fill_price": 4796.0,
            "exit_price": 4802.8,
            "pnl_usd": -329.81,
            "commission": -0.58,
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "account_name": "ACG-DEMO-2",
        }
    )

    section_names = [section["name"] for section in payload.sections]
    assert section_names == ["Summary", "Context"]
    assert payload.fields["Outcome"] == "LOSS"
    assert payload.fields["PnL"] == "-$329.81"
    assert payload.fields["Signal"] == "#46"
```

- [ ] **Step 3: Run the targeted test file to verify it fails**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. pytest tests/services/test_notification_service.py -q
```

Expected:
- FAIL on the new close-image tests because `format_close()` still reuses `_resolve_setup_image_url(signal)`
- existing open-image tests should continue to pass

- [ ] **Step 4: Commit the failing-test checkpoint**

```bash
git add tests/services/test_notification_service.py
git commit -m "test: lock notification screenshot rules"
```

---

### Task 2: Implement Data-Driven Open/Close Image Resolution

**Files:**
- Modify: `src/services/notification_service.py`
- Test: `tests/services/test_notification_service.py`

- [ ] **Step 1: Add a dedicated close-image resolver**

Insert a new helper next to `_resolve_setup_image_url(...)`:

```python
    def _resolve_close_image_url(
        self,
        signal: dict[str, Any],
        explicit_image_url: Optional[str] = None,
    ) -> Optional[str]:
        if explicit_image_url:
            return explicit_image_url

        for key in ("close_image_url", "exit_image_url", "close_screenshot_url"):
            value = signal.get(key)
            if value:
                return str(value)

        close_evidence = signal.get("close_evidence")
        if isinstance(close_evidence, dict):
            focus_image = close_evidence.get("focus_image")
            if isinstance(focus_image, dict) and focus_image.get("url"):
                return str(focus_image["url"])

        return None
```

- [ ] **Step 2: Update `format_close()` to use only the dedicated close-image resolver**

Change the returned payload block from:

```python
            image_url=self._resolve_setup_image_url(signal),
```

to:

```python
            image_url=self._resolve_close_image_url(signal),
```

and keep the rest of the close payload data flow intact.

- [ ] **Step 3: Tighten the close title so it reads like a report**

Replace the current title construction:

```python
            title=f"[{strategy_badge}] Trade Closed - {symbol} {side}" if strategy_badge else f"Trade Closed - {symbol} {side}",
```

with:

```python
            title=(
                f"[{strategy_badge}] {symbol} {side} Closed"
                if strategy_badge
                else f"{symbol} {side} Closed"
            ),
```

This preserves the existing data but removes the more mechanical “Trade Closed -” phrasing.

- [ ] **Step 4: Re-run the notification service tests**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. pytest tests/services/test_notification_service.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit the formatter implementation**

```bash
git add src/services/notification_service.py tests/services/test_notification_service.py
git commit -m "feat: use dedicated close screenshots in notifications"
```

---

### Task 3: Verify Telegram Delivery Only Sends Photos When `image_url` Exists

**Files:**
- Modify: `tests/test_telegram_render.py`
- Verify-only read: `src/adapters/discord.py`
- Test: `tests/test_telegram_render.py`

- [ ] **Step 1: Update Telegram tests to cover close-only screenshot behavior**

Add this regression test:

```python
@patch("src.adapters.discord.requests.post")
@patch("src.adapters.discord.get_settings")
def test_dispatch_payload_telegram_close_without_image_stays_text_only(mock_get_settings, mock_post):
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TELEGRAM_TOKEN"
    mock_settings.telegram_chat_id = "12345"
    mock_settings.discord_webhook_url = None
    mock_settings.discord_alerts_webhook_url = None
    mock_get_settings.return_value = mock_settings

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"message_id": 999}}
    mock_post.return_value = mock_resp

    payload = NotificationPayload(
        type="close",
        title="XAUUSD SELL Closed",
        fields={"Outcome": "LOSS", "PnL": "-$329.81"},
        color="loss",
        image_url=None,
    )

    mock_routing = MagicMock()
    mock_routing.get_routing.return_value = {"telegram_enabled": True, "discord_enabled": False}

    dispatch_payload(payload, notification_service=mock_routing)

    mock_post.assert_called_once()
    args, _kwargs = mock_post.call_args
    assert "sendMessage" in args[0]
```

- [ ] **Step 2: Run the Telegram render tests**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. pytest tests/test_telegram_render.py -q
```

Expected:
- PASS

- [ ] **Step 3: Commit the Telegram regression coverage**

```bash
git add tests/test_telegram_render.py
git commit -m "test: keep telegram close notifications text-only without screenshots"
```

---

### Task 4: Remove Generated Chart Delivery From Trade-Open Flow

**Files:**
- Modify: `src/logic.py`
- Test: `tests/services/test_notification_service.py`

- [ ] **Step 1: Remove the generated-chart block from open notification flow**

Delete the `chart_notifications_enabled` branch that imports and calls:

```python
from src.services.chart_generator import generate_chart_async
from src.adapters.discord import send_chart_to_channels_async
```

and this execution path:

```python
            _chart_png = generate_chart_async(
                symbol=_chart_symbol,
                side=_signal_record.get("side", "BUY"),
                entry=float(_signal_record.get("fill_price") or _signal_record.get("entry") or 0),
                sl=float(_signal_record.get("sl") or 0),
                tp=float(_signal_record.get("tp") or 0),
                signal_id=alert_id,
                zone_type=_signal_record.get("zone_type"),
            )
            if _chart_png:
                send_chart_to_channels_async(_chart_png, alert_id, supabase_client=_sb)
```

The `NotificationService.format_signal(..., image_url=_signal_record.get("image_url"))` path remains the only screenshot path for opens.

- [ ] **Step 2: Run the focused notification test suite**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. pytest tests/services/test_notification_service.py tests/test_telegram_render.py tests/test_discord_render.py -q
```

Expected:
- PASS

- [ ] **Step 3: Commit the removal of generated screenshot fallback**

```bash
git add src/logic.py tests/services/test_notification_service.py tests/test_telegram_render.py tests/test_discord_render.py
git commit -m "feat: stop generated chart fallback for trade notifications"
```

---

### Task 5: End-to-End Verification

**Files:**
- Verify: `src/services/notification_service.py`
- Verify: `src/logic.py`
- Verify: `tests/services/test_notification_service.py`

- [ ] **Step 1: Run all notification-related tests together**

Run:

```bash
source ./venv/bin/activate
PYTHONPATH=. pytest \
  tests/services/test_notification_service.py \
  tests/test_notification_service.py \
  tests/test_discord_render.py \
  tests/test_telegram_render.py \
  -q
```

Expected:
- PASS

- [ ] **Step 2: Sanity-check the diff**

Run:

```bash
git diff -- src/services/notification_service.py src/logic.py tests/services/test_notification_service.py tests/test_telegram_render.py tests/test_discord_render.py
```

Expected:
- `format_signal()` still resolves open/setup screenshots
- `format_close()` only resolves dedicated close screenshots
- no generated chart notification block remains in `src/logic.py`

- [ ] **Step 3: Prepare deploy note**

Use this release note in the PR or handoff:

```text
Discord and Telegram notifications now attach screenshots only when an existing image URL is already present in trade data. Open notifications use persisted setup screenshots, close notifications use only dedicated close-image fields, and generated chart fallback delivery has been removed.
```

- [ ] **Step 4: Final commit if verification required code/test touch-ups**

```bash
git add src/services/notification_service.py src/logic.py tests/services/test_notification_service.py tests/test_telegram_render.py tests/test_discord_render.py
git commit -m "chore: finalize notification screenshot delivery verification"
```

---

## Self-Review

- Spec coverage:
  - open notifications use only existing screenshots: covered by Tasks 1, 2, and 4
  - close notifications use only dedicated close screenshots: covered by Tasks 1 and 2
  - no chart generation fallback: covered by Task 4
  - cleaner close notification presentation: covered by Task 2
  - Discord/Telegram media delivery only when image exists: covered by Task 3 and Task 5

- Placeholder scan:
  - all tasks include exact file paths, commands, and concrete code snippets

- Type consistency:
  - `NotificationPayload.image_url` remains the single delivery toggle
  - close-image source keys are consistently named `close_image_url`, `exit_image_url`, `close_screenshot_url`, and `close_evidence.focus_image.url`

