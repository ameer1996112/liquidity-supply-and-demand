from src.services.notification_service import NotificationService
from src.services.notification_service import NotificationPayload


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

    assert [section["name"] for section in payload.sections] == ["Trade", "Context"]


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


def test_format_signal_omits_image_url_and_keeps_metadata():
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

    assert payload.image_url is None
    assert payload.metadata["symbol"] == "EURUSD"
    assert payload.metadata["ai_result"]["decision"] == "GO"


def test_format_signal_includes_strategy_badge():
    svc = NotificationService()
    signal = {
        "id": 17,
        "symbol": "EURUSD",
        "side": "BUY",
        "entry": 1.08,
        "sl": 1.07,
        "tp": 1.10,
        "strategy_id": "liq_sd_v1",
        "strategy_version": "1",
    }

    payload = svc.format_signal(signal, account_name="Funded Alpha")

    assert payload.fields["Strategy"] == "liq_sd_v1@1"
    assert "liq_sd_v1@1" in payload.title


def test_format_close_includes_strategy_badge():
    svc = NotificationService()
    signal = {
        "id": 18,
        "symbol": "EURUSD",
        "side": "BUY",
        "entry": 1.08,
        "exit_price": 1.09,
        "pnl_usd": 248.50,
        "strategy_id": "liq_sd_v1",
        "strategy_version": "1",
    }

    payload = svc.format_close(signal)

    assert payload.fields["Strategy"] == "liq_sd_v1@1"
    assert "liq_sd_v1@1" in payload.title

def test_format_signal_includes_session_and_bar_time():
    svc = NotificationService()
    signal = {
        "id": 1, "symbol": "XAUUSD", "side": "BUY",
        "entry": 2650.50, "sl": 2640.0, "tp": 2676.25, "size": 0.05,
        "bar_time": "2026-03-30T09:30:00Z",  # London session
        "image_url": "https://www.tradingview.com/x/abc123/",
    }
    payload = svc.format_signal(signal, account_name="Ameer Live MT5")

    assert payload.image_url is None
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
