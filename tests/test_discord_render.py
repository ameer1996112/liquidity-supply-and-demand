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
    assert embed["author"]["name"] == "ACC: Unknown Account"


def test_embed_uses_account_badge_and_status_line():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - XAUUSD",
        fields={"Entry": "3345.2"},
        color="buy",
        account_name="Funded Alpha",
        account_badge="ACC: Funded Alpha",
        status_line="Paper | FTMO",
        sections=[
            {"name": "Trade", "fields": {"Entry": "3345.2", "R:R": "1:2.10"}},
            {"name": "Risk", "fields": {"Risk": "$120.00"}},
        ],
        metadata={"symbol": "XAUUSD"},
    )

    embed = _payload_to_discord_embed(payload)

    assert embed["author"]["name"] == "ACC: Funded Alpha"
    assert embed["description"].startswith("Paper | FTMO")
    assert embed["fields"][0]["name"] == "Trade"
    assert "Entry" in embed["fields"][0]["value"]


def test_embed_falls_back_to_unknown_account_badge():
    payload = NotificationPayload(
        type="alert",
        title="Daily Loss Limit Hit",
        fields={"Severity": "WARNING"},
        color="warning",
        sections=[{"name": "Summary", "fields": {"Severity": "WARNING"}}],
    )

    embed = _payload_to_discord_embed(payload)

    assert embed["author"]["name"] == "ACC: Unknown Account"


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
    assert "AI" in payload.fields
    assert "Confidence" in payload.fields
    assert payload.fields["AI"] == "GO"
    assert "78.4%" in payload.fields["Confidence"]

def test_signal_no_go_ai_decision():
    svc = NotificationService()
    signal = {"id": 2, "symbol": "GBPUSD", "side": "SELL", "entry": 1.27, "sl": 1.28, "tp": 1.25}
    ai = {"decision": "NO_GO", "rf_prob": 0.32, "reason": "Weak setup"}
    payload = svc.format_signal(signal, ai_result=ai)
    assert payload.fields["AI"] == "NO_GO"

def test_signal_no_ai_fields_when_no_ai():
    svc = NotificationService()
    signal = {"id": 3, "symbol": "EURUSD", "side": "BUY", "entry": 1.08, "sl": 1.07, "tp": 1.10}
    payload = svc.format_signal(signal)
    assert "AI" not in payload.fields
    assert "Reason" not in payload.fields

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
    assert "R Multiple" in payload.fields
    assert "+1.99R" in payload.fields["R Multiple"]

def test_close_has_r_multiple_on_loss():
    svc = NotificationService()
    signal = {"id": 6, "symbol": "EURUSD", "side": "BUY",
              "pnl_usd": -62.50, "risk_usd": 125.0}
    payload = svc.format_close(signal)
    assert "R Multiple" in payload.fields
    assert "-0.50R" in payload.fields["R Multiple"]

def test_close_no_r_multiple_without_risk():
    svc = NotificationService()
    signal = {"id": 7, "symbol": "EURUSD", "side": "BUY", "pnl_usd": 100.0}
    payload = svc.format_close(signal)
    assert "R Multiple" not in payload.fields


def test_embed_still_uses_chart_image_when_present():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - EURUSD",
        fields={"Entry": "1.08"},
        color="buy",
        account_badge="ACC: Funded Alpha",
        sections=[{"name": "Trade", "fields": {"Entry": "1.08"}}],
        image_url="https://www.tradingview.com/x/abc123/",
        metadata={"symbol": "EURUSD"},
    )

    embed = _payload_to_discord_embed(payload)

    assert embed["image"]["url"] == "https://www.tradingview.com/x/abc123/"


def test_embed_adds_setup_evidence_field_from_metadata():
    payload = NotificationPayload(
        type="signal",
        title="BUY Signal - GBPUSD",
        fields={"Entry": "1.35414"},
        color="sell",
        sections=[{"name": "Trade", "fields": {"Entry": "1.35414"}}],
        image_url="https://provider.example/setup.png",
        metadata={
            "symbol": "GBPUSD",
            "setup_evidence_summary": {
                "status_label": "Setup Evidence: OK",
                "focus_zone_label": "SUPPLY A+",
                "has_image": True,
            },
        },
    )

    embed = _payload_to_discord_embed(payload)

    assert any(field["name"] == "Setup Evidence" for field in embed["fields"])
    setup_field = next(field for field in embed["fields"] if field["name"] == "Setup Evidence")
    assert "SUPPLY A+" in setup_field["value"]
    assert "attached" in setup_field["value"]
