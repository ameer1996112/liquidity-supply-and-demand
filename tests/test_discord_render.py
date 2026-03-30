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
