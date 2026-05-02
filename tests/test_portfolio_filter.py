from scripts.optimizer.portfolio_filter import filter_portfolio


def test_portfolio_filter_rejects_correlated_overexposure() -> None:
    allowed, blocked, report = filter_portfolio(
        ["NQ", "NAS100", "USDCAD"],
        profile={"max_symbols_active": 3, "max_correlated_symbols": 1},
    )

    assert "NQ" in allowed
    assert "NAS100" in blocked
    assert "index" in blocked["NAS100"]
    assert report["status"] == "filtered"


def test_portfolio_filter_respects_max_symbols_active() -> None:
    allowed, blocked, _report = filter_portfolio(
        ["USDCAD", "EURUSD", "XAUUSD"],
        profile={"max_symbols_active": 2, "max_correlated_symbols": 2},
    )

    assert len(allowed) == 2
    assert "XAUUSD" in blocked
