from src.services.optimizer_market_context_service import (
    build_spread_stress_profiles,
    symbol_currencies,
)
from src.services.optimizer_news_ingest import normalize_trading_economics_event


def test_symbol_currencies_maps_forex_pair() -> None:
    assert symbol_currencies("GBPJPY") == ["GBP", "JPY"]


def test_build_spread_stress_profiles_expands_baseline() -> None:
    profiles = build_spread_stress_profiles(
        baseline_spread=1.2,
        slippage_per_side=0.1,
    )

    assert profiles["baseline"]["spread"] == 1.2
    assert profiles["baseline"]["slippage_per_side"] == 0.1
    assert profiles["spread_125"]["spread"] == 1.5
    assert profiles["spread_125"]["slippage_per_side"] == 0.1
    assert profiles["spread_150"]["spread"] == 1.8
    assert profiles["spread_150"]["slippage_per_side"] == 0.1
    assert profiles["spread_slippage"]["spread"] == 1.5
    assert profiles["spread_slippage"]["slippage_per_side"] == 0.2


def test_normalize_trading_economics_event_normalizes_event_time_to_utc() -> None:
    normalized = normalize_trading_economics_event(
        {
            "CalendarId": 42,
            "Date": "2026-04-19T09:30:00-04:00",
            "Currency": "USD",
            "Country": "United States",
            "Importance": "2",
            "Event": "Retail Sales",
        }
    )

    assert normalized["external_id"] == "42"
    assert normalized["event_time"] == "2026-04-19T13:30:00+00:00"
    assert normalized["importance"] == 2
