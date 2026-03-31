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
    assert "**" not in html, f"Markdown artifacts leaking into Telegram HTML: {html}"
    
    # Assert structural blockquotes are present
    assert "<blockquote>" in html, f"Missing blockquote structuring in: {html}"
    
    # Assert specific mappings exist
    assert "🎯" in html, f"Entry emoji missing in: {html}"
    assert "<code>159.75</code>" in html, f"Prices not monospaced in: {html}"
    assert "<b>🛑 Stop Loss:</b>" in html or "<b>🛑 STOP LOSS:</b>" in html or "🛑" in html
    
    print("Generated HTML:")
    print(html)
