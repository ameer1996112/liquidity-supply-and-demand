from __future__ import annotations

from src.logic import _should_fetch_broker_pnl_after_close


def test_submitted_close_is_eligible_for_broker_pnl_fetch():
    assert _should_fetch_broker_pnl_after_close("submitted") is True


def test_failed_close_is_not_eligible_for_broker_pnl_fetch():
    assert _should_fetch_broker_pnl_after_close("failed") is False
