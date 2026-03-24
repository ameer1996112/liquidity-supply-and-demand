"""
Tests for PineGuardian v2 — Adaptive Daily Trade Limit.

Covers:
1. Session classification
2. Intraday quality adjustment (Dimension 1)
3. Multi-day streak bonus (Dimension 2)
4. Session-slot separation (Dimension 3)
5. Combined effective limit formula
6. Risk budget gate (parallel)
7. Progressive risk scaling
8. Backward-compat static mode
9. Validation result details
"""

import pytest
from src.core.guard_rails.pine_guardian import (
    PineGuardian,
    TradingSession,
    RejectionReason,
    create_pine_guardian_from_settings,
    DEFAULT_MAX_TRADES_LONDON,
    DEFAULT_MAX_TRADES_NY,
    DEFAULT_MAX_TRADES_OFFHOURS,
    DEFAULT_MAX_TRADES_HARD_CAP,
    DEFAULT_DAILY_RISK_BUDGET_PCT,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_guardian(**kwargs) -> PineGuardian:
    """Create a PineGuardian with adaptive on by default."""
    defaults = dict(
        account_balance=50_000.0,
        risk_per_trade_pct=0.5,
        max_daily_loss_pct=2.0,
        max_daily_profit_pct=5.0,
        adaptive_enabled=True,
        max_trades_london=2,
        max_trades_ny=2,
        max_trades_offhours=1,
        max_trades_hard_cap=6,
        daily_risk_budget_pct=3.0,
        streak_enabled=True,
    )
    defaults.update(kwargs)
    return PineGuardian(**defaults)


def valid_signal(symbol="EURUSD", entry=1.1, sl=1.095, size=0.45):
    return {"symbol": symbol, "entry": entry, "sl": sl, "size": size}


# ── 1. Session Classification ─────────────────────────────────────────────────

class TestSessionClassification:
    def test_london_session(self):
        assert PineGuardian.classify_session(7) == TradingSession.LONDON
        assert PineGuardian.classify_session(9) == TradingSession.LONDON
        assert PineGuardian.classify_session(11) == TradingSession.LONDON

    def test_ny_session(self):
        assert PineGuardian.classify_session(13) == TradingSession.NEW_YORK
        assert PineGuardian.classify_session(15) == TradingSession.NEW_YORK
        assert PineGuardian.classify_session(17) == TradingSession.NEW_YORK

    def test_off_hours(self):
        assert PineGuardian.classify_session(0) == TradingSession.OFF_HOURS
        assert PineGuardian.classify_session(6) == TradingSession.OFF_HOURS
        assert PineGuardian.classify_session(12) == TradingSession.OFF_HOURS  # lunch gap
        assert PineGuardian.classify_session(18) == TradingSession.OFF_HOURS
        assert PineGuardian.classify_session(23) == TradingSession.OFF_HOURS


# ── 2. Intraday Adjustment (Dimension 1) ─────────────────────────────────────

class TestIntradayAdjustment:
    def test_no_trades_yet(self):
        g = make_guardian()
        assert g.compute_intraday_adjustment() == 0

    def test_one_win(self):
        g = make_guardian()
        g.record_trade(pnl=100.0, utc_hour=9)
        assert g.compute_intraday_adjustment() == +1

    def test_two_wins(self):
        g = make_guardian()
        g.record_trade(pnl=100.0, utc_hour=9)
        g.record_trade(pnl=80.0, utc_hour=9)
        assert g.compute_intraday_adjustment() == +2

    def test_one_loss_no_win(self):
        g = make_guardian()
        g.record_trade(pnl=-50.0, utc_hour=9)
        assert g.compute_intraday_adjustment() == -1

    def test_two_consecutive_losses_circuit_breaker(self):
        g = make_guardian()
        g.record_trade(pnl=-50.0, utc_hour=9)
        g.record_trade(pnl=-30.0, utc_hour=9)
        assert g.compute_intraday_adjustment() == -2

    def test_mixed_win_then_loss(self):
        g = make_guardian()
        g.record_trade(pnl=100.0, utc_hour=9)
        g.record_trade(pnl=-40.0, utc_hour=9)
        assert g.compute_intraday_adjustment() == 0

    def test_loss_resets_consecutive_on_win(self):
        g = make_guardian()
        g.record_trade(pnl=-50.0, utc_hour=9)
        g.record_trade(pnl=-30.0, utc_hour=9)
        # Circuit breaker: −2
        assert g.compute_intraday_adjustment() == -2
        # A win resets consecutive_losses
        g.record_trade(pnl=200.0, utc_hour=9)
        # Now: 1 win, 2 losses → mixed → 0
        assert g.compute_intraday_adjustment() == 0


# ── 3. Streak Bonus (Dimension 2) ─────────────────────────────────────────────

class TestStreakBonus:
    def test_no_streak(self):
        g = make_guardian()
        assert g.compute_streak_bonus(0) == 0

    def test_one_day_streak(self):
        g = make_guardian()
        assert g.compute_streak_bonus(1) == 1

    def test_two_day_streak(self):
        g = make_guardian()
        assert g.compute_streak_bonus(2) == 2

    def test_five_day_streak_capped_at_2(self):
        g = make_guardian()
        assert g.compute_streak_bonus(5) == 2

    def test_streak_disabled(self):
        g = make_guardian(streak_enabled=False)
        assert g.compute_streak_bonus(5) == 0


# ── 4. Session-Slot Separation (Dimension 3) ──────────────────────────────────

class TestSessionSlotSeparation:
    def test_london_base_slots(self):
        g = make_guardian(max_trades_london=2, max_trades_ny=2)
        state = g.compute_effective_limit(streak_days=0, utc_hour=9)
        assert state.session == TradingSession.LONDON
        assert state.session_base == 2

    def test_ny_base_slots(self):
        g = make_guardian(max_trades_london=2, max_trades_ny=2)
        state = g.compute_effective_limit(streak_days=0, utc_hour=14)
        assert state.session == TradingSession.NEW_YORK
        assert state.session_base == 2

    def test_london_full_does_not_block_ny(self):
        g = make_guardian(max_trades_london=2, max_trades_ny=2)
        # Fill London slots with LOSSES (no bonus — base limit applies)
        g.record_trade(pnl=-50.0, utc_hour=9)
        g.record_trade(pnl=-50.0, utc_hour=9)
        # London base=2, consecutive_losses=2 → intraday_adj=−2 → effective=max(1,0)=1
        # But we've already taken 2 trades, slots_remaining = max(0, 1-2) = 0 → blocked
        assert not g.check_max_trades(streak_days=0, utc_hour=9)
        # NY should still be open (independent session pool)
        assert g.check_max_trades(streak_days=0, utc_hour=14)


# ── 5. Combined Effective Limit ───────────────────────────────────────────────

class TestEffectiveLimit:
    def test_base_no_streak_no_intraday(self):
        g = make_guardian(max_trades_london=2, max_trades_hard_cap=6)
        state = g.compute_effective_limit(streak_days=0, utc_hour=9)
        assert state.effective_limit == 2   # 2 + 0 + 0 = 2

    def test_two_wins_two_day_streak_london(self):
        g = make_guardian(max_trades_london=2, max_trades_hard_cap=6)
        g.record_trade(pnl=100.0, utc_hour=9)
        g.record_trade(pnl=100.0, utc_hour=9)
        state = g.compute_effective_limit(streak_days=2, utc_hour=9)
        # 2 (base) + 2 (intraday: 2 wins) + 2 (streak: 2 days) = 6
        assert state.effective_limit == 6

    def test_hard_cap_is_respected(self):
        g = make_guardian(max_trades_london=2, max_trades_hard_cap=4)
        g.record_trade(pnl=200.0, utc_hour=9)
        g.record_trade(pnl=200.0, utc_hour=9)
        state = g.compute_effective_limit(streak_days=5, utc_hour=9)
        # 2 + 2 + 2 = 6, but cap is 4
        assert state.effective_limit == 4

    def test_circuit_breaker_floors_at_1(self):
        g = make_guardian(max_trades_london=2, max_trades_hard_cap=6)
        g.record_trade(pnl=-100.0, utc_hour=9)
        g.record_trade(pnl=-100.0, utc_hour=9)
        state = g.compute_effective_limit(streak_days=0, utc_hour=9)
        # 2 + (−2) + 0 = 0 → floors at 1
        assert state.effective_limit == 1


# ── 6. Risk Budget Gate ───────────────────────────────────────────────────────

class TestRiskBudget:
    def test_budget_starts_full(self):
        g = make_guardian(daily_risk_budget_pct=3.0)
        assert g.check_risk_budget() is True

    def test_budget_exhausted(self):
        g = make_guardian(daily_risk_budget_pct=3.0)
        g.record_trade(pnl=100.0, risk_pct=1.5, utc_hour=9)
        g.record_trade(pnl=100.0, risk_pct=1.5, utc_hour=9)
        # 3.0% deployed >= 3.0% budget
        assert g.check_risk_budget() is False

    def test_budget_gate_blocks_validation(self):
        g = make_guardian(daily_risk_budget_pct=0.4, max_trades_london=10)
        # Record 1 trade eating almost all budget
        g.record_trade(pnl=100.0, risk_pct=0.35, utc_hour=9)
        # Next signal should be blocked by budget (0.35 >= 0.4... not yet)
        g.record_trade(pnl=100.0, risk_pct=0.1, utc_hour=9)
        # Now 0.45 >= 0.4 → blocked
        result = g.validate_signal(valid_signal(), current_balance=50_000.0, utc_hour=9)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.DAILY_RISK_BUDGET_EXHAUSTED


# ── 7. Progressive Risk Scaling ───────────────────────────────────────────────

class TestRiskScaling:
    def test_first_trade_full_risk(self):
        g = make_guardian()
        # 0 trades taken → 100% of risk_per_trade_pct
        assert g.get_effective_risk_pct() == pytest.approx(0.5)

    def test_second_trade_75_pct(self):
        g = make_guardian()
        g.record_trade(pnl=100.0, utc_hour=9)
        assert g.get_effective_risk_pct() == pytest.approx(0.375)

    def test_third_trade_50_pct(self):
        g = make_guardian()
        g.record_trade(pnl=100.0, utc_hour=9)
        g.record_trade(pnl=100.0, utc_hour=9)
        assert g.get_effective_risk_pct() == pytest.approx(0.25)

    def test_fourth_trade_still_50_pct(self):
        g = make_guardian()
        for _ in range(3):
            g.record_trade(pnl=100.0, utc_hour=9)
        assert g.get_effective_risk_pct() == pytest.approx(0.25)


# ── 8. Backward-Compat Static Mode ───────────────────────────────────────────

class TestStaticMode:
    def test_static_mode_uses_single_pool(self):
        g = make_guardian(adaptive_enabled=False, max_trades_per_day=2)
        assert g.check_max_trades() is True
        g.record_trade(pnl=100.0, utc_hour=9)
        g.record_trade(pnl=100.0, utc_hour=14)
        # 2 trades total — blocked regardless of session
        assert g.check_max_trades() is False

    def test_static_mode_ignores_sessions(self):
        g = make_guardian(adaptive_enabled=False, max_trades_per_day=3)
        g.record_trade(pnl=100.0, utc_hour=9)
        g.record_trade(pnl=100.0, utc_hour=14)
        # 2 trades, limit=3 → still open
        assert g.check_max_trades() is True

    def test_adaptive_mode_blocks_validation(self):
        g = make_guardian(adaptive_enabled=False, max_trades_per_day=1)
        g.record_trade(pnl=100.0, utc_hour=9)
        result = g.validate_signal(valid_signal(), current_balance=50_000.0)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.MAX_TRADES_EXCEEDED


# ── 9. Daily Reset ────────────────────────────────────────────────────────────

class TestDailyReset:
    def test_reset_clears_all_counters(self):
        g = make_guardian()
        g.record_trade(pnl=-100.0, utc_hour=9)
        g.record_trade(pnl=-100.0, utc_hour=14)
        g.reset_daily(current_equity=50_000.0)

        assert g.current_day_trades == 0
        assert g.daily_wins == 0
        assert g.daily_losses == 0
        assert g.consecutive_losses == 0
        assert g.daily_risk_deployed_pct == 0.0
        assert g.compute_intraday_adjustment() == 0

    def test_check_max_trades_after_reset(self):
        g = make_guardian(max_trades_london=2)
        # Take 2 trades with losses so adaptive doesn't expand the limit
        g.record_trade(pnl=-100.0, utc_hour=9)
        g.record_trade(pnl=-100.0, utc_hour=9)
        # consecutive_losses=2 → intraday_adj=−2 → effective=max(1,0)=1<2 → blocked
        assert not g.check_max_trades(streak_days=0, utc_hour=9)
        g.reset_daily(50_000.0)
        # After reset, should be open again
        assert g.check_max_trades(streak_days=0, utc_hour=9)
