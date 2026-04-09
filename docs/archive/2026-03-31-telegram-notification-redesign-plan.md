# Telegram Notification Redesign Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Transform the Telegram notification payloads from inherited Discord markdown into a premium, eye-catching, Telegram-native HTML layout using blockquotes and monospace styling.

**Architecture:** Modify `_payload_to_telegram_html` in `src/adapters/discord.py` to intercept fields by name instead of a generic loop, formatting them with custom emojis and HTML tags (`<blockquote>`, `<code>`).

**Tech Stack:** Python, Telegram HTML Parse Mode

---

### Task 1: Update `_payload_to_telegram_html`

**Files:**
- Modify: `src/adapters/discord.py`

**Step 1: Write the failing test**

```python
# Create tests/test_telegram_formatting.py
import pytest
from src.services.notification_service import NotificationPayload
from src.adapters.discord import _payload_to_telegram_html

def test_telegram_html_redesign():
    payload = NotificationPayload(
        type="signal",
        title="📈 New BUY Signal — #123",
        color="buy",
        description="**Execute manually**",
        fields={
            "Symbol": "**USDJPY**",
            "Entry": "159.75",
            "Stop Loss": "159.81 (6.1 pips)",
            "Take Profit": "159.56 (18.3 pips)",
            "R:R": "1:3.00",
            "Lot Size": "3.27 lots",
            "Account": "ACG-DEMO-2",
            "🧠 AI Analysis": "**Decision:** NO_GO\n**Confidence:** 52.6%\n**Reason:** Quant blocked"
        },
        footer="Signal #123 | /close 123 to close"
    )
    
    html = _payload_to_telegram_html(payload)
    
    # Assert Discord artifacts are stripped
    assert "**" not in html
    # Assert structural blockquotes are present
    assert "<blockquote>" in html
    # Assert new emojis are present
    assert "🎯" in html
    assert "<code>159.75</code>" in html
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/workspace pytest tests/test_telegram_formatting.py -v`
Expected: FAIL due to missing file, or if file exists, assertion errors (no blockquotes, asterisks present)

**Step 3: Write minimal implementation**

Modify `src/adapters/discord.py` -> `_payload_to_telegram_html` function.

```python
import re

def _payload_to_telegram_html(payload: NotificationPayload) -> str:
    """Render a NotificationPayload as a premium Telegram HTML string."""
    
    # Strip Discord markdown ** from all strings safely
    def clean(val: str) -> str:
        return str(val).replace("**", "")

    # Header
    title = clean(payload.title)
    if "GUILD" in title.upper() or "ALERT" in title.upper():
        header_emoji = "⚠️"
    elif "BUY" in title.upper() or "WIN" in title.upper():
        header_emoji = "🟢"
    elif "SELL" in title.upper() or "LOSS" in title.upper():
        header_emoji = "🔴"
    else:
        header_emoji = "🚨"

    lines = [f"{header_emoji} <b>{title.upper()}</b>"]
    
    if payload.metadata and "symbol" in payload.metadata:
        symbol = clean(payload.metadata["symbol"])
        lines.append(f"<b><a href=\"#\">#{symbol}</a></b>")
    elif "Symbol" in payload.fields:
        symbol = clean(payload.fields["Symbol"])
        lines.append(f"<b><a href=\"#\">#{symbol}</a></b>")

    lines.append("")

    # Separate Fields into Trading Data vs AI/Other
    trade_fields = []
    ai_field = None
    
    for k, v in payload.fields.items():
        if k == "Symbol":
            continue
        if "AI Analysis" in k:
            ai_field = v
            continue
            
        # Icon mapping
        icon = "▪️"
        if "Entry" in k: icon = "🎯"
        elif "Take Profit" in k: icon = "💰"
        elif "Stop Loss" in k: icon = "🛑"
        elif "R:R" in k or "Outcome" in k: icon = "⚖️"
        elif "Lot Size" in k or "Risk" in k: icon = "📊"
        elif "Account" in k or "Mode" in k: icon = "🏦"
        elif "Session" in k or "Time" in k: icon = "🕒"
        
        # Wrap the value in code block if it looks like data
        clean_v = clean(v)
        # Assuming most numbers/data look better in code tags
        trade_fields.append(f"<b>{icon} {k}:</b> <code>{clean_v}</code>")

    # Construct the Quote Block
    if trade_fields:
        lines.append("<blockquote>" + "\n".join(trade_fields) + "</blockquote>")
        lines.append("")

    # Construct AI Block
    if ai_field:
        lines.append("<b>🧠 AI GUARDIAN</b>")
        ai_clean = clean(ai_field)
        
        # Split AI reasoning fields if possible
        ai_lines = []
        for line in ai_clean.split("\n"):
            line = line.strip()
            if not line: continue
            if "Decision:" in line:
                ai_lines.append(f"<b>⛔️ DECISION:</b> {line.replace('Decision:', '').strip()}")
            elif "Confidence:" in line:
                ai_lines.append(f"<b>🛡️ CONFIDENCE:</b> <code>{line.replace('Confidence:', '').strip()}</code>")
            elif "Reason:" in line:
                ai_lines.append(f"<b>⚠️ REASON:</b>\n<pre>{line.replace('Reason:', '').strip()}</pre>")
            else:
                ai_lines.append(line)
                
        lines.append("<blockquote>" + "\n".join(ai_lines) + "</blockquote>")

    if payload.footer:
        lines.append(f"\n<i>{clean(payload.footer)}</i>")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=/workspace pytest tests/test_telegram_formatting.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_telegram_formatting.py src/adapters/discord.py
git commit -m "feat(notifications): redesign Telegram HTML payloads to use native blockquotes and monospace"
```
