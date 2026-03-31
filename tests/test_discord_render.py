from src.adapters.discord import _payload_to_discord_embed, _get_symbol_thumbnail_url
from src.services.notification_service import NotificationService, NotificationPayload


# ─── Existing tests ──────────────────────────────────────────────────────────

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


# ─── Author block ─────────────────────────────────────────────────────────────

def test_embed_has_author_block():
    payload = NotificationPayload(
        type="signal", title="📈 BUY EURUSD", fields={},
        color="buy", account_name="FTMO-50K",
        metadata={"symbol": "EURUSD", "side": "BUY", "mode": "manual"},
    )
    embed = _payload_to_discord_embed(payload)
    assert "author" in embed
    assert "FTMO-50K" in embed["author"]["name"]

def test_embed_author_without_account_name():
    payload = NotificationPayload(
        type="signal", title="📈 BUY EURUSD", fields={},
        color="buy",
        metadata={"symbol": "EURUSD"},
    )
    embed = _payload_to_discord_embed(payload)
    assert "author" in embed
    assert embed["author"]["name"] == "Trading Bot"


# ─── Thumbnail / flag logic ───────────────────────────────────────────────────

def test_thumbnail_uses_flag_for_eurusd():
    assert _get_symbol_thumbnail_url("EURUSD", None) == "https://flagcdn.com/w80/eu.png"

def test_thumbnail_uses_flag_for_gbpusd():
    assert _get_symbol_thumbnail_url("GBPUSD", None) == "https://flagcdn.com/w80/gb.png"

def test_thumbnail_uses_image_url_when_present():
    url = "https://www.tradingview.com/x/abc123/"
    assert _get_symbol_thumbnail_url("EURUSD", url) == url

def test_thumbnail_none_for_xauusd():
    assert _get_symbol_thumbnail_url("XAUUSD", None) is None

def test_embed_sets_thumbnail_for_eurusd_no_chart():
    payload = NotificationPayload(
        type="signal", title="📈 BUY EURUSD", fields={},
        color="buy", image_url=None,
        metadata={"symbol": "EURUSD"},
    )
    embed = _payload_to_discord_embed(payload)
    assert "thumbnail" in embed
    assert "eu.png" in embed["thumbnail"]["url"]
    assert "image" not in embed

def test_embed_no_thumbnail_when_image_url_set():
    payload = NotificationPayload(
        type="signal", title="📈 BUY EURUSD", fields={},
        color="buy", image_url="https://www.tradingview.com/x/abc123/",
        metadata={"symbol": "EURUSD"},
    )
    embed = _payload_to_discord_embed(payload)
    assert "image" in embed
    assert "thumbnail" not in embed


# ─── AI compact fields ────────────────────────────────────────────────────────

def test_signal_has_compact_ai_fields():
    svc = NotificationService()
    signal = {"id": 1, "symbol": "EURUSD", "side": "BUY", "entry": 1.08, "sl": 1.07, "tp": 1.10}
    ai = {"decision": "GO", "rf_prob": 0.784, "reason": "Strong trend", "rules": []}
    payload = svc.format_signal(signal, ai_result=ai)
    assert "🧠 AI Decision" in payload.fields
    assert "🎯 Confidence" in payload.fields
    assert "✅ GO" in payload.fields["🧠 AI Decision"]
    assert "78.4%" in payload.fields["🎯 Confidence"]

def test_signal_no_go_ai_decision():
    svc = NotificationService()
    signal = {"id": 2, "symbol": "GBPUSD", "side": "SELL", "entry": 1.27, "sl": 1.28, "tp": 1.25}
    ai = {"decision": "NO_GO", "rf_prob": 0.32, "reason": "Weak setup"}
    payload = svc.format_signal(signal, ai_result=ai)
    assert "⛔ NO_GO" in payload.fields["🧠 AI Decision"]

def test_signal_no_ai_fields_when_no_ai():
    svc = NotificationService()
    signal = {"id": 3, "symbol": "EURUSD", "side": "BUY", "entry": 1.08, "sl": 1.07, "tp": 1.10}
    payload = svc.format_signal(signal)
    assert "🧠 AI Decision" not in payload.fields
    assert "🧠 AI Analysis" not in payload.fields

def test_signal_ai_result_stored_in_metadata():
    svc = NotificationService()
    signal = {"id": 4, "symbol": "EURUSD", "side": "BUY", "entry": 1.08, "sl": 1.07, "tp": 1.10}
    ai = {"decision": "GO", "rf_prob": 0.9}
    payload = svc.format_signal(signal, ai_result=ai)
    assert payload.metadata.get("ai_result") == ai


# ─── R Multiple on close ──────────────────────────────────────────────────────

def test_close_has_r_multiple_on_win():
    svc = NotificationService()
    signal = {"id": 5, "symbol": "EURUSD", "side": "BUY",
              "pnl_usd": 248.50, "risk_usd": 125.0}
    payload = svc.format_close(signal)
    assert "📊 R Multiple" in payload.fields
    assert "+1.99R" in payload.fields["📊 R Multiple"]

def test_close_has_r_multiple_on_loss():
    svc = NotificationService()
    signal = {"id": 6, "symbol": "EURUSD", "side": "BUY",
              "pnl_usd": -62.50, "risk_usd": 125.0}
    payload = svc.format_close(signal)
    assert "📊 R Multiple" in payload.fields
    assert "-0.50R" in payload.fields["📊 R Multiple"]

def test_close_no_r_multiple_without_risk():
    svc = NotificationService()
    signal = {"id": 7, "symbol": "EURUSD", "side": "BUY", "pnl_usd": 100.0}
    payload = svc.format_close(signal)
    assert "📊 R Multiple" not in payload.fields
