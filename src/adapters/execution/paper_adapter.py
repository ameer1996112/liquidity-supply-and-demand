"""Paper execution: delegates to PaperTrader with realistic slippage simulation.

Simulates execution imperfections so paper results are closer to live trading:
  - Random slippage (0–1.5 pips, skewed negative = against you)
  - Spread cost applied to fill price
"""

import logging
import random
from typing import Any

from src.adapters.execution.interfaces import CloseRequest, ExecutionResult, OrderRequest

logger = logging.getLogger(__name__)

# ── Slippage simulation defaults ─────────────────────────────────
_DEFAULT_SLIPPAGE_MIN_PIPS = 0.0
_DEFAULT_SLIPPAGE_MAX_PIPS = 1.5
_DEFAULT_SPREAD_PIPS = 1.5  # Typical major forex spread

# Symbol-specific pip sizes for slippage calculation
_PIP_SIZES = {
    "JPY": 0.01,
    "XAU": 0.01,
    "GOLD": 0.01,
}


def _pip_size(symbol: str) -> float:
    """Return pip size for a symbol."""
    symbol_upper = symbol.upper()
    for key, size in _PIP_SIZES.items():
        if key in symbol_upper:
            return size
    return 0.0001


def _simulate_slippage(entry: float, side: str, symbol: str) -> float:
    """Simulate realistic slippage on the fill price.

    Slippage is biased against the trader (80% unfavorable, 20% favorable)
    to give conservative paper results closer to real execution.
    """
    pip_sz = _pip_size(symbol)
    # 80% chance slippage is against you, 20% in your favor
    direction = -1 if random.random() < 0.80 else 1
    slip_pips = random.uniform(_DEFAULT_SLIPPAGE_MIN_PIPS, _DEFAULT_SLIPPAGE_MAX_PIPS)
    slip_price = slip_pips * pip_sz

    # Add half-spread cost (the other half is implicit in the entry price)
    spread_cost = (_DEFAULT_SPREAD_PIPS / 2) * pip_sz

    if side == "buy":
        # Buying: worse fill = higher price
        fill = entry + (slip_price * (-direction)) + spread_cost
    else:
        # Selling: worse fill = lower price
        fill = entry - (slip_price * (-direction)) - spread_cost

    logger.debug(
        "Paper slippage: %s %s entry=%.5f fill=%.5f slip=%.1f pips spread=%.1f pips",
        side, symbol, entry, fill, slip_pips * (-direction), _DEFAULT_SPREAD_PIPS / 2,
    )
    return round(fill, 5)


class PaperAdapter:
    def __init__(self, paper_trader: Any, *, simulate_slippage: bool = True) -> None:
        self._pt = paper_trader
        self._simulate_slippage = simulate_slippage

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        alert_id = request.alert_id or request.signal_id or 0
        entry = request.entry or 0.0
        sl = request.sl or 0.0
        tp = request.tp or 0.0
        size = request.size or 0.01
        rr_ratio = request.rr_ratio or 0.0
        side = (request.side or "").lower()
        symbol = (request.symbol or "").upper()

        # Simulate realistic fill price with slippage + spread
        actual_fill = entry
        if self._simulate_slippage and entry > 0:
            actual_fill = _simulate_slippage(entry, side, symbol)

        try:
            ok = self._pt.open_position(int(alert_id), symbol, side, float(actual_fill), float(sl), float(tp), float(size), float(rr_ratio))
            if ok:
                return ExecutionResult(
                    status="filled",
                    broker_order_id=str(alert_id),
                    client_order_id=request.client_order_id,
                    actual_fill_price=actual_fill,
                )
            return ExecutionResult(status="failed", message="PaperTrader.open_position returned False", client_order_id=request.client_order_id)
        except Exception as e:
            logger.exception("PaperAdapter submit_order failed: %s", e)
            return ExecutionResult(status="failed", message=str(e), client_order_id=request.client_order_id)

    def close_order(self, request: CloseRequest) -> ExecutionResult:
        alert_id = request.alert_id or request.signal_id or 0
        close_price = request.close_price or 0.0
        outcome = request.outcome or "breakeven"
        notes = request.notes or ""

        # Simulate slippage on exit too
        actual_close = close_price
        if self._simulate_slippage and close_price > 0:
            # Exit slippage: opposite side to entry
            exit_side = "sell" if (request.side or "").lower() == "buy" else "buy"
            actual_close = _simulate_slippage(close_price, exit_side, request.symbol or "EURUSD")

        try:
            pnl = self._pt.close_position(int(alert_id), float(actual_close), outcome, notes)
            if pnl is not None:
                return ExecutionResult(
                    status="submitted",
                    client_order_id=request.client_order_id,
                    actual_fill_price=actual_close,
                )
            return ExecutionResult(status="failed", message="Position not found", client_order_id=request.client_order_id)
        except Exception as e:
            logger.exception("PaperAdapter close_order failed: %s", e)
            return ExecutionResult(status="failed", message=str(e), client_order_id=request.client_order_id)
