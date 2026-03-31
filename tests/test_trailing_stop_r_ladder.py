"""
Tests for DEV-79: Trailing Stop R-Ladder

Covers:
1. Bug fix: breakeven_manager._activate_trailing_stop uses correct params
2. Trail distance = 50% of original SL distance
3. R-ladder: 2R milestone locks in 1R profit
4. R-ladder: 3R milestone locks in 2R profit
5. R-ladder: milestones do not fire twice (r2_locked / r3_locked guards)
6. SELL side correctness
7. Edge cases: missing sl_distance_pips, price below 2R
"""
import pytest
from unittest.mock import MagicMock, patch
from src.services.trailing_stop_manager import TrailingStopManager, TrailingStop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ts(
    side="buy",
    entry_price=1.10000,
    current_sl=1.09500,
    sl_distance_pips=50.0,
    trail_distance_pips=25.0,
    highest_price_seen=None,
    lowest_price_seen=None,
    r2_locked=False,
    r3_locked=False,
    times_moved=0,
) -> TrailingStop:
    return TrailingStop(
        id=1,
        signal_id=42,
        symbol="EURUSD",
        side=side,
        trail_distance_pips=trail_distance_pips,
        activation_price=None,
        wait_for_breakeven=False,
        is_active=True,
        is_activated=True,
        current_sl=current_sl,
        highest_price_seen=highest_price_seen,
        lowest_price_seen=lowest_price_seen,
        entry_price=entry_price,
        times_moved=times_moved,
        sl_distance_pips=sl_distance_pips,
        r2_locked=r2_locked,
        r3_locked=r3_locked,
    )


# ---------------------------------------------------------------------------
# Bug fix: breakeven_manager._activate_trailing_stop call-site
# ---------------------------------------------------------------------------

def test_activate_trailing_stop_passes_only_valid_kwargs():
    """
    _activate_trailing_stop must call add_trailing_stop with only valid kwargs:
    signal_id, trail_distance_pips, activation_price, sl_distance_pips.
    It must NOT pass symbol, side, or entry_price (not in method signature).
    """
    from src.services.breakeven_manager import BreakevenManager

    mock_tsm = MagicMock()
    mock_tsm.add_trailing_stop.return_value = 99

    bm = BreakevenManager(MagicMock(), MagicMock(), trailing_stop_manager=mock_tsm)

    row = {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.10000,
        "sl": 1.09500,
    }

    with patch("src.services.breakeven_manager.get_settings") as mock_settings:
        mock_settings.return_value.trail_activation_pips = 0.0
        bm._activate_trailing_stop(signal_id=42, row=row, be_sl_price=1.10000)

    mock_tsm.add_trailing_stop.assert_called_once()
    kwargs = mock_tsm.add_trailing_stop.call_args.kwargs

    assert "symbol" not in kwargs, "symbol must not be passed to add_trailing_stop"
    assert "side" not in kwargs, "side must not be passed to add_trailing_stop"
    assert "entry_price" not in kwargs, "entry_price must not be passed to add_trailing_stop"
    assert kwargs["signal_id"] == 42
    assert "trail_distance_pips" in kwargs
    assert "sl_distance_pips" in kwargs


def test_trail_distance_is_50_percent_of_sl_distance():
    """Trail distance must be 50% of original SL distance in pips."""
    from src.services.breakeven_manager import BreakevenManager

    mock_tsm = MagicMock()
    mock_tsm.add_trailing_stop.return_value = 1
    bm = BreakevenManager(MagicMock(), MagicMock(), trailing_stop_manager=mock_tsm)

    # entry=1.10000, sl=1.09500 → distance = 0.00500 = 50 pips (pip_size=0.0001)
    # Expected trail = 50 * 0.5 = 25 pips
    row = {"symbol": "EURUSD", "side": "buy", "entry": 1.10000, "sl": 1.09500}

    with patch("src.services.breakeven_manager.get_settings") as mock_settings:
        mock_settings.return_value.trail_activation_pips = 0.0
        bm._activate_trailing_stop(signal_id=42, row=row, be_sl_price=1.10000)

    kwargs = mock_tsm.add_trailing_stop.call_args.kwargs
    assert abs(kwargs["trail_distance_pips"] - 25.0) < 0.1, (
        f"Expected trail_distance_pips=25.0, got {kwargs['trail_distance_pips']}"
    )
    assert abs(kwargs["sl_distance_pips"] - 50.0) < 0.1, (
        f"Expected sl_distance_pips=50.0, got {kwargs['sl_distance_pips']}"
    )


