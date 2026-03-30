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

def test_format_digest():
    svc = NotificationService()
    stats = {
        "net_pnl": 150.50,
        "gross_pnl": 160.0,
        "commission": -9.5,
        "swap": 0.0,
        "total_trades": 5,
        "winning_trades": 3,
        "best_trade_pnl": 100.0,
        "worst_trade_pnl": -50.0,
        "win_rate_pct": 60.0
    }
    
    payload = svc.format_digest(account_name="Trading Account", stats=stats)
    
    # Should be correctly formatted as NotificationPayload
    assert payload.type == "info"
    assert "Daily Performance Report" in payload.title
    assert payload.account_name == "Trading Account"
    
    # Verify the stats are printed
    assert "Net PnL" in payload.fields
    assert payload.fields["Net PnL"].startswith("+$150.50")
    
    assert "Win Rate" in payload.fields
    assert "60.0%" in payload.fields["Win Rate"]
    
    assert "Best Trade" in payload.fields
    assert "+$100.00" in payload.fields["Best Trade"]
