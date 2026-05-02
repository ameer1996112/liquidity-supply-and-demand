from scripts.optimizer.trading_conditions_filter import evaluate_trading_conditions


def test_news_session_spread_filter_blocks_affected_symbols() -> None:
    report = evaluate_trading_conditions(
        symbols=["USDCAD", "XAUUSD", "NAS100"],
        news_blackouts=[
            {
                "symbol_group": "USD",
                "start": "2026-05-03T12:00:00Z",
                "end": "2026-05-03T13:30:00Z",
                "reason": "High-impact USD news",
            }
        ],
        now="2026-05-03T12:30:00Z",
        spread_states={"NAS100": "SPREAD_RISK"},
        session_states={"XAUUSD": "SESSION_BAD"},
        profile={"news_blackout_required": True},
    )

    assert "USDCAD" in report["blocked_symbols"]
    assert "XAUUSD" in report["blocked_symbols"]
    assert "NAS100" in report["blocked_symbols"]
