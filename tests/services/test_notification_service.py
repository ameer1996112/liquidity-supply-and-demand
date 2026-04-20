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


<<<<<<< HEAD
def test_format_close_uses_dedicated_close_image_url() -> None:
    payload = NotificationService().format_close(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "exit_price": 0.7172,
            "pnl_usd": 42.5,
            "close_image_url": "https://provider.example/close.png",
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url == "https://provider.example/close.png"


def test_format_close_does_not_reuse_opening_setup_evidence_image() -> None:
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

    assert payload.image_url is None


||||||| parent of af73693 (DEV-161: remove legacy close screenshot test)
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


=======
>>>>>>> af73693 (DEV-161: remove legacy close screenshot test)
def test_format_close_uses_dedicated_close_image_url() -> None:
    payload = NotificationService().format_close(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "exit_price": 0.7172,
            "pnl_usd": 42.5,
            "close_image_url": "https://provider.example/close.png",
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url == "https://provider.example/close.png"


def test_format_close_does_not_reuse_opening_setup_evidence_image() -> None:
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

    assert payload.image_url is None


def test_format_signal_includes_setup_evidence_summary_metadata() -> None:
    payload = NotificationService().format_signal(
        {
            "id": 45,
            "symbol": "GBPUSD",
            "side": "SELL",
            "entry": 1.35414,
            "sl": 1.3562,
            "tp": 1.3494,
            "setup_evidence": {
                "status": "ok",
                "focus_zone": {"label": "SUPPLY A+"},
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.metadata["setup_evidence_summary"] == {
        "status": "ok",
        "status_label": "Setup Evidence: OK",
        "focus_zone_label": "SUPPLY A+",
        "has_image": True,
        "reason": "",
    }


def test_format_close_reuses_setup_evidence_summary_metadata() -> None:
    payload = NotificationService().format_close(
        {
            "id": 46,
            "symbol": "GBPUSD",
            "side": "SELL",
            "entry": 1.35414,
            "exit_price": 1.3494,
            "pnl_usd": 42.5,
            "setup_evidence": {
                "status": "degraded",
                "reason": "focus zone fallback",
                "focus_zone": {"label": "SUPPLY A+"},
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.metadata["setup_evidence_summary"] == {
        "status": "degraded",
        "status_label": "Setup Evidence: DEGRADED",
        "focus_zone_label": "SUPPLY A+",
        "has_image": True,
        "reason": "focus zone fallback",
    }


def test_format_close_keeps_clean_summary_and_context_sections() -> None:
    payload = NotificationService().format_close(
        {
            "id": 46,
            "symbol": "XAUUSD",
            "side": "SELL",
            "fill_price": 4796.0,
            "exit_price": 4802.8,
            "pnl_usd": -329.81,
            "commission": -0.58,
            "strategy_id": "liq_sd_v1",
            "strategy_version": "1",
            "account_name": "ACG-DEMO-2",
        }
    )

    section_names = [section["name"] for section in payload.sections]
    assert section_names == ["Summary", "Context"]
    assert payload.fields["Outcome"] == "LOSS"
    assert payload.fields["PnL"] == "-$329.81"
    assert payload.fields["Signal"] == "#46"
