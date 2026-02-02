"""
Unit tests for execution adapters: DryRunAdapter and PaperAdapter.
Uses a stub PaperTrader; no imports from src.logic or src.worker.
"""

import pytest
from unittest.mock import MagicMock

from src.adapters.execution.dry_run_adapter import DryRunAdapter, DRY_RUN_MESSAGE
from src.adapters.execution.interfaces import CloseRequest, OrderRequest, ExecutionResult
from src.adapters.execution.paper_adapter import PaperAdapter
from src.adapters.execution.router import get_adapter


# ─── Stub PaperTrader ───────────────────────────────────────────────────────

class StubPaperTrader:
    """Minimal PaperTrader interface for tests."""

    def __init__(self, open_returns: bool = True, close_returns: float | None = 0.0):
        self.open_returns = open_returns
        self.close_returns = close_returns
        self.positions = {}

    def open_position(
        self,
        alert_id: int,
        symbol: str,
        side: str,
        entry: float,
        sl: float,
        tp: float,
        size: float,
        rr_ratio: float,
    ) -> bool:
        self.positions[alert_id] = {"symbol": symbol, "side": side}
        return self.open_returns

    def close_position(
        self,
        alert_id: int,
        close_price: float,
        outcome: str,
        notes: str = "",
    ) -> float | None:
        return self.close_returns


# ─── DryRunAdapter ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_dry_run_adapter_submit_order_returns_submitted():
    adapter = DryRunAdapter()
    req = OrderRequest(
        client_order_id="tk-1",
        symbol="EURUSD",
        side="buy",
        size=0.01,
        entry=1.08,
        sl=1.07,
        tp=1.10,
    )
    result = adapter.submit_order(req)
    assert result.status == "submitted"
    assert result.message == DRY_RUN_MESSAGE
    assert result.client_order_id == "tk-1"
    assert result.broker_order_id is None


@pytest.mark.unit
def test_dry_run_adapter_close_order_returns_submitted():
    adapter = DryRunAdapter()
    req = CloseRequest(
        client_order_id="tk-1",
        symbol="EURUSD",
        close_price=1.09,
        outcome="win",
        alert_id=42,
    )
    result = adapter.close_order(req)
    assert result.status == "submitted"
    assert result.message == DRY_RUN_MESSAGE
    assert result.client_order_id == "tk-1"
    assert result.broker_order_id is None


# ─── PaperAdapter with stub ─────────────────────────────────────────────────

@pytest.mark.unit
def test_paper_adapter_submit_order_success():
    stub = StubPaperTrader(open_returns=True)
    adapter = PaperAdapter(stub)
    req = OrderRequest(
        client_order_id="tk-1",
        alert_id=1,
        symbol="EURUSD",
        side="buy",
        size=0.01,
        entry=1.08,
        sl=1.07,
        tp=1.10,
        rr_ratio=2.0,
    )
    result = adapter.submit_order(req)
    assert result.status == "submitted"
    assert result.broker_order_id == "1"
    assert result.client_order_id == "tk-1"
    assert 1 in stub.positions


@pytest.mark.unit
def test_paper_adapter_submit_order_failure_when_open_returns_false():
    stub = StubPaperTrader(open_returns=False)
    adapter = PaperAdapter(stub)
    req = OrderRequest(
        client_order_id="tk-1",
        alert_id=1,
        symbol="EURUSD",
        side="buy",
        size=0.01,
        entry=1.08,
        sl=1.07,
        tp=1.10,
    )
    result = adapter.submit_order(req)
    assert result.status == "failed"
    assert result.broker_order_id is None
    assert "open_position" in (result.message or "").lower() or result.message is None


@pytest.mark.unit
def test_paper_adapter_close_order_success():
    stub = StubPaperTrader(close_returns=50.0)
    adapter = PaperAdapter(stub)
    req = CloseRequest(
        client_order_id="tk-1",
        alert_id=1,
        symbol="EURUSD",
        close_price=1.09,
        outcome="win",
    )
    result = adapter.close_order(req)
    assert result.status == "submitted"
    assert result.client_order_id == "tk-1"


@pytest.mark.unit
def test_paper_adapter_close_order_failure_when_close_returns_none():
    stub = StubPaperTrader(close_returns=None)
    adapter = PaperAdapter(stub)
    req = CloseRequest(
        client_order_id="tk-1",
        alert_id=999,
        symbol="EURUSD",
        close_price=1.09,
        outcome="loss",
    )
    result = adapter.close_order(req)
    assert result.status == "failed"
    assert result.broker_order_id is None
    assert "position" in (result.message or "").lower() or "None" in (result.message or "")


# ─── Router (no env) ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_router_dry_run_returns_dry_run_adapter():
    settings = MagicMock()
    settings.run_mode = "DRY_RUN"
    settings.live_trading_enabled = False
    adapter = get_adapter(run_mode="DRY_RUN", settings=settings)
    assert isinstance(adapter, DryRunAdapter)


@pytest.mark.unit
def test_router_paper_returns_paper_adapter():
    stub = StubPaperTrader()
    settings = MagicMock()
    settings.run_mode = "PAPER"
    adapter = get_adapter(run_mode="PAPER", settings=settings, paper_trader=stub)
    assert isinstance(adapter, PaperAdapter)


@pytest.mark.unit
def test_router_paper_requires_paper_trader():
    settings = MagicMock()
    settings.run_mode = "PAPER"
    with pytest.raises(ValueError, match="paper_trader"):
        get_adapter(run_mode="PAPER", settings=settings, paper_trader=None)


@pytest.mark.unit
def test_router_live_shadow_returns_live_adapter():
    from src.adapters.execution.live_adapter import LiveAdapter
    settings = MagicMock()
    settings.run_mode = "LIVE"
    settings.live_trading_enabled = True
    settings.live_shadow = True
    adapter = get_adapter(run_mode="LIVE", settings=settings)
    assert isinstance(adapter, LiveAdapter)


@pytest.mark.unit
def test_router_live_not_enabled_returns_dry_run_adapter():
    settings = MagicMock()
    settings.run_mode = "LIVE"
    settings.live_trading_enabled = False
    adapter = get_adapter(run_mode="LIVE", settings=settings)
    assert isinstance(adapter, DryRunAdapter)
