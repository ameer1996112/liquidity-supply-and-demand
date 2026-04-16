import pytest
from src.services.notification_service import NotificationPayload
from src.adapters.discord import _payload_to_telegram_html

def test_telegram_html_redesign():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - USDJPY",
        color="buy",
        description="Execute manually",
        account_badge="ACC: ACG-DEMO-2",
        status_line="Manual | Demo",
        fields={
            "Entry": "159.75",
            "Stop Loss": "159.81 (6.1 pips)",
            "Take Profit": "159.56 (18.3 pips)",
            "R:R": "1:3.00",
        },
        sections=[
            {"name": "Trade", "fields": {
                "Entry": "159.75",
                "Stop Loss": "159.81 (6.1 pips)",
                "Take Profit": "159.56 (18.3 pips)",
                "R:R": "1:3.00",
            }},
            {"name": "Risk", "fields": {"Lot Size": "3.27 lots"}},
            {"name": "AI", "fields": {
                "AI": "NO_GO",
                "Confidence": "52.6%",
                "Reason": "Quant blocked",
            }},
        ],
        footer="Signal #123 | /close 123 to close"
    )
    
    html = _payload_to_telegram_html(payload)
    
    # Assert Discord artifacts are stripped
    assert "**" not in html, f"Markdown artifacts leaking into Telegram HTML: {html}"
    
    # Assert structural blockquotes are present
    assert "<blockquote>" in html, f"Missing blockquote structuring in: {html}"
    
    # Assert specific mappings exist
    assert "ACC: ACG-DEMO-2" in html, f"Account badge missing in: {html}"
    assert "Manual | Demo" in html, f"Status line missing in: {html}"
    assert "<b>Trade</b>" in html, f"Trade section missing in: {html}"
    assert "<b>AI</b>" in html, f"AI section missing in: {html}"
    assert "<code>159.75</code>" in html, f"Prices not monospaced in: {html}"
    assert "<b>Stop Loss:</b>" in html or "<b>STOP LOSS:</b>" in html
    
    print("Generated HTML:")
    print(html)


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
