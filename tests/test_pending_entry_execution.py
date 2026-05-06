import asyncio

import pytest

from src.services.pending_entry_execution import (
    PendingEntryRequest,
    infer_pip_size,
    wait_for_next_wick_entry,
)


class FakePriceAdapter:
    def __init__(self, prices: list[tuple[float, float]]) -> None:
        self.prices = prices
        self.calls = 0

    async def _get_symbol_price(self, symbol: str) -> tuple[float, float]:
        price = self.prices[min(self.calls, len(self.prices) - 1)]
        self.calls += 1
        return price


class SyncPriceAdapter:
    def __init__(self, price: tuple[float | None, float | None]) -> None:
        self.price = price

    def _get_symbol_price(self, symbol: str) -> tuple[float | None, float | None]:
        return self.price


async def no_sleep(_seconds: float) -> None:
    return None


def test_wait_for_next_wick_buy_triggers_on_ask_pullback() -> None:
    adapter = FakePriceAdapter(
        [
            (1.19995, 1.20005),
            (1.19970, 1.19980),
        ]
    )

    result = asyncio.run(
        wait_for_next_wick_entry(
            adapter,
            PendingEntryRequest(
                symbol="EURUSD",
                side="buy",
                reference_price=1.20000,
                pullback_pips=2.0,
                max_spread_pips=1.5,
                pip_size=0.0001,
                max_delay_seconds=2.0,
                poll_interval_seconds=1.0,
            ),
            sleep_fn=no_sleep,
        )
    )

    assert result.triggered is True
    assert result.entry_price == pytest.approx(1.19980)
    assert result.spread_pips == pytest.approx(1.0)
    assert result.attempts == 2


def test_wait_for_next_wick_sell_triggers_on_bid_pullback() -> None:
    adapter = FakePriceAdapter(
        [
            (1.30000, 1.30010),
            (1.30020, 1.30030),
        ]
    )

    result = asyncio.run(
        wait_for_next_wick_entry(
            adapter,
            PendingEntryRequest(
                symbol="GBPUSD",
                side="sell",
                reference_price=1.30000,
                pullback_pips=2.0,
                max_spread_pips=1.5,
                pip_size=0.0001,
                max_delay_seconds=2.0,
                poll_interval_seconds=1.0,
            ),
            sleep_fn=no_sleep,
        )
    )

    assert result.triggered is True
    assert result.entry_price == pytest.approx(1.30020)
    assert result.spread_pips == pytest.approx(1.0)


def test_wait_for_next_wick_rejects_wide_spread_even_when_price_mitigates() -> None:
    adapter = FakePriceAdapter([(1.19940, 1.19980)])

    result = asyncio.run(
        wait_for_next_wick_entry(
            adapter,
            PendingEntryRequest(
                symbol="EURUSD",
                side="buy",
                reference_price=1.20000,
                pullback_pips=2.0,
                max_spread_pips=2.0,
                pip_size=0.0001,
                max_delay_seconds=0.0,
                poll_interval_seconds=1.0,
            ),
            sleep_fn=no_sleep,
        )
    )

    assert result.triggered is False
    assert result.reason == "spread_too_wide"
    assert result.entry_price is None


def test_infer_pip_size_uses_symbol_fallbacks() -> None:
    assert infer_pip_size("EURUSD", {}) == pytest.approx(0.0001)
    assert infer_pip_size("GBPJPY", {}) == pytest.approx(0.01)
    assert infer_pip_size("XAUUSD", {}) == pytest.approx(0.01)
    assert infer_pip_size("EURUSD", {"pipSize": 0.00001}) == pytest.approx(0.00001)


def test_wait_for_next_wick_supports_sync_price_adapter() -> None:
    adapter = SyncPriceAdapter((1.19970, 1.19980))

    result = asyncio.run(
        wait_for_next_wick_entry(
            adapter,
            PendingEntryRequest(
                symbol="EURUSD",
                side="buy",
                reference_price=1.20000,
                pullback_pips=2.0,
                max_spread_pips=1.5,
                pip_size=0.0001,
                max_delay_seconds=0.0,
                poll_interval_seconds=1.0,
            ),
            sleep_fn=no_sleep,
        )
    )

    assert result.triggered is True
    assert result.entry_price == pytest.approx(1.19980)


def test_wait_for_next_wick_rejects_unavailable_prices() -> None:
    adapter = SyncPriceAdapter((None, None))

    result = asyncio.run(
        wait_for_next_wick_entry(
            adapter,
            PendingEntryRequest(
                symbol="EURUSD",
                side="buy",
                reference_price=1.20000,
                pullback_pips=2.0,
                max_spread_pips=1.5,
                pip_size=0.0001,
                max_delay_seconds=0.0,
                poll_interval_seconds=1.0,
            ),
            sleep_fn=no_sleep,
        )
    )

    assert result.triggered is False
    assert result.reason == "price_unavailable"