def test_activate_trailing_stop_skips_when_no_entry():
    """_activate_trailing_stop must return early if entry price is 0 or missing."""
    from src.services.breakeven_manager import BreakevenManager

    mock_tsm = MagicMock()
    bm = BreakevenManager(MagicMock(), MagicMock(), trailing_stop_manager=mock_tsm)

    row = {"symbol": "EURUSD", "side": "buy", "entry": 0, "sl": 1.09500}

    with patch("src.services.breakeven_manager.get_settings") as mock_settings:
        mock_settings.return_value.trail_activation_pips = 0.0
        bm._activate_trailing_stop(signal_id=42, row=row, be_sl_price=1.10000)

    mock_tsm.add_trailing_stop.assert_not_called()


# ---------------------------------------------------------------------------
# R-Ladder: 2R milestone (BUY)
# ---------------------------------------------------------------------------

def test_r_ladder_2r_locks_1r_profit_for_buy():
    """
    BUY: entry=1.10000, sl_distance=50 pips.
    2R target = entry + 2*0.0050 = 1.11000.
    SL must lock at entry + 1*0.0050 = 1.10500.
    """
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        side="buy",
        entry_price=1.10000,
        current_sl=1.10000,  # at breakeven
        sl_distance_pips=50.0,
        trail_distance_pips=25.0,
    )

    with patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.11000)

    mock_lock.assert_called_once_with(ts.id, milestone=2)
    mock_move.assert_called_once()
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.10500) < 0.00001, f"Expected 1.10500, got {new_sl_arg}"


def test_r_ladder_2r_does_not_fire_twice():
    """Once r2_locked=True, _check_r_ladder must not move SL again for 2R."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        entry_price=1.10000, current_sl=1.10500,
        sl_distance_pips=50.0, r2_locked=True,
    )

    with patch.object(tsm, "_move_stop_loss") as mock_move, \
         patch.object(tsm, "_lock_r_milestone") as mock_lock:
        tsm._check_r_ladder(ts, current_price=1.11000)

    mock_move.assert_not_called()
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# R-Ladder: 3R milestone (BUY)
# ---------------------------------------------------------------------------

def test_r_ladder_3r_locks_2r_profit_for_buy():
    """
    BUY: entry=1.10000, sl_distance=50 pips.
    3R target = entry + 3*0.0050 = 1.11500.
    SL must lock at entry + 2*0.0050 = 1.11000.
    """
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        entry_price=1.10000, current_sl=1.10500,
        sl_distance_pips=50.0, r2_locked=True, r3_locked=False,
    )

    with patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.11500)

    mock_lock.assert_called_once_with(ts.id, milestone=3)
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.11000) < 0.00001, f"Expected 1.11000, got {new_sl_arg}"


def test_r_ladder_3r_does_not_fire_twice():
    """Once r3_locked=True, _check_r_ladder must not fire again."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        entry_price=1.10000, current_sl=1.11000,
        sl_distance_pips=50.0, r2_locked=True, r3_locked=True,
    )

    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.12000)

    mock_move.assert_not_called()


# ---------------------------------------------------------------------------
# SELL side
# ---------------------------------------------------------------------------

def test_r_ladder_2r_locks_1r_profit_for_sell():
    """
    SELL: entry=1.10000, sl=1.10500 → sl_distance=50 pips.
    2R target: entry - 2*0.0050 = 1.09000.
    SL locks at: entry - 1*0.0050 = 1.09500.
    """
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        side="sell",
        entry_price=1.10000,
        current_sl=1.10000,  # at breakeven
        sl_distance_pips=50.0,
        trail_distance_pips=25.0,
        r2_locked=False,
    )

    with patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.09000)

    mock_lock.assert_called_once_with(ts.id, milestone=2)
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.09500) < 0.00001, f"Expected 1.09500, got {new_sl_arg}"


def test_r_ladder_3r_locks_2r_profit_for_sell():
    """
    SELL: entry=1.10000, sl_distance=50 pips.
    3R target: entry - 3*0.0050 = 1.08500.
    SL locks at: entry - 2*0.0050 = 1.09000.
    """
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        side="sell",
        entry_price=1.10000,
        current_sl=1.09500,
        sl_distance_pips=50.0,
        r2_locked=True, r3_locked=False,
    )

    with patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.08500)

    mock_lock.assert_called_once_with(ts.id, milestone=3)
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.09000) < 0.00001, f"Expected 1.09000, got {new_sl_arg}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_r_ladder_no_action_below_2r():
    """Price at 1.5R should not trigger any milestone."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(entry_price=1.10000, current_sl=1.10000, sl_distance_pips=50.0)

    # 1.5R = 1.10000 + 0.0075 = 1.10750
    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.10750)

    mock_move.assert_not_called()


def test_r_ladder_skipped_when_sl_distance_zero():
    """If sl_distance_pips is 0, skip R-ladder to avoid division/calculation errors."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(sl_distance_pips=0.0)

    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.15000)

    mock_move.assert_not_called()


def test_r_ladder_skipped_when_sl_distance_none():
    """If sl_distance_pips is None (old record), skip R-ladder gracefully."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(sl_distance_pips=None)

    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.15000)

    mock_move.assert_not_called()
