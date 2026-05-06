"""Pending entry helpers for backend execution refinements."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol


class PriceAdapter(Protocol):
    def _get_symbol_price(self, symbol: str) -> tuple[float, float] | Awaitable[tuple[float, float]]:
        """Return current bid and ask for a symbol."""


SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class PendingEntryRequest:
    symbol: str
    side: str
    reference_price: float
    pullback_pips: float
    max_spread_pips: float
    pip_size: float
    max_delay_seconds: float
    poll_interval_seconds: float


@dataclass(frozen=True)
class PendingEntryResult:
    triggered: bool
    reason: str
    entry_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    spread_pips: float | None = None
    attempts: int = 0


def infer_pip_size(symbol: str, broker_spec: dict[str, Any] | None = None) -> float:
    """Infer pip size from broker spec, then symbol family."""
    spec = broker_spec or {}
    raw_pip_size = spec.get("pipSize") or spec.get("pip_size")
    if raw_pip_size:
        try:
            pip_size = float(raw_pip_size)
            if pip_size > 0:
                return pip_size
        except (TypeError, ValueError):
            pass

    normalized = symbol.upper()
    if "JPY" in normalized:
        return 0.01
    if normalized.startswith(("XAU", "GOLD", "XAG", "SILVER")):
        return 0.01
    return 0.0001


async def wait_for_next_wick_entry(
    adapter: PriceAdapter,
    request: PendingEntryRequest,
    *,
    sleep_fn: SleepFn = asyncio.sleep,
) -> PendingEntryResult:
    """Wait for a side-specific bid/ask pullback before placing a market order."""
    side = request.side.lower()
    if side not in {"buy", "sell"}:
        return PendingEntryResult(triggered=False, reason="invalid_side")
    if request.pip_size <= 0:
        return PendingEntryResult(triggered=False, reason="invalid_pip_size")
    if request.pullback_pips < 0:
        return PendingEntryResult(triggered=False, reason="invalid_pullback")
    if not hasattr(adapter, "_get_symbol_price"):
        return PendingEntryResult(triggered=False, reason="price_feed_unavailable")

    poll_interval = max(float(request.poll_interval_seconds), 0.01)
    max_delay = max(float(request.max_delay_seconds), 0.0)
    max_attempts = max(1, int(max_delay / poll_interval) + 1)
    offset = request.pullback_pips * request.pip_size
    trigger_price = request.reference_price - offset if side == "buy" else request.reference_price + offset

    last_spread_too_wide = False
    last_bid: float | None = None
    last_ask: float | None = None
    last_spread_pips: float | None = None

    for attempt in range(1, max_attempts + 1):
        price_result = adapter._get_symbol_price(request.symbol)
        bid, ask = await price_result if inspect.isawaitable(price_result) else price_result
        if bid is None or ask is None:
            return PendingEntryResult(
                triggered=False,
                reason="price_unavailable",
                attempts=attempt,
            )
        spread_pips = (ask - bid) / request.pip_size
        last_bid = bid
        last_ask = ask
        last_spread_pips = spread_pips

        price_mitigated = ask <= trigger_price if side == "buy" else bid >= trigger_price
        spread_ok = spread_pips <= request.max_spread_pips
        last_spread_too_wide = price_mitigated and not spread_ok

        if price_mitigated and spread_ok:
            entry_price = ask if side == "buy" else bid
            return PendingEntryResult(
                triggered=True,
                reason="triggered",
                entry_price=entry_price,
                bid=bid,
                ask=ask,
                spread_pips=spread_pips,
                attempts=attempt,
            )

        if attempt < max_attempts:
            await sleep_fn(poll_interval)

    reason = "spread_too_wide" if last_spread_too_wide else "timeout"
    return PendingEntryResult(
        triggered=False,
        reason=reason,
        bid=last_bid,
        ask=last_ask,
        spread_pips=last_spread_pips,
        attempts=max_attempts,
    )
