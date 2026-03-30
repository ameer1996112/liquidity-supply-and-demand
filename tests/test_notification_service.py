from src.services.notification_service import NotificationService
from src.services.notification_service import NotificationPayload

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
