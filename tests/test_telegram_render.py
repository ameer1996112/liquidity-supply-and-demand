from unittest.mock import patch, MagicMock
from src.adapters.discord import dispatch_payload
from src.services.notification_service import NotificationPayload

@patch("src.adapters.discord.requests.post")
@patch("src.adapters.discord.get_settings")
def test_dispatch_payload_telegram_send_photo_when_image_present(mock_get_settings, mock_post):
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
        type="signal",
        title="📈 BUY XAUUSD",
        fields={"Symbol": "XAUUSD"},
        color="buy",
        image_url="https://www.tradingview.com/x/abc123/"
    )
    
    mock_routing = MagicMock()
    mock_routing.get_routing.return_value = {"telegram_enabled": True, "discord_enabled": False}

    dispatch_payload(payload, notification_service=mock_routing)

    assert mock_post.call_count == 2

    first_args, first_kwargs = mock_post.call_args_list[0]
    assert "sendMessage" in first_args[0]
    assert "📈 BUY XAUUSD" in first_kwargs["json"]["text"]

    second_args, second_kwargs = mock_post.call_args_list[1]
    assert "sendPhoto" in second_args[0]
    assert second_kwargs["json"]["photo"] == "https://www.tradingview.com/x/abc123/"
    assert "caption" in second_kwargs["json"]
    assert "Setup Evidence" in second_kwargs["json"]["caption"]

@patch("src.adapters.discord.requests.post")
@patch("src.adapters.discord.get_settings")
def test_dispatch_payload_telegram_send_message_when_no_image(mock_get_settings, mock_post):
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
        type="signal",
        title="📈 BUY EURUSD",
        fields={"Symbol": "EURUSD"},
        color="buy",
        image_url=None
    )
    
    mock_routing = MagicMock()
    mock_routing.get_routing.return_value = {"telegram_enabled": True, "discord_enabled": False}

    dispatch_payload(payload, notification_service=mock_routing)

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "sendMessage" in args[0]
    
    json_payload = kwargs.get("json")
    assert "text" in json_payload
    assert "📈 BUY EURUSD" in json_payload["text"]


@patch("src.adapters.discord.requests.post")
@patch("src.adapters.discord.get_settings")
def test_dispatch_payload_telegram_caption_uses_setup_evidence_summary(mock_get_settings, mock_post):
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
        title="Trade Closed - GBPUSD SELL",
        fields={"Outcome": "WIN"},
        color="win",
        image_url="https://provider.example/setup.png",
        metadata={
            "setup_evidence_summary": {
                "status_label": "Setup Evidence: DEGRADED",
                "focus_zone_label": "SUPPLY A+",
                "has_image": True,
            }
        },
    )

    mock_routing = MagicMock()
    mock_routing.get_routing.return_value = {"telegram_enabled": True, "discord_enabled": False}

    dispatch_payload(payload, notification_service=mock_routing)

    second_args, second_kwargs = mock_post.call_args_list[1]
    assert "sendPhoto" in second_args[0]
    assert "SUPPLY A+" in second_kwargs["json"]["caption"]
    assert "DEGRADED" in second_kwargs["json"]["caption"]
