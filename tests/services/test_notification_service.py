from src.services.notification_service import NotificationService


def test_format_signal_prefers_setup_evidence_image_url() -> None:
    payload = NotificationService().format_signal(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "sl": 0.7148,
            "tp": 0.7172,
            "size": 0.25,
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url == "https://provider.example/setup.png"


def test_format_close_reuses_opening_setup_evidence_image() -> None:
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

    assert payload.image_url == "https://provider.example/setup.png"
